# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""icons' checks, runnable on MicroPython and CPython.

    micropython tests/run.py      (from packages/icons, with ttfio built in)
    python tests/run.py           (with omnipython-desktop's ttfio.py on the path)

Bars fixed before the first run:

- 500 names, sorted, every one found by has(), and iconkit's 129 among them;
- every icon draws at 16, 20 and 24 px with ink in it, inside its square, and
  one that needs more scratch than the font starts with grows it and draws;
- mask() keeps a drawn mask and gives the same bytes again; into a buffer it
  draws the same bytes; the cache never holds more than CACHE_SIZE masks;
- an added font module's icons draw, a taken name or a malformed module is
  refused, and unknown names and sizes raise ValueError naming the fix;
- gfx.rgb565() blends to the colours at full and no coverage, and gfx.draw()
  hands blit_alpha the mask.
"""

import sys

_FILE = __file__.replace("\\", "/")
HERE = _FILE.rsplit("/", 1)[0] if "/" in _FILE else "."
sys.path.insert(0, HERE + "/..")

import icons  # noqa: E402
from icons import _material, gfx  # noqa: E402

ICONKIT = (
    "home", "settings", "wifi", "bluetooth", "battery_full", "volume_up", "volume_off",
    "mic", "search", "close", "check", "menu", "arrow_back", "play_arrow", "pause",
    "music_note", "videocam", "photo_camera", "notifications", "lock", "usb", "cast",
)

failures = []


def check(ok, what):
    print("%s  %s" % ("ok  " if ok else "FAIL", what))
    if not ok:
        failures.append(what)


def raises(exc, fn, *args):
    try:
        fn(*args)
    except exc as e:
        return str(e)
    return None


names = icons.names()
check(len(names) == 500 and names == sorted(names), "500 names, sorted (got %d)" % len(names))
check(all(icons.has(n) for n in names), "has() finds every name")
check(all(n in names for n in ICONKIT), "iconkit's everyday icons are all here")

empty = []
spill = []
for px in (16, 20, 24):
    for n in names:
        data, w, h = icons.mask(n, px, bytearray(px * px))
        if max(data) < 128:
            empty.append((n, px))
        entry, cp = icons._find(n)
        gw, gh, gx, gy, _ = entry[1].glyph(cp, px)
        if gx < 0 or gx + gw > px or gy < -px or gy + gh > 0:
            spill.append((n, px))
check(not empty, "every icon has ink at 16, 20 and 24 px %r" % empty[:5])
check(not spill, "every icon fits its square %r" % spill[:5])

big = icons.mask("hub", 96)
# ttfio on CPython has no scratch buffer, so only MicroPython grows one.
grew = icons._fonts[0][2] > icons.SCRATCH or sys.implementation.name != "micropython"
check(max(big[0]) == 255 and grew, "hub at 96 px draws (scratch now %d bytes)" % icons._fonts[0][2])

a = icons.mask("wifi", 20)
b = icons.mask("wifi", 20)
own = icons.mask("wifi", 20, bytearray(400))
check(a[1:] == (20, 20) and bytes(a[0]) == bytes(b[0]) == bytes(own[0]), "a mask from the cache and into a buffer are the same bytes")
for n in names[:icons.CACHE_SIZE + 8]:
    icons.mask(n, 18)
check(len(icons._cache) <= icons.CACHE_SIZE, "the cache holds at most %d masks (%d)" % (icons.CACHE_SIZE, len(icons._cache)))


class Custom:
    FONT = _material.FONT
    NAMES = b"zz_my_home\n"
    i = _material.NAMES.split(b"\n").index(b"home") * 3
    CODES = _material.CODES[i:i + 3]


icons.add(Custom)
check(icons.has("zz_my_home") and bytes(icons.mask("zz_my_home", 24)[0]) == bytes(icons.mask("home", 24)[0]),
      "an added font's icon draws")
check(raises(ValueError, icons.add, Custom) is not None, "adding a taken name raises ValueError")


class Broken:
    FONT = _material.FONT
    NAMES = b"zz_broken\n"
    CODES = b"\x00"


check(raises(ValueError, icons.add, Broken) is not None, "a module with short CODES raises ValueError")
err = raises(ValueError, icons.mask, "no_such_icon", 24)
check(err is not None and "icons.names()" in err, "an unknown name raises ValueError naming names(): %r" % (err,))
check(raises(ValueError, icons.mask, "home", 7) is not None, "size 7 raises ValueError")
check(raises(ValueError, icons.mask, "home", 24, bytearray(10)) is not None, "a wrong-sized buf raises ValueError")

px = gfx.rgb565("stop", 0xF800, 0x001F, 24)
data = icons.mask("stop", 24)[0]
full = [i for i in range(576) if data[i] == 255]
none = [i for i in range(576) if data[i] == 0]
check(len(px) == 1152 and full and none
      and all(px[2 * i] | px[2 * i + 1] << 8 == 0xF800 for i in full)
      and all(px[2 * i] | px[2 * i + 1] << 8 == 0x001F for i in none),
      "rgb565() is the colour under full coverage and the background under none")


class Blitter:
    def blit_alpha(self, data, x, y, w, h, color):
        self.call = (bytes(data), x, y, w, h, color)


fb = Blitter()
gfx.draw(fb, "home", 3, 4, 0x1234, 20)
check(fb.call == (bytes(icons.mask("home", 20)[0]), 3, 4, 20, 20, 0x1234), "gfx.draw() hands blit_alpha the mask")
check(raises(AttributeError, gfx.draw, object(), "home", 0, 0, 0) is not None, "gfx.draw() on something without blit_alpha raises")

impl = sys.implementation.name
if failures:
    print("%d failed on %s" % (len(failures), impl))
    sys.exit(1)
print("all checks passed on %s" % impl)
