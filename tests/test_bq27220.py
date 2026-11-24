# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Check how the BQ27220 driver decides a battery is there.

The registers come from a Waveshare ESP32-S31-Touch-LCD-4.3C, whose gauge has
its BIN pin tied low: with no battery fitted, with one charging, and with a
full one carrying the board's small load after the charger stopped.
"""

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "drivers" / "power"))

from bq27220 import BQ27220  # noqa: E402


class FakeI2C:
    """A ``machine.I2C`` stand-in that answers word reads from a dict."""

    def __init__(self, words):
        self.words = words

    def readfrom_mem_into(self, addr, cmd, buf):
        buf[:] = struct.pack("<H", self.words.get(cmd, 0) & 0xFFFF)


def gauge(status, mv, ma, avg_ma, soc=100, **kwargs):
    words = {0x0A: status, 0x08: mv, 0x0C: ma, 0x14: avg_ma, 0x2C: soc}
    return BQ27220(FakeI2C(words), **kwargs)


class TiedBin(unittest.TestCase):
    def test_no_battery_reads_missing(self):
        g = gauge(0x5028, 4210, 0, 0, bin_tied_low=True)
        self.assertFalse(g.present)
        self.assertIsNone(g.voltage)
        self.assertIsNone(g.percent)
        self.assertFalse(g.charging)
        self.assertEqual(g.battery_status, "missing")

    def test_noise_below_the_threshold_reads_missing(self):
        self.assertFalse(gauge(0x5028, 4210, -4, 3, bin_tied_low=True).present)

    def test_charging_battery_is_present(self):
        g = gauge(0x4028, 4206, 115, 119, bin_tied_low=True)
        self.assertTrue(g.present)
        self.assertEqual(g.voltage, 4.206)
        self.assertEqual(g.percent, 100)
        self.assertEqual(g.battery_status, "charging")

    def test_full_battery_carrying_the_board_is_present(self):
        g = gauge(0x4268, 4164, -22, -22, bin_tied_low=True)
        self.assertTrue(g.present)
        self.assertEqual(g.battery_status, "full")

    def test_average_alone_keeps_it_present(self):
        self.assertTrue(gauge(0x4268, 4190, 0, -12, bin_tied_low=True).present)

    def test_flag_clear_is_missing_whatever_flows(self):
        self.assertFalse(gauge(0x0000, 0, 50, 50, bin_tied_low=True).present)


class WorkingBin(unittest.TestCase):
    def test_flag_decides(self):
        self.assertTrue(gauge(0x5028, 4210, 0, 0).present)
        g = gauge(0x0000, 0, 0, 0)
        self.assertFalse(g.present)
        self.assertEqual(g.battery_status, "missing")


if __name__ == "__main__":
    unittest.main()
