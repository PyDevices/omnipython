# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Draw a Material Symbols icon at two sizes and print it as text.

Counts the built-in icons, checks that a name is among them, and draws one
icon as an 8-bit alpha mask at a small and a larger size. Each mask is
printed with one character per pixel, darker characters for more ink, so
you can see the same icon drawn sharp at both sizes. Success is two Wi-Fi
signs, the second twice as tall.

Needs: a MicroPython firmware built with the ttfio and icons modules
(``--modules ttfio,icons`` or ``all``), or CPython with omnipython-desktop.
No display.

Run it:

    mpremote run icons_simpletest.py

Tested on: the MicroPython unix port v1.30.0-preview.160 built with
``--modules ttfio,icons``, and CPython 3.12 on Linux with
omnipython-desktop's ttfio over freetype-py.
"""

import icons

# Change these to match your setup.
NAME = "wifi"  # any name icons.names() lists
SIZES = (12, 24)  # square sizes in pixels, 8 to 256

# See how many icons the font holds, and whether yours is one of them.
print("%d icons; %s is %s" % (len(icons.names()), NAME, "in" if icons.has(NAME) else "missing"))

# Draw the icon at each size and print the mask row by row.
for size in SIZES:
    data, w, h = icons.mask(NAME, size)
    print("%s at %d px:" % (NAME, size))
    for y in range(h):
        print("".join(" .:#"[a // 64] for a in data[y * w : (y + 1) * w]))
