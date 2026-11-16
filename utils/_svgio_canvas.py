# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""svgio under Pyodide: the browser's 2D canvas draws the SVG.

``import svgio`` picks this module when Python runs in a browser. It reads
the SVG itself and draws it on an ``OffscreenCanvas``, so it works on the
page's main thread and in a worker, needs nothing installed, and never
waits: every call returns with its pixels.

It reads what MicroPython's svgio reads and nothing more: ``svg``, ``g``,
``path``, ``rect``, ``circle``, ``ellipse``, ``line``, ``polyline`` and
``polygon``; fills and strokes with their widths, caps, joins and dashes;
transforms; opacity; linear and radial gradients; and class rules in a
``<style>`` sheet. Colours are ``#rgb``, ``#rrggbb``, ``rgb()`` and the ten
names that module knows, and any other colour is grey, as it is there. Text,
``<use>``, clip paths, masks, patterns, filters and images are left out.
What it does read it draws as the SVG standard says, which is how the
desktop's resvg draws it too.
"""

import math
import re
import xml.etree.ElementTree as ET

try:
    import js
except ImportError:  # CPython: only the reading half works, which the tests use
    js = None

_MAX = 32767
_NOT_SVG = "svgio: not an SVG with a size"
_SVG_NS = "{http://www.w3.org/2000/svg}"
_HREF = "{http://www.w3.org/1999/xlink}href"
_IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
_DPI = 96.0
_MAX_DASHES = 8
_MAX_CYCLES = 256  # of a repeated or reflected gradient across the picture

_NUMBER = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")
_PATH_NUMBER = re.compile(r"[\s,]*(" + _NUMBER.pattern + ")")
_PATH_FLAG = re.compile(r"[\s,]*([01])")
_PATH_COMMAND = re.compile(r"[\s,]*([MmLlHhVvCcSsQqTtAaZz])")
_PATH_ARGS = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7}
_TRANSFORM = re.compile(r"(matrix|translate|scale|rotate|skewX|skewY)\s*\(([^)]*)\)")
_HEX = re.compile(r"#([0-9a-fA-F]+)")
_RGB = re.compile(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)")
_RGB_PERCENT = re.compile(r"rgb\(\s*\+?(\d+(?:\.\d+)?)%\s*,\s*\+?(\d+(?:\.\d+)?)%\s*,\s*\+?(\d+(?:\.\d+)?)%\s*\)")
_GREY = (128, 128, 128)
_NAMED = {
    "red": (255, 0, 0),
    "green": (0, 128, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "cyan": (0, 255, 255),
    "magenta": (255, 0, 255),
    "black": (0, 0, 0),
    "grey": _GREY,
    "gray": _GREY,
    "white": (255, 255, 255),
}
_UNITS = ("px", "pt", "pc", "mm", "cm", "in", "em", "ex")
_CAPS = ("butt", "round", "square")
_JOINS = ("miter", "round", "bevel")
_SHAPES = ("path", "rect", "circle", "ellipse", "line", "polyline", "polygon")


# --- numbers, colours and matrices -------------------------------------------


def _number(text):
    """The number ``text`` starts with, or 0."""
    m = _NUMBER.match(text.strip())
    return float(m.group()) if m else 0.0


def _coordinate(text):
    """``text`` as (value, unit), the unit one of _UNITS, "%" or ""."""
    text = text.strip()
    m = _NUMBER.match(text)
    if not m:
        return 0.0, ""
    rest = text[m.end() : m.end() + 2]
    if rest[:1] == "%":
        return float(m.group()), "%"
    return float(m.group()), rest if rest in _UNITS else ""


def _pixels(coordinate, origin, length, font):
    """A coordinate in user units; a percentage is of ``length``, from ``origin``."""
    value, unit = coordinate
    if unit == "%":
        return origin + value / 100.0 * length
    if unit == "pt":
        return value / 72.0 * _DPI
    if unit == "pc":
        return value / 6.0 * _DPI
    if unit == "mm":
        return value / 25.4 * _DPI
    if unit == "cm":
        return value / 2.54 * _DPI
    if unit == "in":
        return value * _DPI
    if unit == "em":
        return value * font
    if unit == "ex":
        return value * font * 0.52
    return value


def _unit_interval(text):
    return min(1.0, max(0.0, _number(text)))


def _colour(text):
    """A colour as (r, g, b). What MicroPython's svgio can't read is grey there, and here."""
    text = text.strip()
    if text.startswith("#"):
        digits = _HEX.match(text)
        digits = digits.group(1) if digits else ""
        if len(digits) >= 5:
            return int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16)
        if len(digits) >= 3:
            return int(digits[0], 16) * 17, int(digits[1], 16) * 17, int(digits[2], 16) * 17
        return _GREY
    if text.startswith("rgb("):
        m = _RGB.match(text)
        if m:
            return tuple(min(255, int(v)) for v in m.groups())
        m = _RGB_PERCENT.match(text)
        if m:
            return tuple(min(255, int(float(v) * 255 / 100 + 0.5)) for v in m.groups())
        return _GREY
    return _NAMED.get(text, _GREY)


def _css(rgb, alpha=1.0):
    if alpha >= 1.0:
        return "#%02x%02x%02x" % rgb
    return "rgba(%d,%d,%d,%s)" % (rgb[0], rgb[1], rgb[2], _fmt(alpha))


def _fmt(value):
    """A number as the canvas reads it, short and without float noise."""
    return "%.7g" % value


def _mul(m, n):
    """The matrix that applies ``n``, then ``m``. A matrix is (a, b, c, d, e, f), as the canvas takes it."""
    return (
        m[0] * n[0] + m[2] * n[1],
        m[1] * n[0] + m[3] * n[1],
        m[0] * n[2] + m[2] * n[3],
        m[1] * n[2] + m[3] * n[3],
        m[0] * n[4] + m[2] * n[5] + m[4],
        m[1] * n[4] + m[3] * n[5] + m[5],
    )


def _invert(m):
    det = m[0] * m[3] - m[1] * m[2]
    if abs(det) < 1e-12:
        return None
    a, b, c, d = m[3] / det, -m[1] / det, -m[2] / det, m[0] / det
    return (a, b, c, d, -(a * m[4] + c * m[5]), -(b * m[4] + d * m[5]))


def _apply(m, x, y):
    return m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]


def _transform(text):
    """A ``transform`` attribute as one matrix."""
    out = _IDENTITY
    for name, body in _TRANSFORM.findall(text):
        a = [float(v) for v in _NUMBER.findall(body)]
        n = len(a)
        if name == "matrix":
            t = tuple(a) if n == 6 else _IDENTITY
        elif name == "translate":
            t = (1.0, 0.0, 0.0, 1.0, a[0], a[1] if n > 1 else 0.0) if n else _IDENTITY
        elif name == "scale":
            t = (a[0], 0.0, 0.0, a[1] if n > 1 else a[0], 0.0, 0.0) if n else _IDENTITY
        elif name == "rotate":
            if not n:
                continue
            r = math.radians(a[0])
            t = (math.cos(r), math.sin(r), -math.sin(r), math.cos(r), 0.0, 0.0)
            if n > 2:
                t = _mul((1.0, 0.0, 0.0, 1.0, a[1], a[2]), _mul(t, (1.0, 0.0, 0.0, 1.0, -a[1], -a[2])))
        elif name == "skewX":
            t = (1.0, 0.0, math.tan(math.radians(a[0])), 1.0, 0.0, 0.0) if n else _IDENTITY
        else:
            t = (1.0, math.tan(math.radians(a[0])), 0.0, 1.0, 0.0, 0.0) if n else _IDENTITY
        out = _mul(out, t)
    return out


# --- shapes as path data, and the box each one fills -------------------------


class _Box:
    """The smallest rectangle around the points and curves added to it."""

    def __init__(self):
        self.x0 = self.y0 = self.x1 = self.y1 = None

    def add(self, x, y):
        if self.x0 is None:
            self.x0 = self.x1 = x
            self.y0 = self.y1 = y
        else:
            self.x0, self.x1 = min(self.x0, x), max(self.x1, x)
            self.y0, self.y1 = min(self.y0, y), max(self.y1, y)

    def cubic(self, p):
        """A cubic Bézier, as eight numbers: its ends and wherever it turns back."""
        self.add(p[0], p[1])
        self.add(p[6], p[7])
        for axis in (0, 1):
            p0, p1, p2, p3 = p[axis], p[axis + 2], p[axis + 4], p[axis + 6]
            a = 3.0 * (-p0 + 3.0 * p1 - 3.0 * p2 + p3)
            b = 6.0 * (p0 - 2.0 * p1 + p2)
            c = 3.0 * (p1 - p0)
            if abs(a) < 1e-12:
                roots = [-c / b] if abs(b) > 1e-12 else []
            else:
                disc = b * b - 4.0 * a * c
                if disc < 0:
                    continue
                root = math.sqrt(disc)
                roots = [(-b + root) / (2.0 * a), (-b - root) / (2.0 * a)]
            for t in roots:
                if 0.0 < t < 1.0:
                    u = 1.0 - t
                    v = u * u * u * p0 + 3.0 * u * u * t * p1 + 3.0 * u * t * t * p2 + t * t * t * p3
                    q = list(p[0:2])
                    q[axis] = v
                    # the other axis is somewhere on the curve, so an end already covers it
                    self.add(q[0], q[1])

    def arc(self, x0, y0, rx, ry, rotation, large, sweep, x, y):
        """An elliptical arc from (x0, y0) to (x, y), by the SVG endpoint rule."""
        self.add(x0, y0)
        self.add(x, y)
        phi = math.radians(rotation)
        cos_phi, sin_phi = math.cos(phi), math.sin(phi)
        dx, dy = (x0 - x) / 2.0, (y0 - y) / 2.0
        x1 = cos_phi * dx + sin_phi * dy
        y1 = -sin_phi * dx + cos_phi * dy
        scale = (x1 * x1) / (rx * rx) + (y1 * y1) / (ry * ry)
        if scale > 1.0:
            rx, ry = rx * math.sqrt(scale), ry * math.sqrt(scale)
        top = rx * rx * ry * ry - rx * rx * y1 * y1 - ry * ry * x1 * x1
        bottom = rx * rx * y1 * y1 + ry * ry * x1 * x1
        k = math.sqrt(max(0.0, top / bottom)) if bottom else 0.0
        if large == sweep:
            k = -k
        cx1, cy1 = k * rx * y1 / ry, -k * ry * x1 / rx
        cx = cos_phi * cx1 - sin_phi * cy1 + (x0 + x) / 2.0
        cy = sin_phi * cx1 + cos_phi * cy1 + (y0 + y) / 2.0
        start = math.atan2((y1 - cy1) / ry, (x1 - cx1) / rx)
        end = math.atan2((-y1 - cy1) / ry, (-x1 - cx1) / rx)
        span = end - start
        if sweep and span < 0:
            span += 2.0 * math.pi
        elif not sweep and span > 0:
            span -= 2.0 * math.pi
        # where x, then y, stops growing along the ellipse, every half turn
        for base in (math.atan2(-ry * sin_phi, rx * cos_phi), math.atan2(ry * cos_phi, rx * sin_phi)):
            for half in range(-2, 4):
                theta = base + half * math.pi
                along = (theta - start) if sweep else (start - theta)
                along %= 2.0 * math.pi
                if along < abs(span):
                    ex, ey = rx * math.cos(theta), ry * math.sin(theta)
                    self.add(cx + cos_phi * ex - sin_phi * ey, cy + sin_phi * ex + cos_phi * ey)

    def rect(self):
        """(x, y, width, height), or None when nothing was added."""
        if self.x0 is None:
            return None
        return self.x0, self.y0, self.x1 - self.x0, self.y1 - self.y0


def _join(*parts):
    return " ".join(p if isinstance(p, str) else _fmt(p) for p in parts)


def _path(d):
    """Path data rewritten with absolute M, L, C, Q, A and Z only, and its box.

    Reading stops at the first thing that isn't path data, and what came
    before it is drawn, as the SVG standard asks.
    """
    out, box = [], _Box()
    pos = 0
    command = None
    x = y = start_x = start_y = 0.0
    control = None  # the last C or Q control point, for S and T to mirror
    last = ""
    while True:
        m = _PATH_COMMAND.match(d, pos)
        if m:
            command = m.group(1)
            pos = m.end()
            if command in "Zz":
                if out:
                    out.append("Z")
                    x, y = start_x, start_y
                last = "Z"
                continue
        elif command is None or command in "Zz":
            break
        kind = command.upper()
        if not out and kind != "M":
            break
        args = []
        for i in range(_PATH_ARGS[kind]):
            m = (_PATH_FLAG if kind == "A" and i in (3, 4) else _PATH_NUMBER).match(d, pos)
            if not m:
                break
            args.append(float(m.group(1)))
            pos = m.end()
        if len(args) < _PATH_ARGS[kind]:
            break
        ox, oy = (x, y) if command.islower() else (0.0, 0.0)
        if kind == "M":
            x, y = ox + args[0], oy + args[1]
            start_x, start_y = x, y
            out.append(_join("M", x, y))
            command = "l" if command == "m" else "L"  # more pairs are lines
        elif kind in "LHV":
            nx = ox + args[0] if kind != "V" else x
            ny = oy + args[-1] if kind != "H" else y
            box.add(x, y)
            box.add(nx, ny)
            out.append(_join("L", nx, ny))
            x, y = nx, ny
        elif kind in "CS":
            if kind == "C":
                c1 = (ox + args[0], oy + args[1])
                rest = args[2:]
            else:
                c1 = (2 * x - control[0], 2 * y - control[1]) if last in "CS" and control else (x, y)
                rest = args
            c2 = (ox + rest[0], oy + rest[1])
            nx, ny = ox + rest[2], oy + rest[3]
            box.cubic((x, y, c1[0], c1[1], c2[0], c2[1], nx, ny))
            out.append(_join("C", c1[0], c1[1], c2[0], c2[1], nx, ny))
            control = c2
            x, y = nx, ny
        elif kind in "QT":
            if kind == "Q":
                c = (ox + args[0], oy + args[1])
                rest = args[2:]
            else:
                c = (2 * x - control[0], 2 * y - control[1]) if last in "QT" and control else (x, y)
                rest = args
            nx, ny = ox + rest[0], oy + rest[1]
            third = 2.0 / 3.0
            box.cubic(
                (x, y, x + third * (c[0] - x), y + third * (c[1] - y),
                 nx + third * (c[0] - nx), ny + third * (c[1] - ny), nx, ny)
            )
            out.append(_join("Q", c[0], c[1], nx, ny))
            control = c
            x, y = nx, ny
        else:
            rx, ry = abs(args[0]), abs(args[1])
            nx, ny = ox + args[5], oy + args[6]
            if (nx, ny) != (x, y):
                if rx == 0 or ry == 0:
                    box.add(x, y)
                    box.add(nx, ny)
                    out.append(_join("L", nx, ny))
                else:
                    box.arc(x, y, rx, ry, args[2], args[3], args[4], nx, ny)
                    out.append(_join("A", rx, ry, args[2], int(args[3]), int(args[4]), nx, ny))
            x, y = nx, ny
        last = kind
    return " ".join(out), box.rect()


def _rect(x, y, w, h, rx, ry):
    if not (w > 0 and h > 0):
        return "", None
    if rx < 0 and ry > 0:
        rx = ry
    if ry < 0 and rx > 0:
        ry = rx
    rx, ry = min(max(rx, 0.0), w / 2.0), min(max(ry, 0.0), h / 2.0)
    if rx < 0.00001 or ry < 0.0001:
        d = _join("M", x, y, "L", x + w, y, "L", x + w, y + h, "L", x, y + h, "Z")
    else:
        d = _join(
            "M", x + rx, y, "L", x + w - rx, y, "A", rx, ry, 0, 0, 1, x + w, y + ry,
            "L", x + w, y + h - ry, "A", rx, ry, 0, 0, 1, x + w - rx, y + h,
            "L", x + rx, y + h, "A", rx, ry, 0, 0, 1, x, y + h - ry,
            "L", x, y + ry, "A", rx, ry, 0, 0, 1, x + rx, y, "Z",
        )  # fmt: skip
    return d, (x, y, w, h)


def _ellipse(cx, cy, rx, ry):
    if not (rx > 0 and ry > 0):
        return "", None
    d = _join("M", cx + rx, cy, "A", rx, ry, 0, 1, 1, cx - rx, cy, "A", rx, ry, 0, 1, 1, cx + rx, cy, "Z")
    return d, (cx - rx, cy - ry, 2 * rx, 2 * ry)


def _poly(points, closed):
    v = [float(n) for n in _NUMBER.findall(points)]
    if len(v) < 4:
        return "", None
    box = _Box()
    parts = []
    for i in range(0, len(v) - 1, 2):
        box.add(v[i], v[i + 1])
        parts.append(_join("L" if i else "M", v[i], v[i + 1]))
    if closed:
        parts.append("Z")
    return " ".join(parts), box.rect()


# --- the SVG as a list of things to draw -------------------------------------


class _Reader:
    """Reads an SVG's elements into ``ops``, the fills and strokes in drawing order.

    An op is one of:

    - ``("fill", path, matrix, rule, paint, alpha)``
    - ``("stroke", path, matrix, paint, alpha, width, cap, join, miter, dashes, dash_offset)``
    - ``("layer",)`` and ``("end", alpha)`` around what one opacity covers

    A paint is a colour as the canvas reads it, or a gradient:
    ``(kind, geometry, stops, spread, matrix)``, with kind "linear" or
    "radial", geometry in the gradient's own space and matrix taking that
    space to the SVG's.
    """

    def __init__(self, root):
        self.ops = []
        self.gradients = {}
        self.styles = []
        self.size = None  # (width, height) in pixels, as written
        self.view = None  # (x, y, width, height) of the user space it shows
        self.align = ("Mid", "Mid", "meet")
        state = {
            "m": _IDENTITY, "fill": "#000000", "fill_op": 1.0, "stroke": None, "stroke_op": 1.0,
            "width": 1.0, "dashes": (), "dash_offset": 0.0, "cap": "butt", "join": "miter", "miter": 4.0,
            "rule": "nonzero", "visible": True, "font": 0.0, "stroke_first": False, "opacity": 1.0,
            "stop_colour": (0, 0, 0), "stop_op": 1.0, "stop_offset": 0.0,
        }  # fmt: skip
        self._root(root, state)
        self.ops = [op for op in (self._resolve(op) for op in self.ops) if op is not None]
        if state["opacity"] < 1.0:
            self.ops = [("layer",)] + self.ops + [("end", state["opacity"])]

    # ---- attributes ----

    def _length(self, text, origin, length, state):
        return _pixels(_coordinate(text), origin, length, state["font"])

    def _diagonal(self):
        view = self.view or (0.0, 0.0, 0.0, 0.0)
        return math.sqrt((view[2] * view[2] + view[3] * view[3]) / 2.0)

    def _paint(self, value):
        value = value.strip()
        if value == "none":
            return None
        if value.startswith("url("):
            return ("url", value[4:].lstrip("#").split(")")[0])
        return _css(_colour(value))

    def _attribute(self, state, name, value):
        """Apply one presentation attribute. False when ``name`` isn't one."""
        value = value.strip()
        if name == "style":
            for declaration in value.split(";"):
                key, _, text = declaration.partition(":")
                if key.strip():
                    self._attribute(state, key.strip(), text.strip())
        elif name == "class":
            for word in value.split():
                # the rule written last is read first, so the first one written wins
                for cls, text in reversed(self.styles):
                    if cls == word:
                        self._attribute(state, "style", text)
        elif name == "display":
            if value.strip() == "none":
                state["visible"] = False
        elif name == "fill":
            state["fill"] = self._paint(value)
        elif name == "stroke":
            state["stroke"] = self._paint(value)
        elif name == "opacity":
            state["opacity"] = _unit_interval(value)
        elif name == "fill-opacity":
            state["fill_op"] = _unit_interval(value)
        elif name == "stroke-opacity":
            state["stroke_op"] = _unit_interval(value)
        elif name == "stroke-width":
            state["width"] = self._length(value, 0.0, self._diagonal(), state)
        elif name == "stroke-dasharray":
            dashes = []
            if not value.strip().startswith("n"):
                for item in re.split(r"[\s,]+", value.strip()):
                    if item and len(dashes) < _MAX_DASHES:
                        dashes.append(abs(self._length(item, 0.0, self._diagonal(), state)))
            state["dashes"] = tuple(dashes) if sum(dashes) > 1e-6 else ()
        elif name == "stroke-dashoffset":
            state["dash_offset"] = self._length(value, 0.0, self._diagonal(), state)
        elif name == "stroke-linecap":
            state["cap"] = value if value in _CAPS else "butt"
        elif name == "stroke-linejoin":
            state["join"] = value if value in _JOINS else "miter"
        elif name == "stroke-miterlimit":
            state["miter"] = max(0.0, _number(value))
        elif name == "fill-rule":
            state["rule"] = "evenodd" if value == "evenodd" else "nonzero"
        elif name == "font-size":
            state["font"] = self._length(value, 0.0, self._diagonal(), state)
        elif name == "transform":
            state["m"] = _mul(state["m"], _transform(value))
        elif name == "stop-color":
            state["stop_colour"] = _colour(value)
        elif name == "stop-opacity":
            state["stop_op"] = _unit_interval(value)
        elif name == "offset":
            state["stop_offset"] = self._length(value, 0.0, 1.0, state)
        elif name == "paint-order":
            state["stroke_first"] = value.split()[:1] == ["stroke"] or value.split()[:2] == ["markers", "stroke"]
        elif name == "id":
            pass
        else:
            return False
        return True

    def _own(self, element, state):
        """A copy of ``state`` with the element's attributes applied, and the rest of them by name."""
        state = dict(state, opacity=1.0)
        other = {}
        for name, value in element.attrib.items():
            if not self._attribute(state, name, value):
                other[name] = value
        return state, other

    # ---- elements ----

    def _root(self, root, state):
        if _local(root) != "svg":
            raise ValueError(_NOT_SVG)
        width = height = 0.0
        box = None
        for name, value in root.attrib.items():
            if self._attribute(state, name, value):
                continue
            if name == "width":
                width = _pixels(_coordinate(value), 0.0, 0.0, state["font"])
            elif name == "height":
                height = _pixels(_coordinate(value), 0.0, 0.0, state["font"])
            elif name == "viewBox":
                v = [float(n) for n in _NUMBER.findall(value)]
                if len(v) >= 4 and v[2] > 0 and v[3] > 0:
                    box = tuple(v[:4])
            elif name == "preserveAspectRatio":
                if "none" in value:
                    self.align = None
                else:
                    self.align = (
                        "Min" if "xMin" in value else "Max" if "xMax" in value else "Mid",
                        "Min" if "yMin" in value else "Max" if "yMax" in value else "Mid",
                        "slice" if "slice" in value else "meet",
                    )
        if box is not None:
            if width > 0 and not height > 0:
                height = width * box[3] / box[2]
            elif height > 0 and not width > 0:
                width = height * box[2] / box[3]
            elif not width > 0:
                width, height = box[2], box[3]
        if not (width > 0 and height > 0):
            raise ValueError(_NOT_SVG)
        self.size = (width, height)
        self.view = box or (0.0, 0.0, width, height)
        for child in root:
            self._element(child, state, False)

    def _element(self, element, state, in_defs):
        tag = _local(element)
        if tag in ("linearGradient", "radialGradient"):
            self._gradient(element, tag, state)
            return
        if tag == "style":
            self._sheet("".join(element.itertext()))
            return
        if in_defs:
            for child in element:
                self._element(child, state, True)
            return
        if tag == "g":
            own, _ = self._own(element, state)
            layered = own["opacity"] < 1.0
            if layered:
                self.ops.append(("layer",))
            for child in element:
                self._element(child, own, False)
            if layered:
                self.ops.append(("end", own["opacity"]))
            return
        if tag in _SHAPES:
            own, other = self._own(element, state)
            self._shape(tag, own, other)
        # Anything else is passed over, and what it holds is read as if it
        # stood here: that is what MicroPython's svgio does with it.
        for child in element:
            self._element(child, state, in_defs or tag == "defs")

    def _shape(self, tag, state, a):
        view = self.view
        diagonal = self._diagonal()

        def x(name, default=0.0):
            return self._length(a[name], view[0], view[2], state) if name in a else default

        def y(name, default=0.0):
            return self._length(a[name], view[1], view[3], state) if name in a else default

        def w(name, default=0.0):
            return self._length(a[name], 0.0, view[2], state) if name in a else default

        def h(name, default=0.0):
            return self._length(a[name], 0.0, view[3], state) if name in a else default

        if tag == "path":
            d, box = _path(a.get("d", ""))
        elif tag == "rect":
            rx = abs(w("rx")) if "rx" in a else -1.0
            ry = abs(h("ry")) if "ry" in a else -1.0
            d, box = _rect(x("x"), y("y"), w("width"), h("height"), rx, ry)
        elif tag == "circle":
            r = abs(self._length(a["r"], 0.0, diagonal, state)) if "r" in a else 0.0
            d, box = _ellipse(x("cx"), y("cy"), r, r)
        elif tag == "ellipse":
            d, box = _ellipse(x("cx"), y("cy"), abs(w("rx")), abs(h("ry")))
        elif tag == "line":
            d = _join("M", x("x1"), y("y1"), "L", x("x2"), y("y2"))
            lo = _Box()
            lo.add(x("x1"), y("y1"))
            lo.add(x("x2"), y("y2"))
            box = lo.rect()
        else:
            d, box = _poly(a.get("points", ""), tag == "polygon")
        if not d or not state["visible"]:
            return
        ops = []
        if state["fill"] is not None:
            ops.append(("fill", d, state["m"], state["rule"], self._bound(state["fill"], box, state), state["fill_op"]))
        if state["stroke"] is not None and state["width"] > 0:
            ops.append(
                ("stroke", d, state["m"], self._bound(state["stroke"], box, state), state["stroke_op"],
                 state["width"], state["cap"], state["join"], state["miter"], state["dashes"], state["dash_offset"])
            )  # fmt: skip
        if state["stroke_first"]:
            ops.reverse()
        opacity = state["opacity"]
        if opacity < 1.0 and len(ops) == 2:
            ops = [("layer",)] + ops + [("end", opacity)]
        elif opacity < 1.0 and ops:
            op = ops[0]
            at = 5 if op[0] == "fill" else 4
            ops = [op[:at] + (op[at] * opacity,) + op[at + 1 :]]
        self.ops.extend(ops)

    def _bound(self, paint, box, state):
        """A gradient reference keeps the shape's box and matrix until every gradient is read."""
        if isinstance(paint, tuple):
            return ("url", paint[1], box, state["m"])
        return paint

    # ---- gradients and style sheets ----

    def _gradient(self, element, tag, state):
        radial = tag == "radialGradient"
        if radial:
            g = {"cx": (50.0, "%"), "cy": (50.0, "%"), "r": (50.0, "%")}
        else:
            g = {"x1": (0.0, "%"), "y1": (0.0, "%"), "x2": (100.0, "%"), "y2": (0.0, "%")}
        g.update(radial=radial, box_units=True, m=_IDENTITY, spread="pad", href="", stops=[], font=state["font"])
        ident = ""
        for name, value in element.attrib.items():
            if name == "id":
                ident = value
            elif name == "gradientUnits":
                g["box_units"] = value == "objectBoundingBox"
            elif name == "gradientTransform":
                g["m"] = _transform(value)
            elif name in ("cx", "cy", "r", "fx", "fy") if radial else name in ("x1", "y1", "x2", "y2"):
                g[name] = _coordinate(value)
            elif name == "spreadMethod":
                if value in ("pad", "reflect", "repeat"):
                    g["spread"] = value
            elif name == _HREF:
                g["href"] = value[1:]
        for child in element:
            if _local(child) != "stop":
                continue
            stop = dict(state, stop_offset=0.0, stop_colour=(0, 0, 0), stop_op=1.0)
            for name, value in child.attrib.items():
                self._attribute(stop, name, value)
            offset = min(1.0, max(0.0, stop["stop_offset"]))
            at = len(g["stops"])
            for i, other in enumerate(g["stops"]):
                if offset < other[0]:
                    at = i
                    break
            g["stops"].insert(at, (offset, _css(stop["stop_colour"], stop["stop_op"])))
        self.gradients[ident] = g

    def _sheet(self, text):
        """Class rules, ``.name { ... }``, the only selectors MicroPython's svgio reads."""
        pos = 0
        while True:
            opening = text.find("{", pos)
            if opening < 0:
                break
            closing = text.find("}", opening)
            if closing < 0:
                closing = len(text)
            for selector in re.split(r"[\s,]+", text[pos:opening]):
                if selector.startswith("."):
                    self.styles.append((selector[1:], text[opening + 1 : closing]))
            pos = closing + 1

    def _resolve(self, op):
        """The op with its gradient reference made a gradient, or None when there is nothing to paint with."""
        at = 4 if op[0] == "fill" else 3 if op[0] == "stroke" else None
        if at is None or not isinstance(op[at], tuple):
            return op
        _, ident, box, matrix = op[at]
        g = self.gradients.get(ident)
        if g is None or not ident:
            return None
        stops, ref = g["stops"], g
        for _ in range(32):
            if stops:
                break
            ref = self.gradients.get(ref["href"])
            if ref is None:
                break
            stops = ref["stops"]
        if not stops:
            return None
        font = g["font"]
        if g["box_units"]:
            if box is None or not (box[2] > 0 and box[3] > 0):
                return None
            matrix = _mul(matrix, (box[2], 0.0, 0.0, box[3], box[0], box[1]))

            def along(c):
                return c[0] / 100.0 if c[1] == "%" else c[0]

            geometry = [along(g[k]) for k in (("cx", "cy", "r") if g["radial"] else ("x1", "y1", "x2", "y2"))]
            focus = [along(g[k]) if k in g else None for k in ("fx", "fy")]
        else:
            view = self.view
            if g["radial"]:
                geometry = [
                    _pixels(g["cx"], view[0], view[2], font),
                    _pixels(g["cy"], view[1], view[3], font),
                    _pixels(g["r"], 0.0, self._diagonal(), font),
                ]
            else:
                geometry = [
                    _pixels(g["x1"], view[0], view[2], font),
                    _pixels(g["y1"], view[1], view[3], font),
                    _pixels(g["x2"], view[0], view[2], font),
                    _pixels(g["y2"], view[1], view[3], font),
                ]
            focus = [
                _pixels(g["fx"], view[0], view[2], font) if "fx" in g else None,
                _pixels(g["fy"], view[1], view[3], font) if "fy" in g else None,
            ]
        last = stops[-1][1]
        if g["radial"]:
            cx, cy, r = geometry
            if not r > 0:
                paint = last
            else:
                fx = cx if focus[0] is None else focus[0]
                fy = cy if focus[1] is None else focus[1]
                # a focus outside the circle is pulled back onto it
                reach = math.hypot(fx - cx, fy - cy)
                if reach > r * 0.999:
                    fx, fy = cx + (fx - cx) * r * 0.999 / reach, cy + (fy - cy) * r * 0.999 / reach
                paint = ("radial", (cx, cy, r, fx, fy), tuple(stops), g["spread"], _mul(matrix, g["m"]))
        elif geometry[0] == geometry[2] and geometry[1] == geometry[3]:
            paint = last
        else:
            paint = ("linear", tuple(geometry), tuple(stops), g["spread"], _mul(matrix, g["m"]))
        return op[:at] + (paint,) + op[at + 1 :]


