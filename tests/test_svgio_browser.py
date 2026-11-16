# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""``svgio`` under Pyodide, in Chromium, beside the desktop's ``svgio``.

A page loads Pyodide, puts the checkout's ``utils/svgio.py`` and its two
backends in its file system, and decodes each SVG in ``CASES`` three ways:
colour and alpha, alpha alone, and blended over a grey screen at an offset.
The same SVGs go through the desktop backend here, and the two sets of
pixels are compared. Edges differ a little, because two different
rasterisers drew them, so each case has a share of pixels it may differ by.
Everything runs twice, on the page's main thread and in a worker, and every
call into Python is synchronous.

Needs Playwright with Chromium, resvg-py and Pillow, and Pyodide: the folder
named by ``PYDEVICES_PYODIDE_DIR`` (one holding ``pyodide.mjs``), or else
the jsDelivr copy, over the network. Without them the skip is loud, and
``PYDEVICES_REQUIRE_BROWSER=1`` turns it into a failure.

    PYDEVICES_PYODIDE_DIR=~/pyodide python -m unittest discover -s tests -p "test_svgio_browser.py"

``PYDEVICES_SVGIO_OUT=<folder>`` also writes each case as a PNG, desktop on
the left, browser in the middle and where they differ on the right.
"""

import base64
import functools
import http.server
import json
import os
import sys
import threading
import unittest
from pathlib import Path

import _env  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
PYODIDE_CDN = "https://cdn.jsdelivr.net/pyodide/v314.0.0/full/"
MODULES = ("svgio.py", "_svgio_canvas.py", "_svgio_colour.py", "_svgio_compact.py", "_svgio_resvg.py")
BACKGROUND = 0x8410  # the grey each case is also blended over
MARGIN = (5, 3, 8, 6)  # x, y, extra columns, extra rows of the screen it is blended into
TOLERANCE = 16  # of 255: two steps of a five-bit channel


def _svg(body, size='width="48" height="48" viewBox="0 0 48 48"', more=""):
    return '<svg xmlns="http://www.w3.org/2000/svg" %s %s>%s</svg>' % (size, more, body)


# (name, SVG text, open() keywords, the share of pixels that may differ)
CASES = (
    ("rect", _svg('<rect x="2" y="2" width="20" height="8" fill="#ff0000"/>', 'width="24" height="12"'), {}, 0.0),
    ("rect-wide", _svg('<rect x="2" y="2" width="20" height="8" fill="#ff0000"/>',
                       'width="24" height="12" viewBox="0 0 24 12"'), {"width": 96}, 0.0),
    ("circle", _svg('<circle cx="24" cy="24" r="18" fill="#e53935"/>'), {}, 0.02),
    ("ellipse-polygon", _svg(
        '<ellipse cx="24" cy="14" rx="20" ry="9" fill="#00897b"/>'
        '<polygon points="24,22 4,44 16,44 16,34 32,34 32,44 44,44" fill="#6d4c41"/>'), {"width": 96}, 0.02),
    ("rounded-rect", _svg('<rect x="4" y="8" width="40" height="30" rx="8" ry="5" fill="#43a047"/>'
                          '<rect x="12" y="16" width="24" height="14" rx="30" fill="#ffffff"/>'), {}, 0.02),
    ("path-curves", _svg('<path d="M4 40 C 12 4, 36 4, 44 40 Z" fill="#fb8c00"/>'
                         '<path d="M8 44 Q 24 20 40 44 T 44 8" fill="none" stroke="#3e2723" stroke-width="3"/>'
                         '<path d="M6 6h10v10h-10zm20 0 10 0 0 10-10 0z" fill="#3949ab"/>'), {"width": 96}, 0.03),
    ("path-arcs", _svg('<path d="M10.3 2h3.4l.5 2.6a8 8 0 0 1 2 1.2l2.5-.9 1.7 2.9-2 1.7a8 8 0 0 1 0 2.4l2 1.7-1.7 '
                       '2.9-2.5-.9a8 8 0 0 1-2 1.2l-.5 2.6h-3.4l-.5-2.6a8 8 0 0 1-2-1.2l-2.5.9-1.7-2.9 2-1.7a8 8 0 0 '
                       '1 0-2.4l-2-1.7 1.7-2.9 2.5.9a8 8 0 0 1 2-1.2zM12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 1 0 0-7z" '
                       'fill="#546e7a" fill-rule="evenodd"/>', 'width="24" height="24" viewBox="0 0 24 24"'),
     {"width": 96}, 0.03),
    ("stroke-caps-joins", _svg(
        '<polyline points="6,14 16,6 26,14 36,6 42,14" fill="none" stroke="#00acc1" stroke-width="4" '
        'stroke-linejoin="round" stroke-linecap="round"/>'
        '<polyline points="6,28 16,20 26,28 36,20 42,28" fill="none" stroke="#8e24aa" stroke-width="4" '
        'stroke-linejoin="bevel" stroke-linecap="square"/>'
        '<polyline points="6,42 16,34 26,42 36,34 42,42" fill="none" stroke="#424242" stroke-width="4"/>'),
     {"width": 96}, 0.04),
    ("stroke-dashes", _svg('<line x1="4" y1="10" x2="44" y2="10" stroke="#000000" stroke-width="4" '
                           'stroke-dasharray="6 3"/>'
                           '<circle cx="24" cy="30" r="12" fill="none" stroke="#d81b60" stroke-width="3" '
                           'stroke-dasharray="5,2,1,2" stroke-dashoffset="3"/>'), {"width": 96}, 0.04),
    ("inherited-stroke", _svg(
        '<path d="M2 8.8a15 15 0 0 1 20 0"/><path d="M5 12.6a10 10 0 0 1 14 0"/>'
        '<path d="M8.5 16.4a5 5 0 0 1 7 0"/><circle cx="12" cy="20" r="1" fill="#1e88e5"/>',
        'width="24" height="24" viewBox="0 0 24 24"',
        'fill="none" stroke="#1e88e5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"'),
     {"width": 96}, 0.04),
    ("transform", _svg('<g transform="translate(24 24) rotate(30)"><rect x="-16" y="-5" width="32" height="10" '
                       'fill="#8e24aa"/><g transform="scale(0.5)"><ellipse cx="0" cy="0" rx="12" ry="40" '
                       'fill="#fdd835"/></g></g>'
                       '<rect width="8" height="8" fill="#000" transform="matrix(1 0 0 -1 2 46) skewX(20)"/>'),
     {"width": 96}, 0.04),
    ("opacity", _svg('<rect x="2" y="2" width="26" height="26" fill="#d81b60"/>'
                     '<circle cx="30" cy="20" r="14" fill="#3949ab" fill-opacity="0.5"/>'
                     '<line x1="2" y1="40" x2="46" y2="40" stroke="#000000" stroke-width="4" stroke-opacity="0.75"/>'
                     '<rect x="34" y="30" width="12" height="16" fill="#00ff00" opacity="0.25"/>'), {}, 0.03),
    ("group-opacity", _svg('<g opacity="0.5"><rect x="4" y="4" width="28" height="28" fill="#ff0000"/>'
                           '<rect x="16" y="16" width="28" height="28" fill="#0000ff"/></g>'
                           '<circle cx="36" cy="12" r="8" fill="#fdd835" stroke="#000" stroke-width="4" '
                           'opacity="0.5"/>'), {}, 0.03),
    ("linear-gradient", _svg(
        '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#ff0000"/>'
        '<stop offset="0.5" stop-color="#ffff00"/><stop offset="1" stop-color="#0000ff"/></linearGradient></defs>'
        '<rect x="2" y="2" width="60" height="28" rx="6" fill="url(#g)"/>', 'width="64" height="32"'),
     {"width": 128}, 0.03),
    ("radial-gradient", _svg(
        '<defs><radialGradient id="r" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="#ffffff"/>'
        '<stop offset="1" stop-color="#00897b"/></radialGradient></defs>'
        '<circle cx="24" cy="24" r="22" fill="url(#r)"/>'), {"width": 96}, 0.03),
    ("gradient-user-space", _svg(
        '<linearGradient id="a" gradientUnits="userSpaceOnUse" x1="4" y1="4" x2="44" y2="44" '
        'gradientTransform="rotate(20 24 24)"><stop offset="10%" stop-color="#1e88e5"/>'
        '<stop offset="90%" stop-color="#fdd835" stop-opacity="0.4"/></linearGradient>'
        '<radialGradient id="b" gradientUnits="userSpaceOnUse" cx="34" cy="34" r="12" fx="30" fy="30">'
        '<stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#e53935"/></radialGradient>'
        '<rect x="4" y="4" width="40" height="40" fill="url(#a)"/>'
        '<circle cx="34" cy="34" r="12" fill="url(#b)"/>'), {"width": 96}, 0.04),
    ("gradient-stroke", _svg(
        '<linearGradient id="band" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#43a047"/>'
        '<stop offset="0.6" stop-color="#fdd835"/><stop offset="1" stop-color="#e53935"/></linearGradient>'
        '<path d="M6 40 A18 18 0 0 1 42 40" fill="none" stroke="url(#band)" stroke-width="6"/>'
        '<ellipse cx="24" cy="12" rx="20" ry="8" fill="url(#band)" fill-opacity="0.6"/>'), {"width": 96}, 0.05),
    ("gradient-spread", _svg(
        '<linearGradient id="p" x1="0.4" x2="0.6" spreadMethod="reflect"><stop offset="0" stop-color="#000"/>'
        '<stop offset="1" stop-color="#fff"/></linearGradient>'
        '<radialGradient id="q" r="0.2" spreadMethod="repeat"><stop offset="0" stop-color="#3949ab"/>'
        '<stop offset="1" stop-color="#fdd835"/></radialGradient>'
        '<linearGradient id="s" xlink:href="#p" x1="0" x2="1"/>'
        '<rect x="2" y="2" width="44" height="12" fill="url(#p)"/>'
        '<rect x="2" y="16" width="44" height="18" fill="url(#q)"/>'
        '<rect x="2" y="36" width="44" height="10" fill="url(#s)"/>',
        more='xmlns:xlink="http://www.w3.org/1999/xlink"'), {"width": 96}, 0.08),
    ("style-sheet", _svg(
        '<style>.a, .b { fill: #1e88e5; } .b { stroke: #000000; stroke-width: 2 }</style>'
        '<rect class="a" x="4" y="4" width="18" height="18"/><rect class="b" x="26" y="26" width="18" height="18"/>'
        '<circle cx="34" cy="12" r="8" style="fill:#fdd835;stroke:#e53935;stroke-width:3"/>'), {}, 0.03),
    ("view-box-fit", _svg('<rect width="10" height="10" fill="#43a047"/><circle cx="5" cy="5" r="4" fill="#fff"/>',
                          'width="40" height="20" viewBox="0 0 10 10"'), {"scale": 2.0}, 0.03),
    ("height-and-units", _svg('<rect x="10%" y="10%" width="80%" height="80%" fill="#fb8c00"/>',
                              'viewBox="0 0 30 20"'), {"height": 50}, 0.03),
)

def _compact():
    """A drawing in svgio's compact form: a red rect, and a green stroke in a moved group."""
    import struct

    return b"".join(
        (
            b"\x01SVG\x04",
            struct.pack("<B4f", 10, 0, 0, 24, 12),
            b"\x0d",
            struct.pack("<B5fII2fH", 3, 2, 2, 20, 8, 2, 0xFF0000, 0xFFFFFFFE, 1, 1, 0),
            struct.pack("<B4fB", 8, 1.5, 2, 0, 1, 0),
            struct.pack("<BI", 4, 1 + 2 * 4 + 6) + struct.pack("<B2f", 77, 0, 0) + struct.pack("<BH", 84, 3) + b"h4z",
            struct.pack("<II2fH", 0xFFFFFFFF, 0x00FF00, 0.5, 0.25, 0),
            b"\x07\x0e",
        )
    )


