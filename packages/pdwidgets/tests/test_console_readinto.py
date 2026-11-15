# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Console.readinto reads from the reader it was given, and says None without one."""

import unittest

from pdwidgets.console import Console


class Reader:
    def readinto(self, buf, nbytes=0):
        buf[:3] = b"abc"
        return 3


def console():
    # A Console needs a display; readinto touches nothing but the reader.
    made = object.__new__(Console)
    made._read_obj = None
    return made


class TestReadinto(unittest.TestCase):
    def test_no_reader_gives_none(self):
        self.assertIsNone(console().readinto(bytearray(4)))

    def test_a_reader_fills_the_buffer(self):
        made = console()
        made._read_obj = Reader()
        buf = bytearray(4)
        self.assertEqual(made.readinto(buf), 3)
        self.assertEqual(bytes(buf[:3]), b"abc")


if __name__ == "__main__":
    unittest.main()
