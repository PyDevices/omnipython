# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""A browser page's speakers and microphones (`audiodev.page_devices`),
gamepads (`displaydev.endpoints`) and serial ports (`webserial`) in
endpointkit, on the MicroPython WebAssembly build under node.

    python -m unittest tests.test_page_devices

The build is ``OMNIPYTHON_MICROPYTHON_MJS`` or the workspace's
``bin/micropython.mjs``; without node or a build the test is skipped, or
fails when ``OMNIPYTHON_REQUIRE_MICROPYTHON=1``.
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _mprun import run  # noqa: E402

HERE = Path(__file__).resolve().parent


class PageDevices(unittest.TestCase):
    def _run(self, script):
        node = shutil.which("node")
        mjs = os.environ.get("OMNIPYTHON_MICROPYTHON_MJS")
        if not mjs:
            found = [p / "bin" / "micropython.mjs" for p in HERE.parents if (p / "bin" / "micropython.mjs").is_file()]
            mjs = str(found[0]) if found else None
        if not node or not mjs:
            message = "no node or no micropython.mjs: the page's devices did NOT run on the WebAssembly build"
            if os.environ.get("OMNIPYTHON_REQUIRE_MICROPYTHON") == "1":
                self.fail(message)
            sys.stderr.write("\n*** " + message + " ***\n")
            self.skipTest(message)
        with tempfile.TemporaryDirectory() as empty:
            # The runner's adafruit_midi folder: these checks need none.
            result = run([node, HERE / "wasm_node_run.mjs", mjs, empty, script], timeout=300)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(" 0 failed", result.stdout)

    def test_speakers_and_microphones(self):
        self._run("audio_page_checks.py")

    def test_gamepads(self):
        self._run("gamepad_page_checks.py")

    def test_serial_ports(self):
        self._run("serial_page_checks.py")


if __name__ == "__main__":
    unittest.main()