CASES += (("compact-form", "compact:" + _compact().hex(), {"width": 96}, 0.03),)

# The same picture in other colours: fills, a stroke and gradient stops, one with its own opacity.
CASES += (
    ("colours-swapped", _svg(
        '<linearGradient id="g"><stop offset="0" stop-color="#d02020"/>'
        '<stop offset="1" stop-color="#801010" stop-opacity="0.6"/></linearGradient>'
        '<rect x="4" y="4" width="40" height="18" rx="4" fill="url(#g)"/>'
        '<circle cx="16" cy="34" r="10" fill="#d02020" fill-opacity="0.7" stroke="#801010" stroke-width="3"/>'
        '<path d="M30 28h14v14h-14z" fill="#fd0" stroke="#d02020" stroke-width="2"/>'),
     {"width": 96, "colors": {"d02020": "2040d0", "801010": "102080", "ffdd00": "00c060", "123456": "000000"}}, 0.04),
    # every way of writing a colour: names, rgb(), short and capital hex, in attributes, style="" and a sheet
    ("colours-swapped-spellings", _svg(
        '<style>.s { stroke: blue; stroke-width: 3 }</style>'
        '<linearGradient id="g"><stop offset="0" stop-color="red"/>'
        '<stop offset="1" style="stop-color: rgb(0, 0, 255); stop-opacity: 0.6"/></linearGradient>'
        '<rect x="4" y="4" width="40" height="18" rx="4" fill="url(#g)"/>'
        '<circle class="s" cx="16" cy="34" r="10" fill="rgb(100%, 0%, 0%)" fill-opacity="0.7"/>'
        '<path d="M30 28h14v14h-14z" style="fill:#FD0;stroke:#F00" stroke-width="2"/>'
        '<rect x="2" y="44" width="44" height="3" fill="green"/>'),
     {"width": 96, "colors": {"ff0000": "2040d0", "0000ff": "c08000", "ffdd00": "00c060", "808080": "ff00ff"}}, 0.04),
)

