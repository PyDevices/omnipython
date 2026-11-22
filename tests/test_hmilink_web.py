# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""hmilink on a web page, in headless Chromium, against this process.

The page (``tests/hmilink_web/``) opens WebSerial and Web Bluetooth ports
through ``hmilink.js``, on stand-ins whose far end is a CPython device or
panel here, reached through a function Playwright exposes to the page. Three
cases: a plain JavaScript ``Link``; Python in MicroPython's WebAssembly build
as a panel over Bluetooth; and the same as the device over serial. Each
change crosses both ways, and a planted fault (every ``0.75`` turned into
``0.15`` in transit) must fail every case.

This checks the page's half and the framing, not a radio or a USB port.

Needs Playwright with Chromium and the direct MicroPython WebAssembly build:
``bin/micropython.mjs`` in a folder above this checkout, or its path in
``HMILINK_WASM``. Without them the skip is loud, and
``OMNIPYTHON_REQUIRE_BROWSER=1`` turns it into a failure.
"""

from pathlib import Path
import functools
import http.server
import os
import sys
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "packages" / "hmilink"))

import hmilink  # noqa: E402
from hmilink import local, stream  # noqa: E402


def _wasm():
    given = os.environ.get("HMILINK_WASM")
    if given:
        return Path(given)
    for parent in ROOT.parents:
        if (parent / "bin" / "micropython.mjs").exists():
            return parent / "bin" / "micropython.mjs"
    return None


def _missing():
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        return "playwright is not installed"
    wasm = _wasm()
    if wasm is None or not wasm.exists():
        return "no bin/micropython.mjs above this checkout (set HMILINK_WASM)"
    return None


class _Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = dict(
        http.server.SimpleHTTPRequestHandler.extensions_map,
        **{".mjs": "text/javascript", ".js": "text/javascript", ".wasm": "application/wasm", ".py": "text/plain"},
    )
    wasm_dir = None

    def translate_path(self, path):
        clean = path.split("?", 1)[0]
        if clean.startswith("/wasm/"):
            return str(self.wasm_dir / clean[len("/wasm/"):])
        return super().translate_path(path)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *args):
        pass


class HostEnd:
    """The host's end of one page port: a stream for `hmilink.stream.link`."""

    def __init__(self):
        self.inbox = b""
        self.outbox = b""
        self.heard = False

    def read(self, n):
        data, self.inbox = self.inbox[:n], self.inbox[n:]
        return data or None

    def write(self, data):
        self.outbox += data
        return len(data)

    def feed(self, data):
        if data:
            self.heard = True
            self.inbox += bytes(data)

    def take(self):
        out, self.outbox = self.outbox, b""
        return list(out)


class Host:
    """What sits where the board would: a device, or a panel, per case."""

    def __init__(self, case):
        self.case = case
        self.end = HostEnd()
        if case == "wasm-device":
            self.device = None
            self.panel = hmilink.Panel(stream.link(self.end))
        else:
            self.device = hmilink.Device(hmilink.Model({"knobs": {"a": 0.5, "b": 0.5}}))
            listener = self.device.add(local.serve())
            self.mine = hmilink.Panel(listener.connect())
            self.attached = False
            self.panel = None

    def poll(self):
        if self.device is not None:
            # A board on hmilink.ble sends nothing until the central speaks;
            # wait for the page's opening line before attaching, as it does.
            if not self.attached and (self.case != "wasm-panel" or self.end.heard):
                self.device.add(stream.link(self.end))
                self.attached = True
            for _ in range(4):
                self.device.poll()
                self.mine.poll()
        else:
            for _ in range(4):
                self.panel.poll()

    def xfer(self, name, data):
        self.end.feed(data)
        self.poll()
        return self.end.take()


class HmilinkWebGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reason = _missing()
        if reason:
            message = "hmilink web gate did NOT run: " + reason
            if os.environ.get("OMNIPYTHON_REQUIRE_BROWSER") == "1":
                raise AssertionError(message)
            sys.stderr.write("\n*** " + message + " ***\n")
            raise unittest.SkipTest(message)
        from playwright.sync_api import sync_playwright

        _Handler.wasm_dir = _wasm().parent
        handler = functools.partial(_Handler, directory=str(ROOT))
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = "http://127.0.0.1:%d/tests/hmilink_web/page.html" % cls.server.server_address[1]
        cls.pw = sync_playwright().start()
        try:
            cls.browser = cls.pw.chromium.launch()
        except Exception as e:
            cls.pw.stop()
            cls.server.shutdown()
            raise unittest.SkipTest("no Chromium for Playwright: %s" % e)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.server.server_close()

    def run_case(self, case, query="", until=(), seconds=60):
        """Run ``case`` until the host and page say ``until`` (or time runs out)."""
        host = Host(case)
        page = self.browser.new_page()
        try:
            page.expose_function("hostXfer", host.xfer)
            page.goto("%s?case=%s&%s" % (self.base, case, query))
            page.wait_for_function("document.getElementById('log').textContent.includes('PAGE LOADED')")
            page.click("#go")
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                page.wait_for_timeout(100)  # the exposed function runs while this waits
                if host.panel is not None and case == "wasm-device" and host.panel.ready and "sent" not in host.__dict__:
                    host.sent = True
                    host.panel.set("/knobs/a", 0.75)
                log = page.inner_text("#log")
                if "ERROR" in log or all(self._holds(host, log, want) for want in until):
                    break
            return host, page.inner_text("#log")
        finally:
            page.close()

    @staticmethod
    def _holds(host, log, want):
        if callable(want):
            return want(host)
        return want in log

    # -- the cases --

    def check_js(self, plant):
        host, log = self.run_case(
            "js",
            "plant=1" if plant else "",
            until=("PAGE ECHO seq 1 value 0.75", lambda h: h.device.model.doc["knobs"]["a"] == 0.75),
            seconds=10 if plant else 60,
        )
        self.assertNotIn("ERROR", log, log)
        self.assertIn("PAGE DOC a 0.5", log, log)
        self.assertIn("PAGE ECHO seq 1 value 0.75", log, log)
        self.assertEqual(host.device.model.doc["knobs"]["a"], 0.75)
        return host, log

    def test_js_link_over_serial(self):
        self.check_js(False)

    def check_wasm_panel(self, plant):
        def b_moved(h):
            if h.device.model.doc["knobs"]["a"] == 0.75 and h.mine.doc["knobs"]["b"] == 0.5:
                h.mine.set("/knobs/b", 0.75)  # a change from another panel, for the page to follow
            return True

        host, log = self.run_case(
            "wasm-panel",
            "plant=1" if plant else "",
            until=(b_moved, "PAGE B 0.75", lambda h: h.device.model.doc["knobs"]["a"] == 0.75),
            seconds=10 if plant else 90,
        )
        self.assertNotIn("ERROR", log, log)
        self.assertIn("PAGE DOC a 0.5", log, log)
        self.assertEqual(host.device.model.doc["knobs"]["a"], 0.75, log)
        self.assertIn("PAGE B 0.75", log, log)
        return host, log

    def test_wasm_panel_over_bluetooth(self):
        self.check_wasm_panel(False)

    def check_wasm_device(self, plant):
        host, log = self.run_case(
            "wasm-device",
            "plant=1" if plant else "",
            until=("PAGE A 0.75", lambda h: h.panel.ready and h.panel.doc["knobs"]["b"] == 0.75),
            seconds=10 if plant else 90,
        )
        self.assertNotIn("ERROR", log, log)
        self.assertTrue(host.panel.ready, log)
        self.assertIn("PAGE A 0.75", log, log)
        self.assertEqual(host.panel.doc["knobs"]["b"], 0.75, log)
        return host, log

    def test_wasm_device_over_serial(self):
        self.check_wasm_device(False)

    def test_bluetooth_writes_fit_the_mtu(self):
        # The page told 23 sends 20-byte writes, which a 23-byte link carries whole.
        host, log = self.run_case(
            "wasm-panel",
            "mtu=23&mock_mtu=23",
            until=(lambda h: h.device.model.doc["knobs"]["a"] == 0.75,),
        )
        self.assertEqual(host.device.model.doc["knobs"]["a"], 0.75, log)

    def test_an_overstated_mtu_fails(self):
        # The page believes 247, the link carries 23: every long write is cut short.
        host, log = self.run_case(
            "wasm-panel",
            "mtu=247&mock_mtu=23",
            until=(lambda h: h.device.model.doc["knobs"]["a"] == 0.75,),
            seconds=10,
        )
        self.assertEqual(host.device.model.doc["knobs"]["a"], 0.5, log)

    def test_planted_fault_fails_every_case(self):
        for check in (self.check_js, self.check_wasm_panel, self.check_wasm_device):
            with self.subTest(case=check.__name__):
                with self.assertRaises(AssertionError):
                    check(True)


if __name__ == "__main__":
    unittest.main()
