# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""svgio's compact form, read back into SVG text.

``expand(drawing)`` gives the SVG a compact drawing stands for. Both of
svgio's backends here, the desktop's and the browser's, open a compact
drawing by expanding it first.
"""

import struct

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
            s += ' stroke="%s" stroke-width="%s"' % (_paint(stroke), _n(width))
            # round, unless the extra attributes say how
            for name in ("stroke-linecap", "stroke-linejoin"):
                if name not in extra:
                    s += ' %s="round"' % name
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
