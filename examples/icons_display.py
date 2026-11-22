# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Show a grid of icons with their names on the display.

Draws each icon with ``icons.gfx.draw``, which blends its mask in a
colour over a pygraphics framebuffer, and writes its name underneath.
Each cell is drawn in a small buffer of its own and copied onto the
display, so the program needs a few kilobytes, not a whole frame.
Success is twelve icons in three columns, each over its name.

Needs: a board_config with a display_drv, which an OmniPython board
package or omnipython-desktop provides, pygraphics with
``FrameBuffer.blit_alpha``, and the ttfio and icons modules in the
firmware (``--modules ttfio,icons`` or ``all``) or omnipython-desktop.

Run it:

    mpremote run icons_display.py

Tested on: the MicroPython unix port v1.30.0-preview.160 built with
``--modules ttfio,icons``, and CPython 3.12 on Linux with pygraphics 0.2,
each through the desktop board_config in an SDL window.
"""

import time

from board_config import display_drv
from icons import gfx
from pygraphics import RGB565, FrameBuffer

# Change these to match your setup.
NAMES = (
    "home", "settings", "wifi", "bluetooth",
    "battery_full", "volume_up", "mic", "photo_camera",
    "music_note", "headphones", "usb", "cast",
)
COLUMNS = 3
SIZE = 48  # the icon's square, in pixels
COLOR = 0xFFE0  # RGB565 yellow
BACKGROUND = 0x0010  # RGB565 dark blue
SECONDS = 10

# Work out the cells: the display's width split into columns, each tall
# enough for an icon and a line of 8-pixel text below it.
cell_width = display_drv.width // COLUMNS
cell_height = SIZE + 16
pixels = bytearray(cell_width * cell_height * 2)
cell = FrameBuffer(pixels, cell_width, cell_height, RGB565)
display_drv.fill(BACKGROUND)

# Draw each icon and its name into the cell, then copy the cell on.
for i, name in enumerate(NAMES):
    cell.fill(BACKGROUND)
    gfx.draw(cell, name, (cell_width - SIZE) // 2, 0, COLOR, SIZE)
    label = name[: cell_width // 8]
    cell.text(label, (cell_width - len(label) * 8) // 2, SIZE + 4, 0xFFFF)
    x = (i % COLUMNS) * cell_width
    y = (i // COLUMNS) * (cell_height + 8) + 8
    display_drv.blit_rect(pixels, x, y, cell_width, cell_height)

# Put it on the screen and leave it there for a while.
display_drv.show()
print("Drew %d icons at %d px on the %dx%d display" % (len(NAMES), SIZE, display_drv.width, display_drv.height))
time.sleep(SECONDS)
