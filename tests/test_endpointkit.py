# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Run endpointkit's own checks (packages/endpointkit/tests/run.py) on CPython and unix MicroPython."""

import os
import sys
import unittest

import _mprun

HERE = os.path.dirname(os.path.abspath(__file__))
ENDPOINTKIT = os.path.join(os.path.dirname(HERE), "packages", "endpointkit")
RUN = os.path.join(ENDPOINTKIT, "tests", "run.py")


class TestEndpointkit(unittest.TestCase):
    def test_all(self):
        sys.path.insert(0, os.path.join(ENDPOINTKIT, "tests"))
        sys.path.insert(0, ENDPOINTKIT)
        try:
            import run

            run.test_all()
        finally:
            sys.path.remove(ENDPOINTKIT)
            sys.path.remove(os.path.join(ENDPOINTKIT, "tests"))


class EndpointkitOnMicroPython(unittest.TestCase):
    def test_all(self):
        interpreter = _mprun.need_micropython(self)
        result = _mprun.run([interpreter, RUN], timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("all checks passed on micropython", result.stdout)


if __name__ == "__main__":
    unittest.main()
