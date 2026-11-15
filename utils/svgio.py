# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""svgio on CPython: SVG decode, the same API as MicroPython's built-in
svgio (micropython-pydevices' modules/svgio), over resvg and Pillow.

    d = svgio.SvgDecoder()
    w, h = d.open("wifi.svg", width=48)          # or bytes, or a stream
    d.decode(pixels, alpha)                      # RGB565 and coverage
    d.decode(fb_buf, x=10, y=10, stride=480)     # blended over what's there
    d.decode(fb_buf, rows=(0, 120))              # a band of the picture
    d.open(drawing)                              # or a drawing in the compact form

An app imports svgio and doesn't care which runtime it's on. Pixels are
native-order (little-endian) RGB565, as displaydev framebuffers hold them.
resvg reads more SVG than the MicroPython module does, so a file that draws
the same everywhere keeps to what that module reads: shapes, paths,
strokes, transforms, opacity and gradients, with text turned into paths.
"""

import io
import struct

try:
    import resvg_py
    from PIL import Image, ImageChops
except ImportError as e:  # pragma: no cover - the message is the point
    raise ImportError(
        "svgio needs resvg-py and Pillow on CPython. Install them with:  pip install resvg-py pillow"
    ) from e

_MAX = 32767


def _render(text, zoom):
    """The SVG drawn at zoom, as a Pillow RGBA image."""
    try:
        png = resvg_py.svg_to_bytes(svg_string=text, zoom=zoom, skip_system_fonts=True)
    except ValueError:
        raise ValueError("svgio: not an SVG with a size") from None
    return Image.open(io.BytesIO(png)).convert("RGBA")


def _to_565(rgb):
    """A Pillow RGB image as native-order RGB565 bytes, truncating as the C module does."""
    r, g, b = rgb.split()
    # the two bytes of each pixel, built from disjoint bits so add() never clips
    hi = ImageChops.add(r.point(lambda v: v & 0xF8), g.point(lambda v: v >> 5))
    lo = ImageChops.add(g.point(lambda v: (v & 0x1C) << 3), b.point(lambda v: v >> 3))
    return Image.merge("LA", (lo, hi)).tobytes()


_NO_PAINT, _NO_STROKE, _GRADIENT = 0xFFFFFFFF, 0xFFFFFFFE, 0x1000000


def _n(v):
    return "%.5g" % v


def _paint(paint):
    if paint == _NO_PAINT:
        return "none"
    if paint >= _GRADIENT:
        return "url(#g%d)" % (paint - _GRADIENT)
    return "#%06x" % paint


class _Records:
    """A compact drawing being read: fields come off the front."""

    def __init__(self, data, f):
        self.data, self.at, self.f = data, 5, f

    def take(self, fmt):
        fmt = "<" + fmt.replace("F", self.f)
        try:
            values = struct.unpack_from(fmt, self.data, self.at)
        except struct.error:
            raise ValueError("svgio: not a drawing in svgio's compact form") from None
        self.at += struct.calcsize(fmt)
        return values

    def text(self, n):
        if self.at + n > len(self.data):
            raise ValueError("svgio: not a drawing in svgio's compact form")
        self.at += n
        return self.data[self.at - n : self.at].decode("utf-8")

    def style(self, first="", last=""):
        fill, stroke, width, opacity, n = self.take("II2FH")
        extra = first + self.text(n)
        if last:
            extra = (extra + " " + last).strip()
        s = ' fill="%s"' % _paint(fill)
        if stroke != _NO_STROKE:
            s += ' stroke="%s" stroke-width="%s" stroke-linecap="round" stroke-linejoin="round"' % (_paint(stroke), _n(width))
        if opacity < 1:
            s += ' opacity="%s"' % _n(opacity)
        return s + " " + extra if extra else s

    def stops(self, count):
        out = []
        for _ in range(count):
            offset, color, opacity = self.take("FIF")
            s = '<stop offset="%s" stop-color="%s"' % (_n(offset), _paint(color))
            out.append(s + (' stop-opacity="%s"/>' % _n(opacity) if opacity < 1 else "/>"))
        return "".join(out)

    def path_data(self, n):
        out, end = [], self.at + n
        while self.at < end:
            (op,) = self.take("B")
            letter = chr(op)
            if letter in "MLP":
                out.append("%s%s %s" % (("" if letter == "P" else letter,) + tuple(_n(v) for v in self.take("2F"))))
            elif letter in "QC":
                out.append(letter + " ".join(_n(v) for v in self.take("4F" if letter == "Q" else "6F")))
            elif letter == "Z":
                out.append("Z")
            elif letter == "T":
                out.append(self.text(self.take("H")[0]))
            else:
                raise ValueError("svgio: not a drawing in svgio's compact form")
        return "".join(out)


def expand(drawing):
    """The SVG text a drawing in the compact form stands for, as bytes.

    The compact form is SVG with its numbers left as numbers, records that
    ``struct.pack`` makes; the firmware module's README lists them. Here a
    drawing made with floats of either size is read.
    """
    data = bytes(memoryview(drawing).cast("B"))
    if data[:4] != b"\x01SVG" or len(data) < 5:
        raise ValueError("svgio: not a drawing in svgio's compact form")
    if data[4] not in (4, 8):
        raise ValueError("svgio: a compact drawing made for another size of float")
    r = _Records(data, "f" if data[4] == 4 else "d")
    out = []
    gradients = 0
    while r.at < len(data):
        (op,) = r.take("B")
        if op == 1:
            cx, cy, radius = r.take("3F")
            out.append('<circle cx="%s" cy="%s" r="%s"%s/>' % (_n(cx), _n(cy), _n(radius), r.style()))
        elif op == 2:
            cx, cy, rx, ry, rot = r.take("5F")
            turn = 'transform="rotate(%s %s %s)"' % (_n(rot), _n(cx), _n(cy)) if rot else ""
            out.append('<ellipse cx="%s" cy="%s" rx="%s" ry="%s"%s/>' % (_n(cx), _n(cy), _n(rx), _n(ry), r.style(last=turn)))
        elif op == 3:
            x, y, w, h, radius = r.take("5F")
            first = 'rx="%s" ' % _n(radius) if radius else ""
            out.append('<rect x="%s" y="%s" width="%s" height="%s"%s/>' % (_n(x), _n(y), _n(w), _n(h), r.style(first)))
        elif op == 4:
            d = r.path_data(r.take("I")[0])
            out.append('<path d="%s"%s/>' % (d, r.style()))
        elif op == 6:
            opacity, n = r.take("FH")
            attrs = ' transform="%s"' % r.text(n) if n else ""
            out.append("<g%s%s>" % (attrs, ' opacity="%s"' % _n(opacity) if opacity < 1 else ""))
        elif op == 7:
            out.append("</g>")
        elif op == 8:
            x, y, rot, scale, flip = r.take("4FB")
            t = "translate(%s %s)" % (_n(x), _n(y))
            if rot:
                t += " rotate(%s)" % _n(rot)
            if flip:
                t += " scale(%s %s)" % (_n(-scale), _n(scale))
            elif scale != 1:
                t += " scale(%s)" % _n(scale)
            out.append('<g transform="%s">' % t)
        elif op == 10:
            x, y, w, h = r.take("4F")
            out.append(
                '<svg xmlns="http://www.w3.org/2000/svg" width="%s" height="%s" viewBox="%s %s %s %s"><defs>'
                % (_n(w), _n(h), _n(x), _n(y), _n(w), _n(h))
            )
        elif op == 11:
            x1, y1, x2, y2, user, count = r.take("4FBB")
            units = ' gradientUnits="userSpaceOnUse"' if user else ""
            out.append(
                '<linearGradient id="g%d" x1="%s" y1="%s" x2="%s" y2="%s"%s>%s</linearGradient>'
                % (gradients, _n(x1), _n(y1), _n(x2), _n(y2), units, r.stops(count))
            )
            gradients += 1
        elif op == 12:
            cx, cy, radius, focus, fx, fy, user, count = r.take("3FB2FBB")
            where = ' fx="%s" fy="%s"' % (_n(fx), _n(fy)) if focus else ""
            units = ' gradientUnits="userSpaceOnUse"' if user else ""
            out.append(
                '<radialGradient id="g%d" cx="%s" cy="%s" r="%s"%s%s>%s</radialGradient>'
                % (gradients, _n(cx), _n(cy), _n(radius), where, units, r.stops(count))
            )
            gradients += 1
        elif op == 13:
            out.append("</defs>")
        elif op == 14:
            out.append("</svg>")
        else:
            raise ValueError("svgio: not a drawing in svgio's compact form")
    return "".join(out).encode()


class SvgDecoder:
    """``SvgDecoder()``: ``open(source, width=)``, then ``decode(target, alpha)``."""

    def __init__(self, *, memory=None):
        # The firmware module works inside `memory` bytes of its own. Here
        # resvg has its own memory, so the argument is checked and kept.
        if memory is not None and memory < 4096:
            raise ValueError("svgio: memory must be at least 4096 bytes")
        self._memory = 0 if memory is None else memory & ~7
        self._text = None
        self._size = None
        self._zoom = 1.0

    @property
    def memory(self):
        return self._memory

    @property
    def memory_peak(self):
        """Always 0 here: the working memory is resvg's, not this decoder's."""
        return 0

    @property
    def width(self):
        if self._size is None:
            raise RuntimeError("width needs a successful open()")
        return self._size[0]

    @property
    def height(self):
        if self._size is None:
            raise RuntimeError("height needs a successful open()")
        return self._size[1]

    def open(self, source, *, width=None, height=None, scale=None):
        """``source``: bytes-like, a path, or a binary stream. Returns (width, height)."""
        if sum(v is not None for v in (width, height, scale)) > 1:
            raise ValueError("give one of width, height and scale")
        self._text = self._size = None
        if isinstance(source, str):
            with open(source, "rb") as f:
                data = f.read()
        elif hasattr(source, "read"):
            data = source.read()
        else:
            data = bytes(memoryview(source).cast("B"))
        if data[:4] == b"\x01SVG":
            data = expand(data)
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("svgio: not an SVG with a size") from None
        own = _render(text, 1.0).size
        if width is not None:
            zoom = width / own[0]
        elif height is not None:
            zoom = height / own[1]
        else:
            zoom = 1.0 if scale is None else float(scale)
        w, h = int(own[0] * zoom + 0.5), int(own[1] * zoom + 0.5)
        if not (zoom > 0 and 1 <= w <= _MAX and 1 <= h <= _MAX):
            raise ValueError("svgio: the size must come to 1..32767 pixels a side")
        self._text, self._size, self._zoom = text, (w, h), zoom
        return w, h

    def decode(self, target, alpha=None, *, x=0, y=0, stride=None, rows=None):
        """RGB565 into ``target`` and coverage into ``alpha``; ``target`` alone blends.

        ``rows=(first, end)`` draws only those rows of the image, where they
        sit in the whole picture.
        """
        if self._text is None:
            raise RuntimeError("decode() needs a successful open()")
        if target is None and alpha is None:
            raise ValueError("give a target, an alpha buffer, or both")
        w, h = self._size
        y0, y1 = 0, h
        if rows is not None:
            if len(rows) != 2 or not 0 <= rows[0] <= rows[1] <= h:
                raise ValueError("rows is (first, end) within the image's height")
            y0, y1 = rows
        stride = w if stride is None else stride
        if x < 0 or y < 0 or x + w > stride:
            raise ValueError("the image doesn't fit across the target at that x and stride")
        pix = memoryview(target).cast("B") if target is not None else None
        cov = memoryview(alpha).cast("B") if alpha is not None else None
        last = (y + y1 - 1) * stride + x + w if y1 > y0 else 0
        if pix is not None and pix.nbytes < last * 2:
            raise ValueError("target has %d bytes; it needs %d" % (pix.nbytes, last * 2))
        if cov is not None and cov.nbytes < last:
            raise ValueError("alpha has %d bytes; it needs %d" % (cov.nbytes, last))
        if y1 == y0:
            return

        image = _render(self._text, self._zoom)
        if image.size != (w, h):
            # resvg rounds its canvas up; the C module rounds to nearest
            canvas = Image.new("RGBA", (w, h))
            canvas.paste(image.crop((0, 0, min(w, image.width), min(h, image.height))), (0, 0))
            image = canvas
        a = image.getchannel("A")
        rows = range(y0, y1)

        if cov is not None:
            mask = a.tobytes()
            for j in rows:
                at = (y + j) * stride + x
                cov[at : at + w] = mask[j * w : (j + 1) * w]
            if pix is not None:
                px = _to_565(image.convert("RGB"))
                for j in rows:
                    at = ((y + j) * stride + x) * 2
                    pix[at : at + w * 2] = px[j * w * 2 : (j + 1) * w * 2]
            return

        # Blended over what the target holds, widened to 8 bits a channel.
        under = b"".join(bytes(pix[((y + j) * stride + x) * 2 : ((y + j) * stride + x + w) * 2]) for j in rows)
        back = Image.frombuffer("RGB", (w, y1 - y0), under, "raw", "BGR;16", 0, 1)
        band = (0, y0, w, y1)
        px = _to_565(Image.composite(image.convert("RGB").crop(band), back, a.crop(band)))
        for j in rows:
            at = ((y + j) * stride + x) * 2
            pix[at : at + w * 2] = px[(j - y0) * w * 2 : (j - y0 + 1) * w * 2]
