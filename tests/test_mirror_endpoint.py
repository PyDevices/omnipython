# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""The browser mirror as a cast.target endpoint."""
import os
import sys
import types
import unittest

import _env  # noqa: F401

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "packages", "castdisplay"))
sys.path.insert(0, os.path.join(ROOT, "packages", "endpointkit"))

import endpointkit  # noqa: E402
from castdisplay.endpoints import Mirror  # noqa: E402


class Panel:
    width = 64
    height = 32

    def __init__(self):
        self.buf = bytearray(self.width * self.height * 2)

    def framebuffers(self):
        return (self.buf, None, None, self.width * 2)

    def blit_rect(self, buf, x, y, w, h):
        pass

    def fill_rect(self, x, y, w, h, c):
        pass

    def flush_rect(self, x, y, w, h):
        pass


class NoFrame:
    def framebuffers(self):
        return None


class MirrorTest(unittest.TestCase):
    def setUp(self):
        sys.modules.pop("webrepl_cfg", None)
        self.registry = endpointkit.Registry(store=None)

    def tearDown(self):
        sys.modules.pop("webrepl_cfg", None)

    def provider(self, display=None, **kwargs):
        p = Mirror(display=display or Panel(), port=18765, **kwargs)
        self.registry.register(p)
        self.addCleanup(p.stop)
        return p

    def test_no_password_never_runs_open(self):
        sys.modules["webrepl_cfg"] = types.ModuleType("webrepl_cfg")
        p = self.provider()
        (e,) = p.scan()
        self.assertEqual(e.state, endpointkit.UNAVAILABLE)
        self.assertIn("WebREPL password", e.caps["why"])
        with self.assertRaises(ValueError):
            p.apply(e, True)
        self.assertIsNone(p.server)

    def test_webrepl_password_starts_it(self):
        cfg = types.ModuleType("webrepl_cfg")
        cfg.PASS = "hunter22"
        sys.modules["webrepl_cfg"] = cfg
        panel = Panel()
        plain = panel.blit_rect
        p = self.provider(panel)
        (e,) = p.scan()
        self.assertEqual(e.state, endpointkit.AVAILABLE)
        p.apply(e, True)
        self.assertEqual(p.server._password, "hunter22")
        (e,) = p.scan()
        self.assertEqual(e.state, endpointkit.CONNECTED)
        self.assertTrue(e.caps["url"].endswith(":18765/"))
        self.assertNotIn("hunter22", repr(e.caps))
        p.apply(e, False)
        self.assertIsNone(p.server)
        # Letting it go puts the panel's own drawing back.
        self.assertEqual(panel.blit_rect, plain)

    def test_poll_reports_choosing_and_letting_go(self):
        p = self.provider(password="x")
        (e,) = p.scan()
        self.assertIsNone(p.poll())
        p.apply(e, True)
        (e,) = p.poll()
        self.assertEqual(e.state, endpointkit.CONNECTED)
        self.assertTrue(e.caps["url"].startswith("http://"))
        self.assertFalse(e.caps["viewing"])
        self.assertIsNone(p.poll())
        p.apply(e, False)
        (e,) = p.poll()
        self.assertEqual(e.state, endpointkit.AVAILABLE)
        self.assertIsNone(e.caps["url"])

    def test_not_remembered(self):
        self.assertFalse(Mirror.remember)

    def test_remote_display_no_endpoint(self):
        panel = Panel()
        panel.server = types.SimpleNamespace(note=lambda *a: None)
        self.assertEqual(self.provider(panel, password="x").scan(), [])

    def test_no_frame_no_endpoint(self):
        self.assertEqual(self.provider(NoFrame(), password="x").scan(), [])


if __name__ == "__main__":
    unittest.main()
