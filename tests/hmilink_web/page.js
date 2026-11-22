// SPDX-FileCopyrightText: 2026 Brad Barnett
//
// SPDX-License-Identifier: MIT

// The gate page. ?case= picks what runs on the page:
//   js           a plain JavaScript Link over WebSerial, the host a device
//   wasm-panel   Python in MicroPython WebAssembly as a panel over Web
//                Bluetooth, the host a device (a board's desk page)
//   wasm-device  Python in MicroPython WebAssembly as the device over
//                WebSerial, the host a panel (the browser as the box)
// The ports are the stand-ins in mock_ports.js. The page logs PAGE lines;
// the test reads them and checks the host's side itself.
import { openSerial, openBluetooth, Link } from "/packages/hmilink/js/hmilink.js";

const q = new URLSearchParams(location.search);
const CASE = q.get("case");
const log = window.gateLog;

const PY_FILES = ["__init__", "local", "stream", "web"];

async function loadPython() {
  const { loadMicroPython } = await import("/wasm/micropython.mjs");
  const mp = await loadMicroPython({ stdout: (line) => log("PY " + line), linebuffer: true });
  mp.FS.mkdirTree("/lib/hmilink");
  for (const name of PY_FILES) {
    const response = await fetch(`/packages/hmilink/hmilink/${name}.py`, { cache: "no-store" });
    mp.FS.writeFile(`/lib/hmilink/${name}.py`, await response.text());
  }
  mp.runPython("import sys\nif '/lib' not in sys.path: sys.path.append('/lib')");
  return mp;
}

function every(mp, ms) {
  const timer = setInterval(() => {
    try {
      mp.runPython("tick()");
    } catch (e) {
      clearInterval(timer);
      log("PYTHON ERROR " + e);
    }
  }, ms);
}

const PANEL = `
import js
import hmilink
from hmilink import stream, web

panel = hmilink.Panel(stream.link(web.stream(js.hmiPort)))
said = set()

def say(line):
    if line not in said:
        said.add(line)
        js.gateLog(line)

def tick():
    panel.poll()
    if not panel.ready:
        return
    say("PAGE DOC a %s" % panel.doc["knobs"]["a"])
    if "sent" not in said:
        said.add("sent")
        panel.set("/knobs/a", 0.75)
    if panel.doc["knobs"]["b"] != 0.5:
        say("PAGE B %s" % panel.doc["knobs"]["b"])
`;

const DEVICE = `
import js
import hmilink
from hmilink import local, stream, web

model = hmilink.Model({"knobs": {"a": 0.5, "b": 0.5}})
device = hmilink.Device(model)
device.add(stream.link(web.stream(js.hmiPort)))
mine = hmilink.Panel(device.add(local.serve()).connect())
said = set()

def say(line):
    if line not in said:
        said.add(line)
        js.gateLog(line)

def tick():
    device.poll()
    mine.poll()
    if model.doc["knobs"]["a"] != 0.5:
        say("PAGE A %s" % model.doc["knobs"]["a"])
        if "sent" not in said:
            said.add("sent")
            mine.set("/knobs/b", 0.75)
`;

async function run() {
  if (CASE === "js") {
    const link = new Link(await openSerial({ serial: window.mockSerial }));
    link.onmessage = (msg) => {
      if (msg.t === "doc") {
        log("PAGE DOC a " + msg.doc.knobs.a);
        link.send({ t: "op", op: "replace", path: "/knobs/a", value: 0.75, id: 1 });
      } else if (msg.t === "op" && msg.id === 1) {
        log("PAGE ECHO seq " + msg.seq + " value " + msg.value);
      } else if (msg.t === "op" && msg.path === "/knobs/b") {
        log("PAGE B " + msg.value);
      }
    };
  } else if (CASE === "wasm-panel") {
    const mp = await loadPython();
    window.hmiPort = await openBluetooth({ name: "rack", mtu: parseInt(q.get("mtu") || "247", 10), bluetooth: window.mockBluetooth });
    mp.runPython(PANEL);
    every(mp, 10);
  } else if (CASE === "wasm-device") {
    const mp = await loadPython();
    window.hmiPort = await openSerial({ serial: window.mockSerial });
    mp.runPython(DEVICE);
    every(mp, 10);
  } else {
    log("PAGE ERROR no case " + CASE);
    return;
  }
  log("PAGE RUNNING");
}

document.getElementById("go").addEventListener("click", () => {
  run().catch((e) => log("PAGE ERROR " + e));
});
log("PAGE LOADED");
