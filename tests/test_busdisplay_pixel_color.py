# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""``BusDisplay.pixel()`` sends its colour the way a blit does.

A bus with ``send_color()`` (spibus with ``swap_bytes=True`` converts the
colour as it copies) must see the pixel's RAMWR through ``send_color()``;
before, ``pixel()`` used ``send()``, which never converts, so single pixels
had the wrong byte order. A bus without ``send_color()`` sees no change.
"""

import unittest

import _env  # noqa: F401

from displaydev.busdisplay import BusDisplay

_RAMWR = 0x2C
_SEQUENCE = b"\x11\x80\x78"  # SLPOUT + 120 ms


class PlainBus:
    def __init__(self):
        self.sent = []

    def send(self, command, data=b"", **kwargs):
        self.sent.append(("send", command, bytes(data)))


class ColorBus(PlainBus):
    def send_color(self, command, data, **kwargs):
        self.sent.append(("send_color", command, bytes(data)))


def pixel_writes(bus, **kw):
    display = BusDisplay(bus, _SEQUENCE, width=8, height=8, quiet=True, **kw)
    del bus.sent[:]
    result = display.pixel(3, 2, 0xF800)
    return result, [w for w in bus.sent if w[1] == _RAMWR]


class TestPixelColor(unittest.TestCase):
    def test_bus_with_send_color_gets_the_pixel_through_it(self):
        result, writes = pixel_writes(ColorBus())
        self.assertEqual(result, (3, 2, 1, 1))
        self.assertEqual(writes, [("send_color", _RAMWR, b"\x00\xf8")])

    def test_window_commands_stay_on_send(self):
        bus = ColorBus()
        pixel_writes(bus)
        self.assertTrue(all(w[0] == "send" for w in bus.sent if w[1] != _RAMWR))

    def test_bus_without_send_color_is_unchanged(self):
        result, writes = pixel_writes(PlainBus())
        self.assertEqual(result, (3, 2, 1, 1))
        self.assertEqual(writes, [("send", _RAMWR, b"\x00\xf8")])

    def test_byte_order_of_the_pixel_bytes_is_unchanged(self):
        _, writes = pixel_writes(ColorBus(), reverse_bytes_in_word=True)
        self.assertEqual(writes, [("send_color", _RAMWR, b"\xf8\x00")])


if __name__ == "__main__":
    unittest.main()
