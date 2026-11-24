# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Run hmilink's own checks (tests/hmilink_checks.py) under unittest."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(os.path.dirname(HERE), "lib")


class TestHmilink(unittest.TestCase):
    def test_all(self):
        sys.path.insert(0, HERE)
        sys.path.insert(0, LIB)
        try:
            import hmilink_checks

            hmilink_checks.test_all()
        finally:
            sys.path.remove(LIB)
            sys.path.remove(HERE)


if __name__ == "__main__":
    unittest.main()
