# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Run the desktop endpointkit providers' checks (tests/endpoint_providers_checks.py) on CPython and unix MicroPython."""

import os
import subprocess
import sys
import unittest

import _mprun

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CHECKS = os.path.join(HERE, "endpoint_providers_checks.py")


def _env():
    return dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")


class EndpointProviders(unittest.TestCase):
    def test_all(self):
        result = subprocess.run([sys.executable, CHECKS], cwd=ROOT, env=_env(), capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("all checks passed on cpython", result.stdout)


class EndpointProvidersOnMicroPython(unittest.TestCase):
    def test_all(self):
        interpreter = _mprun.need_micropython(self)
        result = subprocess.run([interpreter, CHECKS], cwd=ROOT, env=_env(), capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("all checks passed on micropython", result.stdout)


if __name__ == "__main__":
    unittest.main()
