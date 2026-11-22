# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""ttfio.py (omnipython-desktop): MicroPython's ttfio API over FreeType.

The API test is omnipython-builds' modules/ttfio/tests/test_ttfio.py, which
runs unchanged on CPython against this file. What is here is the part only a
desktop can check: that each icon lands where the C module puts it on a
board, with the same ink, and the message a desktop without freetype-py gets.
"""

import importlib
import os
import sys
import unittest

import _env  # noqa: F401

try:
    import freetype  # noqa: F401
except ImportError:
    freetype = None

FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ttfio_data", "icons20.ttf")

# What the C module gives at 20 px on MicroPython's unix port: glyph() and the
# sum of render()'s coverage.
BOARD = {
    0xE63E: ((20, 14, 0, -17, 20), 19987),
    0xE1A7: ((11, 16, 4, -18, 20), 17062),
    0xE1A5: ((8, 16, 6, -18, 20), 30432),
    0xE050: ((14, 14, 3, -17, 20), 20013),
    0xE8B8: ((16, 16, 2, -18, 20), 33438),
    0xE9B2: ((12, 14, 4, -17, 20), 31755),
    0xE5CD: ((10, 10, 5, -15, 20), 9096),
    0xE668: ((12, 10, 4, -15, 20), 5864),
    0xEF7A: ((14, 14, 3, -17, 20), 12711),
    0xE31D: ((12, 15, 4, -18, 20), 17706),
}


@unittest.skipIf(freetype is None, "freetype-py isn't installed")
class SameAsTheBoard(unittest.TestCase):
    def setUp(self):
        import ttfio

        with open(FONT, "rb") as f:
            self.font = ttfio.Font(f.read())

    def test_each_icon_lands_where_the_board_puts_it(self):
        for cp, (box, ink) in BOARD.items():
            with self.subTest(icon=hex(cp)):
                self.assertEqual(self.font.glyph(cp, 20), box)
                self.assertLess(abs(sum(self.font.render(cp, 20)) - ink) / ink, 0.03)

    def test_metrics_match_the_board(self):
        self.assertEqual(self.font.units_per_em, 960)
        self.assertEqual(self.font.metrics(20), (22, -2, 0))
        self.assertEqual(self.font.metrics(13.5), (15, -1, 0))


class WithoutFreetype(unittest.TestCase):
    def test_the_message_says_how_to_install_it(self):
        saved = {k: sys.modules.pop(k) for k in list(sys.modules) if k == "ttfio" or k.startswith("freetype")}
        sys.modules["freetype"] = None      # import freetype now raises ImportError
        try:
            with self.assertRaises(ImportError) as cm:
                importlib.import_module("ttfio")
            self.assertIn("pip install freetype-py", str(cm.exception))
        finally:
            sys.modules.pop("freetype", None)
            sys.modules.pop("ttfio", None)
            sys.modules.update(saved)


if __name__ == "__main__":
    unittest.main()
