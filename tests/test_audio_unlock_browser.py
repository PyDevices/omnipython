# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""``AudioOut`` on the direct MicroPython WebAssembly build, under Chromium's
default autoplay policy.

A page that has not had a click may not start audio. This plays a tone
through ``audiodev.auto.audio_out()`` without any retry of its own, and checks
that the browser's ``AudioContext`` stays suspended and nothing is queued
until the first click, and that it is running and filled with samples after
it. The page runs the checkout's own ``lib/audiodev`` over the build's frozen
copy.

Needs Playwright with Chromium and a wasm build with the audio unlock in its
bridge: ``bin/micropython.mjs`` in the workspace, or the folder named by
``PYDEVICES_WASM_DIR``. Without them the skip is loud, and
``PYDEVICES_REQUIRE_BROWSER=1`` turns it into a failure.
"""

import functools
import http.server
import json
import os
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PAGE = """<!doctype html>
<meta charset="utf-8"><title>audio unlock</title>
<body><button id="b" style="width:200px;height:200px">click</button>
<script>
window.ctxs = [];
window.sources = 0;
const Real = window.AudioContext;
window.AudioContext = class extends Real {
  constructor(...a) { super(...a); window.ctxs.push(this); }
  createBufferSource() { window.sources++; return super.createBufferSource(); }
};
</script>
<script type="module">
const { loadMicroPython } = await import("/wasm/micropython.mjs");
const mp = await loadMicroPython({ stdout: (l) => console.log(l), linebuffer: true, heapsize: 16 * 1024 * 1024 });
const files = JSON.parse(await (await fetch("/files.json")).text());
mp.FS.mkdirTree("/t/audiodev");
for (const name of files) {
  const r = await fetch("/lib/" + name);
  mp.FS.writeFile("/t/" + name, await r.text());
}
await mp.runPythonAsync(`
import sys
sys.path.insert(0, "/t")
import array, math
import audiocore
from audiodev.auto import audio_out
rate = 48000
tone = array.array("h", [int(8000 * math.sin(2 * math.pi * 440 * (i // 2) / rate)) for i in range(rate // 5)])
sample = audiocore.RawSample(tone, sample_rate=rate, channel_count=2)
out = audio_out(latency="low")
out.play(sample, loop=True)
def tick():
    out.service()
    return out.playing
`);
window.tick = () => { mp.runPython("window_playing = tick()"); return mp.globals.get("window_playing"); };
window.ready = true;
setInterval(() => window.tick(), 10);
</script>
"""


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = dict(
        http.server.SimpleHTTPRequestHandler.extensions_map,
        **{".mjs": "text/javascript", ".wasm": "application/wasm", ".py": "text/plain"},
    )
    wasm_dir = None
    files = []

    def translate_path(self, path):
        clean = path.split("?", 1)[0]
        if clean.startswith("/wasm/"):
            return str(self.wasm_dir / clean[len("/wasm/"):])
        return super().translate_path(path)

    def do_GET(self):
        if self.path == "/":
            body = PAGE.encode()
            ctype = "text/html"
        elif self.path == "/files.json":
            body = json.dumps(self.files).encode()
            ctype = "application/json"
        else:
            return super().do_GET()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def _wasm_dir():
    env = os.environ.get("PYDEVICES_WASM_DIR")
    if env:
        return Path(env)
    for parent in ROOT.parents:
        if (parent / "bin" / "micropython.mjs").exists():
            return parent / "bin"
    return None


def _missing():
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        return "playwright is not installed"
    folder = _wasm_dir()
    if folder is None or not (folder / "micropython.mjs").exists():
        return "no wasm build (bin/micropython.mjs or PYDEVICES_WASM_DIR)"
    return None


class AudioUnlocksOnTheFirstClick(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reason = _missing()
        if reason:
            message = "the browser audio-unlock gate did NOT run: " + reason
            if os.environ.get("PYDEVICES_REQUIRE_BROWSER") == "1":
                raise AssertionError(message)
            sys.stderr.write("\n*** " + message + " ***\n")
            raise unittest.SkipTest(message)
        from playwright.sync_api import sync_playwright

        Handler.wasm_dir = _wasm_dir()
        Handler.files = sorted(
            str(p.relative_to(ROOT / "lib")).replace(os.sep, "/")
            for p in (ROOT / "lib" / "audiodev").glob("*.py")
        ) + ["backends.py"]
        handler = functools.partial(Handler, directory=str(ROOT))
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.pw = sync_playwright().start()
        try:
            # No autoplay flag: the browser's default policy is the point.
            cls.browser = cls.pw.chromium.launch()
        except Exception as e:
            cls.pw.stop()
            cls.server.shutdown()
            raise unittest.SkipTest("no Chromium for Playwright: {}".format(e))

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()

    def state(self, page):
        return page.evaluate(
            "({state: window.ctxs.length ? window.ctxs[0].state : 'none',"
            " sources: window.sources,"
            " time: window.ctxs.length ? window.ctxs[0].currentTime : 0})"
        )

    def test_suspended_before_a_click_and_playing_after(self):
        page = self.browser.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        try:
            page.goto("http://127.0.0.1:%d/" % self.server.server_port)
            page.wait_for_function("window.ready === true", timeout=120000)
            page.wait_for_timeout(1500)
            before = self.state(page)
            self.assertNotEqual(before["state"], "running", before)
            self.assertEqual(before["sources"], 0, before)
            self.assertTrue(page.evaluate("window.tick()"), "play() was refused")

            page.click("#b")
            page.wait_for_function(
                "window.ctxs.length && window.ctxs[0].state === 'running' && window.sources > 3",
                timeout=20000,
            )
            first = self.state(page)
            page.wait_for_timeout(500)
            later = self.state(page)
            self.assertEqual(later["state"], "running", later)
            self.assertGreater(later["time"], first["time"])
            self.assertGreater(later["sources"], first["sources"])
            self.assertEqual(errors, [])
        finally:
            page.close()


if __name__ == "__main__":
    unittest.main()
