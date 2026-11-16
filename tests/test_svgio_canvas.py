# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""svgio's Pyodide backend, without a browser.

``_svgio_canvas`` reads an SVG into fills and strokes and then draws them
with the browser's canvas. Here the browser is a stand-in that writes down
every call, so the tests can say exactly which canvas calls an SVG turns
into, and a second stand-in that holds real pixels, for the RGB565, alpha
and blending half. ``test_svgio_browser.py`` is the same module in Chromium.
"""

import importlib
import json
import struct
import sys
import unittest
import xml.etree.ElementTree as ET
from unittest import mock

import _env  # noqa: F401

import _svgio_canvas as canvas


class _Object:
    """A JavaScript object that logs each call and each property set, under its name."""

    def __init__(self, log, name):
        self.__dict__["_log"] = log
        self.__dict__["_name"] = name

    def __setattr__(self, key, value):
        self._log.append(("%s.%s =" % (self._name, key), _plain(value)))

    def __getattr__(self, key):
        def call(*args):
            self._log.append(("%s.%s" % (self._name, key),) + tuple(_plain(a) for a in args))

        return call


def _plain(value):
    return value._name if isinstance(value, (_Object, _Canvas)) else value


class _Context(_Object):
    def createLinearGradient(self, *args):
        self._log.append((self._name + ".createLinearGradient",) + args)
        return _Object(self._log, "gradient")

    def createRadialGradient(self, *args):
        self._log.append((self._name + ".createRadialGradient",) + args)
        return _Object(self._log, "gradient")


class _Canvas:
    def __init__(self, log, name):
        self._name = name
        self._context = _Context(log, name)

    def getContext(self, kind, options=None):
        return self._context


class _Class:
    def __init__(self, make):
        self.new = make


class RecordingJs:
    """The parts of the ``js`` module the backend uses, each writing to ``log``."""

    def __init__(self):
        self.log = []
        self.canvases = 0
        self.OffscreenCanvas = _Class(self._canvas)
        self.Path2D = _Class(lambda d: "Path2D(%s)" % d)
        self.JSON = mock.Mock(parse=json.loads)
        self.Array = mock.Mock(of=lambda *values: list(values))

    def _canvas(self, width, height):
        name = "canvas%d" % self.canvases
        self.canvases += 1
        self.log.append(("new", name, width, height))
        return _Canvas(self.log, name)


def calls(svg, zoom=1.0, colors=None):
    """The canvas calls that draw ``svg`` at its own size times ``zoom``, in other colours if given."""
    reader = canvas._Reader(ET.fromstring(svg))
    js = RecordingJs()
    with mock.patch.object(canvas, "js", js):
        w, h = int(reader.size[0] * zoom + 0.5), int(reader.size[1] * zoom + 0.5)
        ops = reader.ops if colors is None else canvas._recolored(reader.ops, colors)
        canvas._Painter(w, h, canvas._viewport(reader, zoom)).draw(ops)
    return js.log


def svg(body, head='width="20" height="10"'):
    return ('<svg xmlns="http://www.w3.org/2000/svg" %s>%s</svg>' % (head, body)).encode()


class CanvasCalls(unittest.TestCase):
    def test_a_filled_rect_is_one_path_filled(self):
        self.assertEqual(
            calls(svg('<rect x="2" y="1" width="6" height="4" fill="#ff8000"/>')),
            [
                ("new", "canvas0", 20, 10),
                ("canvas0.setTransform", 1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
                ("canvas0.globalAlpha =", 1.0),
                ("canvas0.fillStyle =", "#ff8000"),
                ("canvas0.fill", "Path2D(M 2 1 L 8 1 L 8 5 L 2 5 Z)", "nonzero"),
            ],
        )

    def test_width_scales_through_the_view_box_and_the_group_s_transform(self):
        log = calls(
            svg('<g transform="translate(5 0)"><circle cx="1" cy="2" r="1" fill="red"/></g>',
                'width="20" height="10" viewBox="0 0 10 5"'),
            zoom=3.0,
        )  # fmt: skip
        self.assertEqual(log[0], ("new", "canvas0", 60, 30))
        # 20/10 from the viewBox, times 3, and the group's 5 units become 30 pixels
        self.assertEqual(log[1], ("canvas0.setTransform", 6.0, 0.0, 0.0, 6.0, 30.0, 0.0))
        self.assertEqual(log[-1], ("canvas0.fill", "Path2D(M 2 2 A 1 1 0 1 1 0 2 A 1 1 0 1 1 2 2 Z)", "nonzero"))

    def test_a_stroke_carries_its_width_cap_join_dashes_and_opacity(self):
        log = calls(
            svg('<polyline points="1,1 5,5 9,1" fill="none" stroke="#102030" stroke-width="2" '
                'stroke-linecap="round" stroke-linejoin="bevel" stroke-miterlimit="3" '
                'stroke-dasharray="4 1" stroke-dashoffset="2" stroke-opacity="0.5"/>')
        )  # fmt: skip
        self.assertEqual(
            log[1:],
            [
                ("canvas0.setTransform", 1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
                ("canvas0.lineWidth =", 2.0),
                ("canvas0.lineCap =", "round"),
                ("canvas0.lineJoin =", "bevel"),
                ("canvas0.miterLimit =", 3.0),
                ("canvas0.setLineDash", [4.0, 1.0]),
                ("canvas0.lineDashOffset =", 2.0),
                ("canvas0.globalAlpha =", 0.5),
                ("canvas0.strokeStyle =", "#102030"),
                ("canvas0.stroke", "Path2D(M 1 1 L 5 5 L 9 1)"),
            ],
        )

    def test_fill_then_stroke_and_even_odd(self):
        log = calls(svg('<path d="M1 1h8v8h-8z" fill="blue" stroke="black" fill-rule="evenodd"/>'))
        drawn = [c for c in log if c[0] in ("canvas0.fill", "canvas0.stroke")]
        self.assertEqual(
            drawn,
            [("canvas0.fill", "Path2D(M 1 1 L 9 1 L 9 9 L 1 9 Z)", "evenodd"),
             ("canvas0.stroke", "Path2D(M 1 1 L 9 1 L 9 9 L 1 9 Z)")],
        )  # fmt: skip

    def test_one_paint_takes_the_opacity_and_two_share_a_layer(self):
        one = calls(svg('<rect width="4" height="4" fill="red" fill-opacity="0.5" opacity="0.5"/>'))
        self.assertIn(("canvas0.globalAlpha =", 0.25), one)
        self.assertEqual([c for c in one if c[0] == "new"], [("new", "canvas0", 20, 10)])
        two = calls(svg('<g opacity="0.5"><rect width="4" height="4"/><rect x="2" width="4" height="4"/></g>'))
        self.assertEqual([c[1] for c in two if c[0] == "new"], ["canvas0", "canvas1"])
        self.assertEqual([c[0] for c in two if c[0].endswith(".fill")], ["canvas1.fill", "canvas1.fill"])
        self.assertEqual(
            two[-3:],
            [("canvas0.setTransform", 1, 0, 0, 1, 0, 0), ("canvas0.globalAlpha =", 0.5),
             ("canvas0.drawImage", "canvas1", 0, 0)],
        )  # fmt: skip

    def test_a_gradient_in_the_shape_s_box_is_poured_into_the_shape(self):
        log = calls(
            svg('<linearGradient id="g"><stop offset="0" stop-color="#ff0000"/>'
                '<stop offset="1" stop-color="#0000ff" stop-opacity="0.5"/></linearGradient>'
                '<rect x="2" y="1" width="10" height="5" fill="url(#g)"/>')
        )  # fmt: skip
        self.assertEqual(
            log,
            [
                ("new", "canvas0", 20, 10),
                ("new", "canvas1", 20, 10),
                ("canvas1.globalCompositeOperation =", "source-over"),
                ("canvas1.setTransform", 1, 0, 0, 1, 0, 0),
                ("canvas1.clearRect", 0, 0, 20, 10),
                ("canvas1.setTransform", 1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
                ("canvas1.fillStyle =", "#000000"),
                ("canvas1.fill", "Path2D(M 2 1 L 12 1 L 12 6 L 2 6 Z)", "nonzero"),
                # the box, 10 by 5 at (2, 1), is the gradient's unit square
                ("canvas1.setTransform", 10.0, 0.0, 0.0, 5.0, 2.0, 1.0),
                ("canvas1.createLinearGradient", 0.0, 0.0, 1.0, 0.0),
                ("gradient.addColorStop", 0.0, "#ff0000"),
                ("gradient.addColorStop", 1.0, "rgba(0,0,255,0.5)"),
                ("canvas1.globalCompositeOperation =", "source-in"),
                ("canvas1.fillStyle =", "gradient"),
                ("canvas1.fillRect", -0.2, -0.2, 2.0, 2.0),
                ("canvas0.setTransform", 1, 0, 0, 1, 0, 0),
                ("canvas0.globalAlpha =", 1.0),
                ("canvas0.drawImage", "canvas1", 0, 0),
            ],
        )

    def test_a_user_space_radial_gradient_with_a_transform_and_a_focus(self):
        log = calls(
            svg('<radialGradient id="r" gradientUnits="userSpaceOnUse" cx="10" cy="5" r="4" fx="9" fy="5" '
                'gradientTransform="translate(1 0)"><stop offset="0" stop-color="white"/>'
                '<stop offset="100%" stop-color="black"/></radialGradient>'
                '<circle cx="10" cy="5" r="4" stroke="url(#r)" fill="none"/>')
        )  # fmt: skip
        self.assertIn(("canvas1.setTransform", 1.0, 0.0, 0.0, 1.0, 1.0, 0.0), log)
        self.assertIn(("canvas1.createRadialGradient", 9.0, 5.0, 0, 10.0, 5.0, 4.0), log)
        self.assertIn(("canvas1.stroke", "Path2D(M 14 5 A 4 4 0 1 1 6 5 A 4 4 0 1 1 14 5 Z)"), log)

    def test_a_reflected_gradient_repeats_its_stops_across_the_picture(self):
        log = calls(
            svg('<linearGradient id="g" gradientUnits="userSpaceOnUse" x1="0" x2="10" spreadMethod="reflect">'
                '<stop offset="0" stop-color="black"/><stop offset="1" stop-color="white"/></linearGradient>'
                '<rect width="20" height="10" fill="url(#g)"/>')
        )  # fmt: skip
        self.assertIn(("canvas1.createLinearGradient", 0.0, 0.0, 20.0, 0.0), log)
        self.assertEqual(
            [c[1:] for c in log if c[0] == "gradient.addColorStop"],
            [(0.0, "#000000"), (0.5, "#ffffff"), (0.5, "#ffffff"), (1.0, "#000000")],
        )


    def test_colors_swaps_fills_strokes_and_stops_and_keeps_their_opacity(self):
        picture = svg(
            '<linearGradient id="g"><stop offset="0" stop-color="#ff0000"/>'
            '<stop offset="1" stop-color="rgb(0, 0, 255)" stop-opacity="0.5"/></linearGradient>'
            '<rect width="4" height="4" fill="red" stroke="#00f" fill-opacity="0.5"/>'
            '<rect x="6" width="4" height="4" fill="url(#g)"/><rect y="6" width="4" height="4" fill="#00ff00"/>'
        )
        log = calls(picture, colors={0xFF0000: 0x102030, 0x0000FF: 0xA0B0C0, 0x123456: 0})
        styles = [c[1] for c in log if c[0].endswith(("fillStyle =", "strokeStyle =")) and c[1] not in ("#000000", "gradient")]
        self.assertEqual(styles, ["#102030", "#a0b0c0", "#00ff00"])
        self.assertIn(("canvas0.globalAlpha =", 0.5), log)
        self.assertEqual(
            [c[1:] for c in log if c[0] == "gradient.addColorStop"],
            [(0.0, "#102030"), (1.0, "rgba(160,176,192,0.5)")],
        )
        self.assertEqual(calls(picture, colors={}), calls(picture))


class Reading(unittest.TestCase):
    def ops(self, body, head='width="20" height="10"'):
        return canvas._Reader(ET.fromstring(svg(body, head))).ops

    def test_sizes(self):
        def size(head):
            reader = canvas._Reader(ET.fromstring(svg("", head)))
            return reader.size, reader.view

        self.assertEqual(size('width="20" height="10"'), ((20.0, 10.0), (0.0, 0.0, 20.0, 10.0)))
        self.assertEqual(size('viewBox="0 0 30 20"'), ((30.0, 20.0), (0.0, 0.0, 30.0, 20.0)))
        self.assertEqual(size('width="60" viewBox="0 0 30 20"')[0], (60.0, 40.0))
        self.assertEqual(size('width="1in" height="72pt"')[0], (96.0, 96.0))
        self.assertEqual(size('width="100%" height="100%" viewBox="1 2 30 20"')[0], (30.0, 20.0))
        for head in ("", 'width="20"', 'width="0" height="0"'):
            with self.assertRaises(ValueError):
                size(head)
        with self.assertRaises(ValueError):
            canvas._Reader(ET.fromstring(b'<rect xmlns="http://www.w3.org/2000/svg" width="4" height="4"/>'))

    def test_colours_are_the_ones_micropython_s_svgio_reads(self):
        for text, rgb in (
            ("#1e88e5", (0x1E, 0x88, 0xE5)),
            ("#fa0", (0xFF, 0xAA, 0x00)),
            ("rgb(1, 2, 300)", (1, 2, 255)),
            ("rgb(100%, 50%, 0%)", (255, 128, 0)),
            ("white", (255, 255, 255)),
            ("green", (0, 128, 0)),
            ("tomato", (128, 128, 128)),
            ("currentColor", (128, 128, 128)),
            ("#zz", (128, 128, 128)),
            ("#12345678", (0x12, 0x34, 0x56)),
            ("#abcd", (0xAA, 0xBB, 0xCC)),
            ("Red", (128, 128, 128)),
        ):
            self.assertEqual(canvas._colour(text), rgb, text)

    def test_paths_become_absolute(self):
        for d, want in (
            ("M1 2l3 4h5v-6z", "M 1 2 L 4 6 L 9 6 L 9 0 Z"),
            ("m1,2 3,4 5,6", "M 1 2 L 4 6 L 9 12"),
            ("M0 0C1 2 3 4 5 6s3 4 5 6", "M 0 0 C 1 2 3 4 5 6 C 7 8 8 10 10 12"),
            ("M0 0Q2 4 4 0T8 0", "M 0 0 Q 2 4 4 0 Q 6 -4 8 0"),
            ("M2 8.8a15 15 0 0 1 20 0", "M 2 8.8 A 15 15 0 0 1 22 8.8"),
            ("M0 0a5 5 0 1010 0", "M 0 0 A 5 5 0 1 0 10 0"),
            ("M1 1L5 5 oops 9 9", "M 1 1 L 5 5"),
            ("L5 5", ""),
        ):
            self.assertEqual(canvas._path(d)[0], want, d)

    def test_a_path_s_box_follows_its_curves(self):
        box = canvas._path("M0 0 C 0 10 10 10 10 0")[1]
        self.assertEqual(box[:3], (0.0, 0.0, 10.0))
        self.assertAlmostEqual(box[3], 7.5)
        x, y, w, h = canvas._path("M0 5 A5 5 0 0 1 10 5")[1]
        self.assertEqual((x, w), (0.0, 10.0))
        self.assertAlmostEqual(y, 0.0)
        self.assertAlmostEqual(h, 5.0)

    def test_transforms(self):
        self.assertEqual(canvas._transform("translate(3) scale(2 4)"), (2.0, 0.0, 0.0, 4.0, 3.0, 0.0))
        m = canvas._transform("rotate(90 5 5)")
        self.assertEqual([round(v, 6) for v in m], [0, 1, -1, 0, 10, 0])
        self.assertEqual(canvas._transform("matrix(1 2 3 4 5 6)"), (1.0, 2.0, 3.0, 4.0, 5.0, 6.0))

    def test_styles_classes_and_inheritance(self):
        ops = self.ops(
            '<style>.a { fill: #010203 } .b, .c { stroke: #040506; stroke-width: 3 }</style>'
            '<g fill="#0a0b0c"><rect class="a b" width="4" height="4"/>'
            '<rect width="4" height="4" style="fill:#111213"/><rect width="4" height="4"/></g>'
        )
        self.assertEqual([op[0] for op in ops], ["fill", "stroke", "fill", "fill"])
        self.assertEqual((ops[0][4], ops[1][3], ops[1][5]), ("#010203", "#040506", 3.0))
        self.assertEqual((ops[2][4], ops[3][4]), ("#111213", "#0a0b0c"))

    def test_what_isn_t_read_is_left_out(self):
        ops = self.ops(
            '<defs><rect width="4" height="4"/></defs><text x="1" y="1">hi</text>'
            '<use href="#x"/><image href="a.png" width="4" height="4"/>'
            '<g display="none"><rect width="4" height="4"/></g>'
            '<rect width="4" height="4" fill="none"/><rect width="4" height="4" fill="url(#missing)"/>'
            '<circle r="0"/><rect width="4" height="4" stroke="red" stroke-width="0" fill="none"/>'
        )
        self.assertEqual(ops, [])

    def test_a_shape_inside_an_element_it_doesn_t_know_is_drawn_as_micropython_draws_it(self):
        ops = self.ops('<clipPath id="c" fill="red"><rect width="4" height="4"/></clipPath>')
        self.assertEqual([(op[0], op[4]) for op in ops], [("fill", "#000000")])

    def test_a_gradient_takes_its_stops_from_the_one_it_names(self):
        head = 'width="20" height="10" xmlns:xlink="http://www.w3.org/1999/xlink"'
        ops = self.ops(
            '<rect width="4" height="4" fill="url(#b)"/>'
            '<linearGradient id="a"><stop offset="0.2" stop-color="red"/><stop offset="0.1" stop-color="blue"/>'
            '</linearGradient><linearGradient id="b" xlink:href="#a" x2="0" y2="1"/>',
            head,
        )
        kind, geometry, stops, spread, matrix = ops[0][4]
        self.assertEqual((kind, geometry, spread), ("linear", (0.0, 0.0, 0.0, 1.0), "pad"))
        self.assertEqual(stops, ((0.1, "#0000ff"), (0.2, "#ff0000")))
        self.assertEqual(matrix, (4.0, 0.0, 0.0, 4.0, 0.0, 0.0))


def _naive_565(rgba):
    out = bytearray()
    for i in range(0, len(rgba), 4):
        r, g, b = rgba[i : i + 3]
        v = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        out += bytes((v & 0xFF, v >> 8))
    return out


class Pixels(unittest.TestCase):
    def test_rgb565_and_back(self):
        rgba = bytes((i * 7) & 0xFF for i in range(4 * 1024))
        self.assertEqual(canvas._to_565(rgba), _naive_565(rgba))
        every = b"".join(v.to_bytes(2, "little") for v in range(0, 65536, 7))
        wide = canvas._from_565(every)
        self.assertEqual(wide[3::4], b"\xff" * (len(every) // 2))
        self.assertEqual(canvas._to_565(bytes(wide)), every)
        self.assertEqual(bytes(canvas._from_565(b"\xff\xff\x00\x00\x00\xf8")), b"\xff\xff\xff\xff\x00\x00\x00\xff\xff\x00\x00\xff")


class PaintedJs:
    """A ``js`` whose canvases hold one fixed picture, to follow the pixels out of ``decode()``.

    The picture is 4 by 2: an opaque red row, then a clear pixel, a half
    covered green one and two opaque blue ones.
    """

    PICTURE = bytes(
        (255, 0, 0, 255) * 4
        + (0, 0, 0, 0) + (0, 255, 0, 128) + (0, 0, 255, 255) * 2
    )  # fmt: skip

    def __init__(self):
        outer = self
        self.canvases = 0

        class Data:
            def __init__(self, pixels):
                self.pixels = bytearray(pixels)

            def assign(self, source):
                self.pixels[:] = source

            def to_bytes(self):
                return bytes(self.pixels)

        class Context:
            def __init__(self, pixels):
                self.pixels = pixels

            def __getattr__(self, name):
                return lambda *args: None

            def getImageData(self, x, y, w, h):
                return mock.Mock(data=Data(self.pixels))

            def putImageData(self, image, x, y):
                self.pixels[:] = image.data.pixels

            def drawImage(self, other, x, y):
                top = other.context.pixels[-y * 16 :]  # the picture is 4 wide: 16 bytes a row
                for i in range(0, len(self.pixels), 4):
                    a = top[i + 3]
                    for c in range(3):
                        self.pixels[i + c] = (top[i + c] * a + self.pixels[i + c] * (255 - a) + 127) // 255

        class Canvas:
            def __init__(self, w, h):
                outer.canvases += 1
                self.context = Context(bytearray(outer.PICTURE[: w * h * 4]))

            def getContext(self, kind, options=None):
                return self.context

        self.OffscreenCanvas = _Class(Canvas)
        self.Path2D = _Class(lambda d: d)
        self.JSON = mock.Mock(parse=json.loads)
        self.Array = mock.Mock(of=lambda *values: list(values))
        self.Uint8ClampedArray = _Class(lambda n: Data(bytes(n)))
        self.ImageData = _Class(lambda data, w, h: mock.Mock(data=data))


def px(buf, i):
    return buf[2 * i] | buf[2 * i + 1] << 8


class Decode(unittest.TestCase):
    ICON = svg('<rect width="4" height="2"/>', 'width="4" height="2"')

    def setUp(self):
        self.js = PaintedJs()
        patch = mock.patch.object(canvas, "js", self.js)
        patch.start()
        self.addCleanup(patch.stop)
        self.d = canvas.SvgDecoder()

    def test_sizes(self):
        d = self.d
        self.assertEqual(d.open(self.ICON), (4, 2))
        self.assertEqual((d.width, d.height), (4, 2))
        self.assertEqual(d.open(self.ICON, width=8), (8, 4))
        self.assertEqual(d.open(self.ICON, height=1), (2, 1))
        self.assertEqual(d.open(self.ICON, scale=1.5), (6, 3))
        with self.assertRaises(ValueError):
            d.open(self.ICON, width=4, height=4)
        with self.assertRaises(ValueError):
            d.open(b"hello, not an svg")
        with self.assertRaises(RuntimeError):
            d.width

    def test_colour_alpha_and_mask(self):
        d = self.d
        w, h = d.open(self.ICON)
        pixels, alpha = bytearray(w * h * 2), bytearray(w * h)
        d.decode(pixels, alpha)
        self.assertEqual(bytes(alpha), bytes((255, 255, 255, 255, 0, 128, 255, 255)))
        self.assertEqual([px(pixels, i) for i in (0, 4, 5, 6)], [0xF800, 0x0000, 0x07E0, 0x001F])
        mask = bytearray(w * h)
        d.decode(None, mask)
        self.assertEqual(mask, alpha)

    def test_blended_and_placed(self):
        d = self.d
        w, h = d.open(self.ICON)
        sw, sh, x, y = 7, 4, 2, 1
        screen = bytearray(b"\x1f\x00" * (sw * sh))  # blue
        d.decode(screen, x=x, y=y, stride=sw)
        rows = [[px(screen, r * sw + c) for c in range(sw)] for r in range(sh)]
        blue = 0x001F
        self.assertEqual(rows[0], [blue] * sw)
        self.assertEqual(rows[1], [blue, blue, 0xF800, 0xF800, 0xF800, 0xF800, blue])
        # clear leaves the blue, half green over blue is half of each
        self.assertEqual(rows[2], [blue, blue, blue, 0x040F, blue, blue, blue])
        self.assertEqual(rows[3], [blue] * sw)

    def test_bands_are_the_whole_picture(self):
        d = self.d
        w, h = d.open(self.ICON)
        whole_p, whole_a = bytearray(w * h * 2), bytearray(w * h)
        d.decode(whole_p, whole_a)
        band_p, band_a = bytearray(w * h * 2), bytearray(w * h)
        blend_whole, blend_bands = bytearray(b"\x1f\x00" * (w * h)), bytearray(b"\x1f\x00" * (w * h))
        d.decode(blend_whole)
        for y0, y1 in ((0, 1), (1, 1), (1, h)):
            d.decode(band_p, band_a, rows=(y0, y1))
            d.decode(blend_bands, rows=(y0, y1))
        self.assertEqual((band_p, band_a), (whole_p, whole_a))
        self.assertEqual(blend_bands, blend_whole)
        d.decode(bytearray(w * 1 * 2), rows=(0, 1))  # a target only as tall as the rows
        for bad in ((2, 1), (0, h + 1), (1,)):
            with self.assertRaises(ValueError):
                d.decode(whole_p, rows=bad)

    def test_memory_is_accepted(self):
        d = canvas.SvgDecoder(memory=64 * 1024 + 3)
        self.assertEqual((d.memory, d.memory_peak, self.d.memory), (64 * 1024, 0, 0))
        with self.assertRaises(ValueError):
            canvas.SvgDecoder(memory=100)

    def test_a_compact_drawing_opens(self):
        drawing = b"\x01SVG\x04" + struct.pack("<B4f", 10, 0, 0, 4, 2) + b"\x0d\x0e"
        self.assertEqual(self.d.open(drawing, width=8), (8, 4))
        with self.assertRaises(ValueError):
            self.d.open(b"\x01SVG\x02")

    def test_colors_is_checked_and_draws_the_picture_again_only_when_it_changes(self):
        d = self.d
        w, h = d.open(self.ICON)
        pixels, alpha = bytearray(w * h * 2), bytearray(w * h)
        d.decode(pixels, alpha)
        d.decode(pixels, alpha)
        d.decode(pixels, alpha, colors={})
        self.assertEqual(self.js.canvases, 1)
        for rows in ((0, 1), (1, 2)):
            d.decode(pixels, alpha, rows=rows, colors={0: 0xFF0000})
        self.assertEqual(self.js.canvases, 2)
        d.decode(pixels, alpha)
        self.assertEqual(self.js.canvases, 3)
        with self.assertRaisesRegex(TypeError, "colors is a dict"):
            d.decode(pixels, colors=[(1, 2)])
        with self.assertRaisesRegex(ValueError, "colors is a dict"):
            d.decode(pixels, colors={0x1000000: 0})
        with self.assertRaisesRegex(ValueError, "colors is a dict"):
            d.decode(pixels, colors={0: -1}, rows=(0, 0))

    def test_buffer_and_close(self):
        w, h = self.d.open(self.ICON)
        buf = canvas.Buffer(w * h * 3)
        view = memoryview(buf)
        self.d.decode(view[: w * h * 2], view[w * h * 2 :])
        self.assertEqual((len(buf), px(buf, 0), buf[w * h * 2]), (w * h * 3, 0xF800, 255))
        buf.close()  # a memoryview still shows it
        self.assertEqual(len(buf), w * h * 3)
        view = None
        buf.close()
        self.assertEqual(len(buf), 0)
        with self.assertRaises(ValueError):
            canvas.Buffer(0)
        d = canvas.SvgDecoder(memory=8192)
        d.open(self.ICON)
        d.close()
        self.assertEqual(d.memory, 0)
        with self.assertRaises(RuntimeError):
            d.decode(bytearray(w * h * 2))
        with self.assertRaises(RuntimeError):
            d.width

    def test_errors(self):
        with self.assertRaisesRegex(RuntimeError, "needs a successful open"):
            canvas.SvgDecoder().decode(bytearray(4))
        self.d.open(self.ICON)
        with self.assertRaisesRegex(ValueError, "give a target"):
            self.d.decode(None)
        with self.assertRaisesRegex(ValueError, "target has 10 bytes; it needs 16"):
            self.d.decode(bytearray(10))
        with self.assertRaisesRegex(ValueError, "alpha has 3 bytes; it needs 8"):
            self.d.decode(None, bytearray(3))
        with self.assertRaisesRegex(ValueError, "doesn't fit across"):
            self.d.decode(bytearray(64), x=2, stride=4)


class WhichBackend(unittest.TestCase):
    def test_svgio_is_the_canvas_backend_under_pyodide(self):
        saved = sys.modules.pop("svgio", None)
        try:
            with mock.patch.object(sys, "platform", "emscripten"):
                svgio = importlib.import_module("svgio")
                self.assertIs(svgio.SvgDecoder, canvas.SvgDecoder)
                self.assertIs(svgio.expand, canvas.expand)
                self.assertIs(svgio.Buffer, canvas.Buffer)
        finally:
            sys.modules.pop("svgio", None)
            if saved is not None:
                sys.modules["svgio"] = saved


if __name__ == "__main__":
    unittest.main()
