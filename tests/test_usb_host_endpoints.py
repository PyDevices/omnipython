# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Run usb.host.endpoints' checks (tests/usb_host_endpoints_checks.py) on CPython and unix MicroPython."""

import os
import subprocess
import sys
import unittest

import _mprun

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CHECKS = os.path.join(HERE, "usb_host_endpoints_checks.py")


class UsbHostEndpoints(unittest.TestCase):
    def test_all(self):
        result = subprocess.run([sys.executable, CHECKS], cwd=ROOT, capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("all checks passed on cpython", result.stdout)


class UsbHostEndpointsOnMicroPython(unittest.TestCase):
    def test_all(self):
        interpreter = _mprun.need_micropython(self)
        result = subprocess.run([interpreter, CHECKS], cwd=ROOT, capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("all checks passed on micropython", result.stdout)


if __name__ == "__main__":
    unittest.main()
