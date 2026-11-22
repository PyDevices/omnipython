# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Draw every icon in a grid, on CPython, for the docs.

    python tools/icon_sheet.py OUT.png [--size 24] [--cols 25]

Needs Pillow and omnipython-desktop's ttfio.py (freetype-py).
"""

import argparse
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import icons  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("out")
    p.add_argument("--size", type=int, default=24)
    p.add_argument("--cols", type=int, default=25)
    args = p.parse_args()
    names = icons.names()
    cell = args.size * 3 // 2
    rows = (len(names) + args.cols - 1) // args.cols
    sheet = Image.new("L", (args.cols * cell, rows * cell), 255)
    pad = (cell - args.size) // 2
    for i, name in enumerate(names):
        data, w, h = icons.mask(name, args.size)
        glyph = Image.frombytes("L", (w, h), bytes(255 - a for a in data))
        sheet.paste(glyph, ((i % args.cols) * cell + pad, (i // args.cols) * cell + pad))
    sheet.save(args.out, optimize=True)
    print("%s: %d icons at %d px" % (args.out, len(names), args.size))


if __name__ == "__main__":
    main()
