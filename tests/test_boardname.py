# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Every package that names something after the board gets the name from
_boardname, so older firmware gets the same plain error everywhere.

A firmware frozen before ``boarddev.name()`` existed runs its own boarddev
ahead of a newer one in ``/lib``. ``packages/_boardname`` says so plainly.
Each package here must require it (in ``manifest.py`` for the index and a
firmware, in ``package.json`` for ``mip.install("github:...")``) and must
never call ``boarddev.name()`` itself.
"""

import json
import re
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "_boardname"))

import _boardname  # noqa: E402

# Each package that names something after the board, and the file that does it.
USERS = {
    "usb-hid": ("packages/usb/usb-hid", "usb_hid.py"),
    "midiports": ("packages/midiports", "midiports/usb_device.py"),
    "castdisplay": ("packages/castdisplay", "castdisplay/micecast.py"),
    "hmilink": ("packages/hmilink", "hmilink/tcp.py"),
}
DEP = "github:PyDevices/pydevices/packages/_boardname"
# A call of boarddev.name() with nothing in the brackets reads the name. With
# an argument it sets it, which is the program's own business.
_DIRECT = re.compile(r"\bboarddev\.name\(\s*\)")


def _code(text):
    """*text* without its comments and docstrings, which may mention the call."""
    text = re.sub(r'"""[\s\S]*?"""', "", text)
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


class EveryUserRequiresIt(unittest.TestCase):
    def test_each_manifest_requires_it(self):
        for name, (folder, _module) in USERS.items():
            with self.subTest(package=name):
                manifest = (ROOT / folder / "manifest.py").read_text(encoding="utf-8")
                self.assertRegex(manifest, r'(?m)^require\("_boardname"\)', "%s/manifest.py" % folder)

    def test_each_package_json_depends_on_it(self):
        for name, (folder, _module) in USERS.items():
            with self.subTest(package=name):
                spec = json.loads((ROOT / folder / "package.json").read_text(encoding="utf-8"))
                self.assertIn(DEP, [dep for dep, _ref in spec.get("deps", [])], "%s/package.json" % folder)

    def test_none_reads_boarddev_name_itself(self):
        for name, (folder, module) in USERS.items():
            with self.subTest(package=name):
                code = _code((ROOT / folder / module).read_text(encoding="utf-8"))
                self.assertIsNone(_DIRECT.search(code), "%s/%s calls boarddev.name() directly" % (folder, module))
                self.assertIn("_boardname.name(", code)

    def test_it_is_listed_for_the_index(self):
        split = (ROOT / "mip-split.toml").read_text(encoding="utf-8")
        self.assertRegex(split, r"(?m)^\[_boardname\]\ntop-level = true$")


class OlderFirmware(unittest.TestCase):
    def setUp(self):
        saved = sys.modules.get("boarddev")
        self.addCleanup(lambda: sys.modules.__setitem__("boarddev", saved) if saved else sys.modules.pop("boarddev", None))

    def test_the_board_name_when_boarddev_has_it(self):
        sys.modules["boarddev"] = types.SimpleNamespace(name=lambda: "porch")
        self.assertEqual(_boardname.name("x names the thing", "x", "pass name="), "porch")

    def test_an_older_boarddev_says_what_to_do(self):
        sys.modules["boarddev"] = types.SimpleNamespace()
        with self.assertRaises(AttributeError) as caught:
            _boardname.name("Session() names the cast source", "castdisplay", "pass name= to Session()")
        message = str(caught.exception)
        self.assertIn("Session() names the cast source after the board with boarddev.name()", message)
        self.assertIn("older than castdisplay", message)
        self.assertIn("Update the firmware", message)
        self.assertIn('target="/"', message)
        self.assertIn("pass name= to Session()", message)

    def test_castdisplay_and_hmilink_say_it_too(self):
        sys.path.insert(0, str(ROOT / "packages" / "castdisplay"))
        sys.path.insert(0, str(ROOT / "packages" / "hmilink"))
        self.addCleanup(sys.path.remove, str(ROOT / "packages" / "castdisplay"))
        self.addCleanup(sys.path.remove, str(ROOT / "packages" / "hmilink"))
        from castdisplay.micecast import Session
        from hmilink import tcp

        sys.modules["boarddev"] = types.SimpleNamespace()
        with self.assertRaises(AttributeError) as caught:
            Session("192.168.1.50")
        self.assertIn("pass name= to Session()", str(caught.exception))
        self.assertEqual(Session("192.168.1.50", name="den").name, "den")
        listener = tcp.Listener.__new__(tcp.Listener)
        with self.assertRaises(AttributeError) as caught:
            listener._announce(None)
        self.assertIn('pass announce="a-name"', str(caught.exception))


if __name__ == "__main__":
    unittest.main()
