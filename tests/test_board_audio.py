# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Run a board's audio routing checks (tests/board_audio_checks.py) on CPython and unix MicroPython, and each plant failing them."""

import os
import subprocess
import sys
import unittest

import _mprun

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CHECKS = os.path.join(HERE, "board_audio_checks.py")
PLANTS = ("route_ignores_choice", "plays_before_link", "radio_at_register", "no_drop_before_stream", "capability_lost",
          "mic_ignores_choice")


def _run(interpreter, plant=None):
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    env.pop("BOARD_AUDIO_PLANT", None)
    if plant:
        env["BOARD_AUDIO_PLANT"] = plant
    return subprocess.run([interpreter, CHECKS], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)


class BoardAudio(unittest.TestCase):
    def test_all(self):
        result = _run(sys.executable)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("all checks passed on cpython", result.stdout)

    def test_each_plant_fails_them(self):
        for plant in PLANTS:
            with self.subTest(plant=plant):
                result = _run(sys.executable, plant)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("FAIL", result.stdout + result.stderr)


class BoardAudioOnMicroPython(unittest.TestCase):
    def test_all(self):
        result = _run(_mprun.need_micropython(self))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("all checks passed on micropython", result.stdout)

    def test_each_plant_fails_them(self):
        interpreter = _mprun.need_micropython(self)
        for plant in PLANTS:
            with self.subTest(plant=plant):
                result = _run(interpreter, plant)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("FAIL", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
