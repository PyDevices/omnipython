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
    d.decode(pixels, alpha, colors={0xFF0000: 0x00A0FF})    # in other colours

An app imports svgio and doesn't care which runtime it's on. Pixels are
native-order (little-endian) RGB565, as displaydev framebuffers hold them.
resvg reads more SVG than the MicroPython module does, so a file that draws
the same everywhere keeps to what that module reads: shapes, paths,
strokes, transforms, opacity and gradients, with text turned into paths.
"""

import io
import re

from _svgio_compact import expand

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


_HEX = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-fA-F])")


def _recolored(text, colors):
    """*text* with each colour written as hex swapped for its value in *colors*."""
    if not isinstance(colors, dict):
        raise TypeError("colors is a dict of 0xRRGGBB to 0xRRGGBB")
    if any(not 0 <= c <= 0xFFFFFF for pair in colors.items() for c in pair):
        raise ValueError("colors is a dict of 0xRRGGBB to 0xRRGGBB")

    def swap(m):
        digits = m.group(1)
        if len(digits) == 3:
            digits = "".join(c * 2 for c in digits)
        value = int(digits, 16)
        return "#%06x" % colors[value] if value in colors else m.group(0)

    return _HEX.sub(swap, text) if colors else text


class Buffer(bytearray):
    """Bytes to draw pictures into.

    On a board these come from outside MicroPython's heap, where its
    collector doesn't read them. Here it is a ``bytearray`` with ``close()``.
    """

    def __init__(self, size):
        if size < 1:
            raise ValueError("svgio: a Buffer has at least one byte")
        super().__init__(size)

    def close(self):
        """Let the bytes go, unless a memoryview still shows them."""
        try:
            self.clear()
        except BufferError:
            pass


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

    def close(self):
        """Let go of the SVG."""
        self._text = self._size = None
        self._memory = 0

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

    def decode(self, target, alpha=None, *, x=0, y=0, stride=None, rows=None, colors=None):
        """RGB565 into ``target`` and coverage into ``alpha``; ``target`` alone blends.

        ``rows=(first, end)`` draws only those rows of the image, where they
        sit in the whole picture. ``colors={0xRRGGBB: 0xRRGGBB}`` draws it
        with those colours swapped; here that reaches colours the SVG writes
        as ``#rrggbb`` or ``#rgb``, not ones it names or writes as ``rgb()``.
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
        text = self._text if colors is None else _recolored(self._text, colors)
        if y1 == y0:
            return

        image = _render(text, self._zoom)
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