# Calls that must fail the same way in both: (name, Python that fails, given a decoder d and an SVG text s)
ERRORS = (
    ("two sizes", "d.open(s, width=4, height=4)"),
    ("not an svg", "d.open(b'hello, not an svg')"),
    ("not utf-8", "d.open(b'\\xff\\xfe<svg/>')"),
    ("no size", "d.open(b'<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"0\" height=\"0\"/>')"),
    ("too big", "d.open(s, scale=5000)"),
    ("decode before open", "d.decode(bytearray(4))"),
    ("width before open", "d.width"),
    ("no buffers", "d.open(s) and d.decode(None)"),
    ("small target", "d.open(s) and d.decode(bytearray(10))"),
    ("small alpha", "d.open(s) and d.decode(None, bytearray(10))"),
    ("stride too narrow", "d.open(s) and d.decode(bytearray(4096), x=4, stride=24)"),
    ("rows past the end", "d.open(s) and d.decode(bytearray(4096), rows=(0, 13))"),
    ("too little memory", "type(d)(memory=100)"),
    ("not a compact drawing", "d.open(b'\\x01SVG\\x02')"),
    ("colors not a dict", "d.open(s) and d.decode(bytearray(4096), colors=[(1, 2)])"),
    ("colors out of range", "d.open(s) and d.decode(bytearray(4096), colors={0x1000000: 0})"),
    ("decode after close", "d.open(s) and (d.close(), d.decode(bytearray(4096)))"),
    ("width after close", "d.open(s) and (d.close(), d.width)"),
    ("empty Buffer", "Buffer(0)"),
)

