# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""A cast with no name is listed under the board's name."""
import os
import sys
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "lib"))

import boarddev  # noqa: E402
from castdisplay.micecast import Session  # noqa: E402


class CastNameTest(unittest.TestCase):
    def setUp(self):
        boarddev.name("porch")
        self.addCleanup(boarddev.name, None)

    def test_no_name_is_the_board_name(self):
        self.assertEqual(Session("192.168.1.50").name, "porch")

    def test_a_name_given_wins(self):
        self.assertEqual(Session("192.168.1.50", name="den").name, "den")


if __name__ == "__main__":
    unittest.main()
