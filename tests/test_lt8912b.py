# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Run the LT8912B driver contract (``lt8912b_contract.py``) on CPython and MicroPython.

The contract checks, on a fake I2C bus, that `lt8912b` writes the registers
Adafruit's and Espressif's drivers write, packs each mode's timing, refuses
modes the lanes can't carry, keeps the audio registers alone unless audio is
asked for, and reads a real monitor's EDID. It is a plain script so
MicroPython can run it too. This file runs it under CPython, under a unix
``micropython`` when one is available, and once per planted fault, each of
which must make it fail.

The MicroPython run looks for ``OMNIPYTHON_MICROPYTHON``, then ``micropython``
on PATH, then the workspace's ``bin/micropython`` beside this checkout. When
none exists the skip is loud, and ``OMNIPYTHON_REQUIRE_MICROPYTHON=1`` turns it
into a failure.
"""

import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _mprun  # noqa: E402

CONTRACT = Path(__file__).resolve().parent / "lt8912b_contract.py"
PLANTS = ("hfp-hbp", "no-lane-check", "audio-leak", "edid-polarity")


def _run(interpreter, *args):
    return subprocess.run(
        [interpreter, str(CONTRACT), *args],
        capture_output=True,
        text=True,
        timeout=120,
    )


class LT8912BContract(unittest.TestCase):
    def assertPasses(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(" 0 failed", result.stdout)

    def test_cpython(self):
        self.assertPasses(_run(sys.executable))

    def test_micropython(self):
        result = _run(_mprun.need_micropython(self))
        self.assertPasses(result)
        self.assertIn("(micropython)", result.stdout)

    def test_every_plant_fails(self):
        for plant in PLANTS:
            with self.subTest(plant=plant):
                result = _run(sys.executable, "--plant=" + plant)
                self.assertIn("PLANTED " + plant, result.stdout)
                self.assertNotEqual(result.returncode, 0, "plant %r went unnoticed:\n%s" % (plant, result.stdout))
                self.assertIn("FAIL", result.stdout)


if __name__ == "__main__":
    unittest.main()