# What runs under Pyodide, and here against the desktop backend: every case decoded the three ways.
DRIVER = '''
import base64, functools, json, sys, time


def run(svgio, cases, errors, background, margin):
    out = {"platform": sys.platform, "cases": {}, "errors": {}}
    for name, text, kw in cases:
        d = svgio.SvgDecoder()
        began = time.time()
        source = bytes.fromhex(text[8:]) if text.startswith("compact:") else text.encode()
        kw = dict(kw)
        colors = kw.pop("colors", None)
        if colors is not None:
            colors = {int(k, 16): int(v, 16) for k, v in colors.items()}
        w, h = d.open(source, **kw)
        # one Buffer holds the colour and the alpha, as a board would have it
        buffer = svgio.Buffer(w * h * 3)
        whole = memoryview(buffer)
        pixels, alpha = whole[: w * h * 2], whole[w * h * 2 :]
        d.decode(pixels, alpha)
        took = time.time() - began
        own = bytes(buffer)
        d.decode(pixels, alpha, colors={})
        same_without = bytes(buffer) == own
        if colors is not None:
            d.decode(pixels, alpha, colors=colors)
        pixels, alpha = bytearray(pixels), bytearray(alpha)
        whole = None
        buffer.close()
        d.decode = functools.partial(d.decode, colors=colors)
        mask = bytearray(w * h)
        d.decode(None, mask)
        band_p, band_a = bytearray(w * h * 2), bytearray(w * h)
        for rows in ((0, h // 3), (h // 3, h // 3), (h // 3, h)):
            d.decode(band_p, band_a, rows=rows)
        x, y, wide, tall = margin
        screen = bytearray(background.to_bytes(2, "little") * ((w + wide) * (h + tall)))
        d.decode(screen, x=x, y=y, stride=w + wide)
        banded = bytearray(background.to_bytes(2, "little") * ((w + wide) * (h + tall)))
        for rows in ((0, h // 2), (h // 2, h)):
            d.decode(banded, x=x, y=y, stride=w + wide, rows=rows)
        out["cases"][name] = {
            "size": [w, h, d.width, d.height], "ms": took * 1000, "mask_is_alpha": mask == alpha,
            "empty_colors_is_own": same_without, "buffer_closed": len(buffer) == 0,
            "recolored": colors is not None and bytes(pixels) != own[: w * h * 2],
            "bands_are_whole": (band_p, band_a, banded) == (pixels, alpha, screen),
            "pixels": base64.b64encode(pixels).decode(), "alpha": base64.b64encode(alpha).decode(),
            "screen": base64.b64encode(screen).decode(),
        }
    s = cases[0][1].encode()
    for name, code in errors:
        d = svgio.SvgDecoder()
        try:
            eval(code, {"d": d, "s": s, "Buffer": svgio.Buffer})
            out["errors"][name] = "no error"
        except Exception as e:
            out["errors"][name] = "%s: %s" % (type(e).__name__, e)
    return json.dumps(out)
'''