def _local(element):
    """The element's SVG name, or "" for one from another vocabulary."""
    tag = element.tag
    if not isinstance(tag, str):
        return ""
    if tag.startswith(_SVG_NS):
        return tag[len(_SVG_NS) :]
    return "" if tag.startswith("{") else tag


def _viewport(reader, zoom):
    """The matrix from the SVG's user space to output pixels."""
    width, height = reader.size
    vx, vy, vw, vh = reader.view
    sx, sy = width / vw, height / vh
    tx = ty = 0.0
    if reader.align is not None:
        how_x, how_y, fit = reader.align
        sx = sy = max(sx, sy) if fit == "slice" else min(sx, sy)
        tx = (width - vw * sx) * {"Min": 0.0, "Mid": 0.5, "Max": 1.0}[how_x]
        ty = (height - vh * sy) * {"Min": 0.0, "Mid": 0.5, "Max": 1.0}[how_y]
    return (zoom * sx, 0.0, 0.0, zoom * sy, zoom * (tx - vx * sx), zoom * (ty - vy * sy))


# --- drawing: the only part that touches the browser --------------------------


class _Painter:
    """Draws ops on an OffscreenCanvas ``width`` by ``height``, through ``view``."""

    def __init__(self, width, height, view):
        self.width, self.height, self.view = width, height, view
        self.canvas, self.ctx = self._new()
        self.scratch = None

    def _new(self):
        canvas = js.OffscreenCanvas.new(self.width, self.height)
        # read back often: the browser then draws in memory, not on the GPU
        return canvas, canvas.getContext("2d", js.JSON.parse('{"willReadFrequently": true}'))

    def draw(self, ops):
        below = []
        for op in ops:
            kind = op[0]
            if kind == "layer":
                below.append((self.canvas, self.ctx))
                self.canvas, self.ctx = self._new()
            elif kind == "end":
                top = self.canvas
                self.canvas, self.ctx = below.pop()
                self._stamp(top, op[1])
            elif kind == "fill":
                self._fill(op)
            else:
                self._stroke(op)
        return self.canvas

    def _stamp(self, canvas, alpha):
        ctx = self.ctx
        ctx.setTransform(1, 0, 0, 1, 0, 0)
        ctx.globalAlpha = alpha
        ctx.drawImage(canvas, 0, 0)

    def _fill(self, op):
        _, d, matrix, rule, paint, alpha = op
        path = js.Path2D.new(d)
        matrix = _mul(self.view, matrix)
        ctx = self.ctx if isinstance(paint, str) else self._clear()
        ctx.setTransform(*matrix)
        if isinstance(paint, str):
            ctx.globalAlpha = alpha
            ctx.fillStyle = paint
            ctx.fill(path, rule)
        else:
            ctx.fillStyle = "#000000"
            ctx.fill(path, rule)
            self._tint(paint, alpha)

    def _stroke(self, op):
        _, d, matrix, paint, alpha, width, cap, join, miter, dashes, dash_offset = op
        path = js.Path2D.new(d)
        matrix = _mul(self.view, matrix)
        ctx = self.ctx if isinstance(paint, str) else self._clear()
        ctx.setTransform(*matrix)
        ctx.lineWidth = width
        ctx.lineCap = cap
        ctx.lineJoin = join
        ctx.miterLimit = miter
        ctx.setLineDash(js.Array.of(*dashes))
        ctx.lineDashOffset = dash_offset
        if isinstance(paint, str):
            ctx.globalAlpha = alpha
            ctx.strokeStyle = paint
            ctx.stroke(path)
        else:
            ctx.strokeStyle = "#000000"
            ctx.stroke(path)
            self._tint(paint, alpha)

    def _clear(self):
        """The scratch canvas, empty: a gradient is poured into a shape drawn there first."""
        if self.scratch is None:
            self.scratch = self._new()
        ctx = self.scratch[1]
        ctx.globalCompositeOperation = "source-over"
        ctx.setTransform(1, 0, 0, 1, 0, 0)
        ctx.clearRect(0, 0, self.width, self.height)
        return ctx

    def _tint(self, paint, alpha):
        """Colour the shape on the scratch canvas with the gradient, and put it on the picture."""
        kind, geometry, stops, spread, matrix = paint
        matrix = _mul(self.view, matrix)
        inverse = _invert(matrix)
        if inverse is None:
            return
        # the picture's corners in the gradient's space: how far it must reach
        corners = [_apply(inverse, x, y) for x in (0, self.width) for y in (0, self.height)]
        ctx = self.scratch[1]
        ctx.setTransform(*matrix)
        if kind == "linear":
            x1, y1, x2, y2 = geometry
            dx, dy = x2 - x1, y2 - y1
            lo, hi = 0, 1
            if spread != "pad":
                t = [((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy) for x, y in corners]
                first, last = math.floor(min(t)), max(math.ceil(max(t)), math.floor(min(t)) + 1)
                if last - first <= _MAX_CYCLES:
                    lo, hi = first, last
            gradient = ctx.createLinearGradient(x1 + lo * dx, y1 + lo * dy, x1 + hi * dx, y1 + hi * dy)
        else:
            cx, cy, r, fx, fy = geometry
            lo, hi = 0, 1
            if spread != "pad" and (fx, fy) == (cx, cy):
                last = max(1, math.ceil(max(math.hypot(x - cx, y - cy) for x, y in corners) / r))
                if last <= _MAX_CYCLES:
                    hi = last
            gradient = ctx.createRadialGradient(fx, fy, 0, cx, cy, r * hi)
        for cycle in range(lo, hi):
            flipped = spread == "reflect" and cycle % 2
            for offset, colour in reversed(stops) if flipped else stops:
                at = (cycle - lo + (1.0 - offset if flipped else offset)) / (hi - lo)
                gradient.addColorStop(min(1.0, max(0.0, at)), colour)
        xs, ys = [c[0] for c in corners], [c[1] for c in corners]
        ctx.globalCompositeOperation = "source-in"
        ctx.fillStyle = gradient
        ctx.fillRect(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
        self._stamp(self.scratch[0], alpha)


def _rgba(canvas, width, height):
    return canvas.getContext("2d").getImageData(0, 0, width, height).data.to_bytes()


def _over(canvas, under, width, height):
    """The picture drawn over ``under``, opaque RGBA bytes, by the browser."""
    base = js.OffscreenCanvas.new(width, height)
    ctx = base.getContext("2d", js.JSON.parse('{"willReadFrequently": true}'))
    pixels = js.Uint8ClampedArray.new(width * height * 4)
    pixels.assign(under)
    ctx.putImageData(js.ImageData.new(pixels, width, height), 0, 0)
    ctx.drawImage(canvas, 0, 0)
    return ctx.getImageData(0, 0, width, height).data.to_bytes()


# --- RGBA to RGB565 and back, a whole picture at a time ------------------------


def _either(a, b):
    """Two byte strings of one length, ORed together."""
    return (int.from_bytes(a, "little") | int.from_bytes(b, "little")).to_bytes(len(a), "little")


_RED_HIGH = bytes(v & 0xF8 for v in range(256))
_GREEN_HIGH = bytes(v >> 5 for v in range(256))
_GREEN_LOW = bytes((v & 0x1C) << 3 for v in range(256))
_BLUE_LOW = bytes(v >> 3 for v in range(256))
_RED_WIDE = bytes((v & 0xF8) | (v >> 5) for v in range(256))
_GREEN_WIDE_HIGH = bytes(((v & 7) << 5) | ((v & 7) >> 1) for v in range(256))
_GREEN_WIDE_LOW = bytes((v >> 5) << 2 for v in range(256))
_BLUE_WIDE = bytes(((v & 0x1F) << 3) | ((v & 0x1F) >> 2) for v in range(256))


def _to_565(rgba):
    """RGBA bytes as native-order RGB565 bytes, truncating as the C module does."""
    r, g, b = rgba[0::4], rgba[1::4], rgba[2::4]
    out = bytearray(len(r) * 2)
    out[0::2] = _either(g.translate(_GREEN_LOW), b.translate(_BLUE_LOW))
    out[1::2] = _either(r.translate(_RED_HIGH), g.translate(_GREEN_HIGH))
    return out


def _from_565(pixels):
    """RGB565 bytes widened to opaque RGBA, each channel's top bits repeated below."""
    low, high = pixels[0::2], pixels[1::2]
    out = bytearray(b"\xff") * (len(low) * 4)
    out[0::4] = high.translate(_RED_WIDE)
    out[1::4] = _either(high.translate(_GREEN_WIDE_HIGH), low.translate(_GREEN_WIDE_LOW))
    out[2::4] = low.translate(_BLUE_WIDE)
    return out


class SvgDecoder:
    """``SvgDecoder()``: ``open(source, width=)``, then ``decode(target, alpha)``."""

    def __init__(self):
        self._reader = None
        self._size = None
        self._zoom = 1.0
        self._canvas = None

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
        self._reader = self._size = self._canvas = None
        if isinstance(source, str):
            with open(source, "rb") as f:
                data = f.read()
        elif hasattr(source, "read"):
            data = source.read()
        else:
            data = bytes(memoryview(source).cast("B"))
        try:
            data.decode("utf-8")
            reader = _Reader(ET.fromstring(data))
        except (UnicodeDecodeError, ET.ParseError):
            raise ValueError(_NOT_SVG) from None
        own = (int(reader.size[0] + 0.5), int(reader.size[1] + 0.5))
        if own[0] < 1 or own[1] < 1:
            raise ValueError(_NOT_SVG)
        if width is not None:
            zoom = width / own[0]
        elif height is not None:
            zoom = height / own[1]
        else:
            zoom = 1.0 if scale is None else float(scale)
        w, h = int(own[0] * zoom + 0.5), int(own[1] * zoom + 0.5)
        if not (zoom > 0 and 1 <= w <= _MAX and 1 <= h <= _MAX):
            raise ValueError("svgio: the size must come to 1..32767 pixels a side")
        self._reader, self._size, self._zoom = reader, (w, h), zoom
        return w, h

    def decode(self, target, alpha=None, *, x=0, y=0, stride=None):
        """RGB565 into ``target`` and coverage into ``alpha``; ``target`` alone blends."""
        if self._reader is None:
            raise RuntimeError("decode() needs a successful open()")
        if target is None and alpha is None:
            raise ValueError("give a target, an alpha buffer, or both")
        w, h = self._size
        stride = w if stride is None else stride
        if x < 0 or y < 0 or x + w > stride:
            raise ValueError("the image doesn't fit across the target at that x and stride")
        pix = memoryview(target).cast("B") if target is not None else None
        cov = memoryview(alpha).cast("B") if alpha is not None else None
        last = (y + h - 1) * stride + x + w
        if pix is not None and pix.nbytes < last * 2:
            raise ValueError("target has %d bytes; it needs %d" % (pix.nbytes, last * 2))
        if cov is not None and cov.nbytes < last:
            raise ValueError("alpha has %d bytes; it needs %d" % (cov.nbytes, last))

        if self._canvas is None:
            # drawn once: the same picture goes into every buffer after this
            view = _viewport(self._reader, self._zoom)
            self._canvas = _Painter(w, h, view).draw(self._reader.ops)
        rows = range(h)

        if cov is not None:
            rgba = _rgba(self._canvas, w, h)
            mask = rgba[3::4]
            for j in rows:
                at = (y + j) * stride + x
                cov[at : at + w] = mask[j * w : (j + 1) * w]
            if pix is not None:
                px = _to_565(rgba)
                for j in rows:
                    at = ((y + j) * stride + x) * 2
                    pix[at : at + w * 2] = px[j * w * 2 : (j + 1) * w * 2]
            return

        # Blended over what the target holds, widened to 8 bits a channel.
        under = b"".join(bytes(pix[((y + j) * stride + x) * 2 : ((y + j) * stride + x + w) * 2]) for j in rows)
        px = _to_565(_over(self._canvas, _from_565(under), w, h))
        for j in rows:
            at = ((y + j) * stride + x) * 2
            pix[at : at + w * 2] = px[j * w * 2 : (j + 1) * w * 2]
