# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""svgio on CPython and Pyodide: SVG decode, the same API as MicroPython's
built-in svgio (micropython-pydevices' modules/svgio).

    d = svgio.SvgDecoder()
    w, h = d.open("wifi.svg", width=48)          # or bytes, or a stream
    d.decode(pixels, alpha)                      # RGB565 and coverage
    d.decode(fb_buf, x=10, y=10, stride=480)     # blended over what's there
    d.decode(fb_buf, rows=(0, 120))              # a band of the picture
    d.open(drawing)                              # or a drawing in the compact form

An app imports svgio and doesn't care which runtime it's on. On a desktop
resvg and Pillow draw (``pip install resvg-py pillow``). In a browser, under
Pyodide, the page's own 2D canvas draws, so there is nothing to install.
Pixels are native-order (little-endian) RGB565, as displaydev framebuffers
hold them.
"""

import sys

from _svgio_compact import expand  # noqa: F401

if sys.platform == "emscripten":
    from _svgio_canvas import SvgDecoder  # noqa: F401
else:
    from _svgio_resvg import SvgDecoder  # noqa: F401