BOOT_JS = """
export async function boot(base) {
  const { loadPyodide } = await import(base + "pyodide.mjs");
  const py = await loadPyodide({ indexURL: base });
  for (const name of MODULES) {
    py.FS.writeFile("/home/pyodide/" + name, await (await fetch("/utils/" + name)).text());
  }
  py.FS.writeFile("/home/pyodide/driver.py", await (await fetch("/driver.py")).text());
  py.runPython("import driver, svgio, json");
  // runPython, never runPythonAsync: nothing in svgio may need awaiting.
  return (args) => {
    py.globals.set("args", args);
    return py.runPython("driver.run(svgio, *json.loads(args))");
  };
}
"""

WORKER_JS = """
import { boot } from "/boot.js";
let run = null;
self.onmessage = async (e) => {
  try {
    if (run === null) run = await boot(e.data.base);
    self.postMessage({ result: run(e.data.args) });
  } catch (err) {
    self.postMessage({ error: String(err) });
  }
};
"""

PAGE = """<!doctype html>
<meta charset="utf-8"><title>svgio under Pyodide</title>
<script type="module">
import { boot } from "/boot.js";
let main = null;
window.runMain = async (base, args) => {
  if (main === null) main = await boot(base);
  return main(args);
};
const worker = new Worker("/worker.js", { type: "module" });
window.runWorker = (base, args) => new Promise((resolve, reject) => {
  worker.onmessage = (e) => (e.data.error ? reject(new Error(e.data.error)) : resolve(e.data.result));
  worker.onerror = (e) => reject(new Error(e.message));
  worker.postMessage({ base, args });
});
window.ready = true;
</script>
"""


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = dict(
        http.server.SimpleHTTPRequestHandler.extensions_map,
        **{".mjs": "text/javascript", ".js": "text/javascript", ".wasm": "application/wasm", ".py": "text/plain"},
    )
    pyodide_dir = None
    pages = {
        "/": ("text/html", PAGE),
        "/boot.js": ("text/javascript", "const MODULES = %s;\n%s" % (json.dumps(MODULES), BOOT_JS)),
        "/worker.js": ("text/javascript", WORKER_JS),
        "/driver.py": ("text/plain", DRIVER),
    }

    def translate_path(self, path):
        clean = path.split("?", 1)[0]
        if clean.startswith("/pyodide/") and self.pyodide_dir is not None:
            return str(self.pyodide_dir / clean[len("/pyodide/"):])
        if clean.startswith("/utils/") and clean[len("/utils/"):] in MODULES:
            return str(ROOT / "utils" / clean[len("/utils/"):])
        return str(ROOT / "tests" / "no-such-file")

    def do_GET(self):
        if self.path not in self.pages:
            return super().do_GET()
        ctype, text = self.pages[self.path]
        body = text.encode()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def _pyodide_dir():
    env = os.environ.get("PYDEVICES_PYODIDE_DIR")
    return Path(env).expanduser() if env else None


