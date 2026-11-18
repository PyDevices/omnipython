# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""AndroidSDLDisplay fills by uploading pixels, not by queueing GPU draws.

A queued ``SDL_RenderFillRect`` into the render-target texture was
sometimes lost on a phone while the Activity settled after turning to
landscape. These tests check that a fill lands in the texture, is clipped
to it, and issues no render-target draw.
"""

from pathlib import Path
import sys
import unittest
from unittest import mock

_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))
import _env  # noqa: E402, F401

try:
    import usdl2
    from displaydev import androidsdl
except Exception as exc:  # usdl2 / SDL2 missing on this host
    androidsdl = None
    _SKIP = str(exc)
else:
    _SKIP = ""

RED565 = 0xF800
CYAN565 = 0x07FF


@unittest.skipIf(androidsdl is None, "displaydev.androidsdl unavailable: %s" % _SKIP)
class FillRectTests(unittest.TestCase):
    def setUp(self):
        self.display = androidsdl.AndroidSDLDisplay(width=64, height=32, quiet=True)
        self.addCleanup(self.display.deinit)

    def _rgb(self, x, y):
        rgb = self.display._read_texture_rgb()
        at = (y * self.display.width + x) * 3
        return tuple(rgb[at : at + 3])

    def test_fill_lands_in_the_texture(self):
        self.display.fill_rect(8, 4, 16, 8, RED565)
        self.assertEqual(self._rgb(8, 4), (255, 0, 0))
        self.assertEqual(self._rgb(23, 11), (255, 0, 0))
        self.assertNotEqual(self._rgb(24, 11), (255, 0, 0))
        self.assertNotEqual(self._rgb(7, 4), (255, 0, 0))

    def test_a_later_fill_covers_an_earlier_one_in_order(self):
        self.display.fill_rect(0, 0, 64, 32, RED565)
        self.display.fill_rect(10, 10, 5, 5, CYAN565)
        self.assertEqual(self._rgb(12, 12), (0, 255, 255))
        self.assertEqual(self._rgb(9, 12), (255, 0, 0))

    def test_a_fill_past_the_edge_is_clipped(self):
        self.display.fill_rect(-10, -10, 20, 20, RED565)
        self.display.fill_rect(60, 28, 20, 20, RED565)
        self.assertEqual(self._rgb(0, 0), (255, 0, 0))
        self.assertEqual(self._rgb(63, 31), (255, 0, 0))
        self.display.fill_rect(100, 100, 5, 5, RED565)

    def test_no_render_target_draw_is_queued(self):
        with mock.patch.object(usdl2, "SDL_RenderFillRect") as fill, \
                mock.patch.object(usdl2, "SDL_SetRenderTarget") as target:
            self.display.fill_rect(0, 0, 10, 10, RED565)
        fill.assert_not_called()
        target.assert_not_called()


if __name__ == "__main__":
    unittest.main()
