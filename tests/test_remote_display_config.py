# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""The remote-display board config: a RemoteDisplay beside any board's peripherals."""

import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest
from unittest import mock

_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))
import _env  # noqa: E402, F401  (lib/ and drivers/ on the path)

import boarddev  # noqa: E402

ROOT = _env.ROOT
CONFIG = ROOT / "board_configs" / "nodisplay" / "remote-display" / "board_config.py"
NODISPLAY = ROOT / "board_configs" / "nodisplay"
if str(ROOT / "drivers" / "input") not in sys.path:
    sys.path.insert(0, str(ROOT / "drivers" / "input"))  # keypad_gpio


class _Pin:
    def __init__(self, level=1):
        self.level = level

    def value(self):
        return self.level


def _peripherals(with_keypad):
    mod = types.ModuleType("board_peripherals")
    mod.PERIPHERALS = frozenset({"thing"})
    mod.thing = lambda: "made"
    mod.pin = _Pin()

    def load_peripherals(ns):
        boarddev.bind_lazy(ns, mod)

    mod.load_peripherals = load_peripherals
    if with_keypad:

        def keypad():
            import keys
            from keypad_gpio import GPIOButtons

            return GPIOButtons({"a": (mod.pin, keys.K_RETURN)})

        mod.keypad = keypad
    return mod


class RemoteDisplayConfigTests(unittest.TestCase):
    def setUp(self):
        self.made = []
        test = self

        class FakeRemoteDisplay:
            def __init__(self, width, height, port=80, *, password=None):
                self.width, self.height, self.port, self.password = width, height, port, password
                test.made.append(self)

            def get_events(self):
                return []

            def fill(self, color):
                pass

        remote = types.ModuleType("displaydev.remotedisplay")
        remote.RemoteDisplay = FakeRemoteDisplay
        self.modules = {"displaydev.remotedisplay": remote}
        # env_set writes os.environ too: give each test its own copy.
        names = ("OMNIPYTHON_REMOTE_PASSWORD", "OMNIPYTHON_WIDTH", "OMNIPYTHON_HEIGHT", "OMNIPYTHON_REMOTE_PORT")
        environ = mock.patch.dict(os.environ)
        environ.start()
        self.addCleanup(environ.stop)
        for name in names:
            os.environ.pop(name, None)
            boarddev._overrides.pop(name, None)
            self.addCleanup(boarddev._overrides.pop, name, None)

    def _load(self, peripherals, webrepl_pass=None):
        modules = dict(self.modules)
        modules["board_peripherals"] = peripherals
        if webrepl_pass is None:
            modules["webrepl_cfg"] = None  # an import of it raises ImportError
        else:
            modules["webrepl_cfg"] = types.SimpleNamespace(PASS=webrepl_pass)
        with mock.patch.dict(sys.modules, modules):
            spec = importlib.util.spec_from_file_location("board_config", CONFIG)
            config = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(config)
        return config

    def test_defaults_and_webrepl_password(self):
        config = self._load(_peripherals(False), webrepl_pass="secret")
        display = config.display_drv
        self.assertEqual((display.width, display.height, display.port), (480, 320, 80))
        self.assertEqual(display.password, "secret")
        self.assertEqual(config.host_read(), [])
        self.assertFalse(hasattr(config, "keypad"))

    def test_board_peripherals_bind(self):
        config = self._load(_peripherals(False), webrepl_pass="secret")
        self.assertEqual(config.PERIPHERALS, frozenset({"thing"}))
        self.assertEqual(config.thing, "made")

    def test_environment_overrides(self):
        boarddev.env_set("OMNIPYTHON_REMOTE_PASSWORD", "other")
        boarddev.env_set("OMNIPYTHON_WIDTH", 320)
        boarddev.env_set("OMNIPYTHON_HEIGHT", 240)
        boarddev.env_set("OMNIPYTHON_REMOTE_PORT", 8080)
        display = self._load(_peripherals(False)).display_drv
        self.assertEqual((display.width, display.height, display.port), (320, 240, 8080))
        self.assertEqual(display.password, "other")

    def test_no_password_refuses(self):
        with self.assertRaises(ImportError) as caught:
            self._load(_peripherals(False))
        self.assertIn("OMNIPYTHON_REMOTE_PASSWORD", str(caught.exception))
        self.assertEqual(self.made, [])

    def test_board_buttons_become_keypad(self):
        import keys

        peripherals = _peripherals(True)
        config = self._load(peripherals, webrepl_pass="secret")
        self.assertEqual(config.keypad_read(), [])
        peripherals.pin.level = 0
        self.assertEqual(config.keypad_read(), [keys.K_RETURN])

    def test_every_headless_board_has_peripherals_only(self):
        # A headless board's package must not bring a board_config.py: that
        # would overwrite this one, or a display's, when both are installed.
        for folder in sorted(NODISPLAY.iterdir()):
            if folder.name == "remote-display" or not (folder / "manifest.py").is_file():
                continue
            with self.subTest(board=folder.name):
                self.assertTrue((folder / "board_peripherals.py").is_file())
                self.assertFalse((folder / "board_config.py").exists())


if __name__ == "__main__":
    unittest.main()