def _missing():
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        return "playwright is not installed"
    try:
        import resvg_py  # noqa: F401
        import PIL  # noqa: F401
    except ImportError:
        return "resvg-py or Pillow isn't installed, so there is no desktop render to compare with"
    folder = _pyodide_dir()
    if folder is not None and not (folder / "pyodide.mjs").exists():
        return "PYDEVICES_PYODIDE_DIR has no pyodide.mjs"
    return None


def desktop(cases, errors=()):
    """Every case through the desktop backend, as the page returns them."""
    import _svgio_resvg

    scope = {}
    exec(DRIVER, scope)
    return json.loads(scope["run"](_svgio_resvg, [c[:3] for c in cases], errors, BACKGROUND, MARGIN))


def _wide(buffer, alpha=None):
    """RGB565 bytes, and coverage if given, as a Pillow RGBA picture's bytes."""
    out = bytearray()
    for i in range(0, len(buffer), 2):
        v = buffer[i] | buffer[i + 1] << 8
        r, g, b = (v >> 8) & 0xF8, (v >> 3) & 0xFC, (v << 3) & 0xF8
        out += bytes((r | r >> 5, g | g >> 6, b | b >> 5, 255 if alpha is None else alpha[i // 2]))
    return bytes(out)


def compare(name, ours, theirs, out=None):
    """How one case differs between the browser and the desktop.

    Returns (share of screen pixels more than TOLERANCE apart, the same for
    alpha, the largest difference on the screen). The screen is the picture
    blended over grey, which is what a display shows.
    """
    from PIL import Image, ImageChops

    w, h = ours["size"][:2]
    x, y, wide, tall = MARGIN
    size = (w + wide, h + tall)
    a = Image.frombytes("RGBA", size, _wide(base64.b64decode(theirs["screen"]))).convert("RGB")
    b = Image.frombytes("RGBA", size, _wide(base64.b64decode(ours["screen"]))).convert("RGB")
    diff = ImageChops.difference(a, b)
    worst = diff.convert("L").point(lambda v: 0)  # the largest channel difference, per pixel
    for band in diff.split():
        worst = ImageChops.lighter(worst, band)
    far = sum(worst.histogram()[TOLERANCE + 1:]) / (size[0] * size[1])
    alpha_a = Image.frombytes("L", (w, h), base64.b64decode(theirs["alpha"]))
    alpha_b = Image.frombytes("L", (w, h), base64.b64decode(ours["alpha"]))
    alpha_far = sum(ImageChops.difference(alpha_a, alpha_b).histogram()[TOLERANCE + 1:]) / (w * h)
    if out is not None:
        zoom = max(1, 192 // max(size))
        sheet = Image.new("RGB", (size[0] * 3 + 8, size[1]), (255, 255, 255))
        sheet.paste(a, (0, 0))
        sheet.paste(b, (size[0] + 4, 0))
        sheet.paste(worst.point(lambda v: 255 if v > TOLERANCE else v * 4).convert("RGB"), (size[0] * 2 + 8, 0))
        sheet = sheet.resize((sheet.width * zoom, sheet.height * zoom), Image.NEAREST)
        Path(out).mkdir(parents=True, exist_ok=True)
        sheet.save(Path(out) / (name + ".png"))
    return far, alpha_far, worst.getextrema()[1]


class Browser:
    """A page with Pyodide and this checkout's svgio, on the main thread and in a worker."""

    def __init__(self):
        from playwright.sync_api import sync_playwright

        Handler.pyodide_dir = _pyodide_dir()
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = "/pyodide/" if Handler.pyodide_dir is not None else PYODIDE_CDN
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch()
        self.page = self.browser.new_page()
        self.messages = []
        self.page.on("console", lambda m: self.messages.append(m.text))
        self.page.on("pageerror", lambda e: self.messages.append(str(e)))
        self.page.goto("http://127.0.0.1:%d/" % self.server.server_address[1])
        self.page.wait_for_function("window.ready === true", timeout=30000)

    def run(self, where, cases, errors=()):
        """Decode ``cases`` on the "Main" thread or in the "Worker"; the driver's result."""
        args = json.dumps([[list(c[:3]) for c in cases], [list(e) for e in errors], BACKGROUND, list(MARGIN)])
        self.page.set_default_timeout(180000)
        return json.loads(self.page.evaluate("([base, args]) => window.run%s(base, args)" % where, [self.base, args]))

    def close(self):
        self.browser.close()
        self.playwright.stop()
        self.server.shutdown()
        self.server.server_close()


class InTheBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reason = _missing()
        if reason is None:
            try:
                cls.browser = Browser()
                cls.addClassCleanup(cls.browser.close)
                cls.results = {where: cls.browser.run(where, CASES, ERRORS) for where in ("Main", "Worker")}
            except Exception as e:  # no Chromium, or Pyodide didn't load
                reason = "%s: %s" % (type(e).__name__, str(e).splitlines()[0])
        if reason:
            message = "the svgio browser check did NOT run: " + reason
            if os.environ.get("PYDEVICES_REQUIRE_BROWSER") == "1":
                raise AssertionError(message)
            sys.stderr.write("\n*** " + message + " ***\n")
            raise unittest.SkipTest(message)
        cls.desktop = desktop(CASES, ERRORS)

    def test_it_ran_under_pyodide(self):
        for where, result in self.results.items():
            self.assertEqual(result["platform"], "emscripten", where)

    def test_sizes_match_the_desktop(self):
        for where, result in self.results.items():
            for name, _, _, _ in CASES:
                self.assertEqual(result["cases"][name]["size"], self.desktop["cases"][name]["size"], (where, name))

    def test_the_mask_is_the_alpha(self):
        for where, result in self.results.items():
            for name, case in result["cases"].items():
                self.assertTrue(case["mask_is_alpha"], (where, name))

    def test_bands_are_the_whole_picture(self):
        for where, result in self.results.items():
            for name, case in result["cases"].items():
                self.assertTrue(case["bands_are_whole"], (where, name))

    def test_colors_buffer_and_close(self):
        for where, result in self.results.items():
            for name, case in result["cases"].items():
                self.assertTrue(case["empty_colors_is_own"], (where, name))
                self.assertTrue(case["buffer_closed"], (where, name))
                self.assertEqual(case["recolored"], name.startswith("colours-swapped"), (where, name))

    def test_pixels_are_close_to_the_desktop(self):
        out = os.environ.get("PYDEVICES_SVGIO_OUT")
        for name, _, _, allowed in CASES:
            far, alpha_far, worst = compare(name, self.results["Main"]["cases"][name], self.desktop["cases"][name], out)
            if out:
                print("%-20s screen %.4f  alpha %.4f  worst %d" % (name, far, alpha_far, worst))
            self.assertLessEqual(far, allowed, name)
            self.assertLessEqual(alpha_far, allowed, name)

    def test_the_worker_draws_what_the_main_thread_draws(self):
        for name, case in self.results["Main"]["cases"].items():
            other = self.results["Worker"]["cases"][name]
            for buffer in ("pixels", "alpha", "screen"):
                self.assertEqual(case[buffer], other[buffer], (name, buffer))

    def test_the_screen_outside_the_picture_is_left_alone(self):
        x, y, wide, tall = MARGIN
        grey = BACKGROUND.to_bytes(2, "little")
        for name, case in self.results["Main"]["cases"].items():
            w, h = case["size"][:2]
            screen = base64.b64decode(case["screen"])
            stride = w + wide
            for row in range(h + tall):
                for col in range(stride):
                    if not (x <= col < x + w and y <= row < y + h):
                        at = (row * stride + col) * 2
                        self.assertEqual(screen[at : at + 2], grey, (name, col, row))

    def test_errors_are_the_desktop_s(self):
        for where, result in self.results.items():
            for name, _ in ERRORS:
                self.assertEqual(result["errors"][name], self.desktop["errors"][name], (where, name))
                self.assertNotEqual(result["errors"][name], "no error", (where, name))


if __name__ == "__main__":
    unittest.main()
