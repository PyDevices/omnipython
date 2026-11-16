# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""``boarddev.name()`` on CPython and on unix MicroPython.

``board_name_checks.py`` holds the checks: the naming rules, a desktop's
name, a browser's, and each board store (ESP32 NVS, a file, CircuitPython's
settings.toml) over fakes.
"""

import os
import subprocess
import sys
import unittest

import _mprun

CHECKS = str(_mprun.TESTS / "board_name_checks.py")


class BoardNameTest(unittest.TestCase):
    def _check(self, interpreter):
        env = dict(os.environ)
        env.pop("OMNIPYTHON_BOARD_NAME", None)
        result = subprocess.run([interpreter, CHECKS], capture_output=True, text=True, timeout=60, env=env)
        out = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, out)
        self.assertIn("OK", out)

    def test_cpython(self):
        self._check(sys.executable)

    def test_micropython(self):
        self._check(_mprun.need_micropython(self))


if __name__ == "__main__":
    unittest.main()
