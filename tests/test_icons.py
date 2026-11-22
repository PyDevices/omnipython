# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Run icons' own checks (packages/icons/tests/run.py) on CPython, and on MicroPython when it has ttfio."""

import os
import subprocess
import sys
import unittest

import _env  # noqa: F401
import _mprun

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.join(os.path.dirname(HERE), "packages", "icons", "tests", "run.py")

try:
    import freetype  # noqa: F401
except ImportError:
    freetype = None


@unittest.skipIf(freetype is None, "freetype-py isn't installed (ttfio.py needs it)")
class IconsOnCPython(unittest.TestCase):
    def test_all(self):
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(p for p in sys.path if p))
        result = subprocess.run([sys.executable, RUN], capture_output=True, text=True, timeout=300, env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("all checks passed on cpython", result.stdout)


class IconsOnMicroPython(unittest.TestCase):
    def test_all(self):
        interpreter = _mprun.need_micropython(self)
        probe = _mprun.run([interpreter, "-c", "import ttfio"], timeout=30)
        if probe.returncode != 0:
            self.skipTest("this MicroPython has no ttfio; build it with --modules ttfio")
        result = _mprun.run([interpreter, RUN], timeout=300)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("all checks passed on micropython", result.stdout)


if __name__ == "__main__":
    unittest.main()
