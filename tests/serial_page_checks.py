# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""A browser page's serial ports (`webserial`) in endpointkit, against a fake Web Serial.

Runs on the MicroPython WebAssembly build under node (``wasm_node_run.mjs``),
where ``js`` is the real FFI and ``navigator.serial`` is a JavaScript
stand-in whose ports echo what they're sent and can be fed bytes.
"""

import sys

try:
    _here = __file__
except NameError:  # pragma: no cover
    _here = sys.argv[0]
_dir = _here.rsplit("/", 1)[0] if "/" in _here else "."
sys.path.insert(0, _dir + "/../packages/endpointkit")
sys.path.insert(0, _dir + "/../lib")

import asyncio

import js

import endpointkit
import webserial

TESTS = []


class Air:
    """Nothing: these checks need no radio."""


class Failed(Exception):
    pass


def check(fn):
    TESTS.append(fn)
    return fn


def expect(cond, message="expectation failed"):
    if not cond:
        raise Failed(message)


# A page whose browser already let it use one Espressif board, and whose
# chooser gives a WCH adapter (or refuses). Each port keeps what it was
# sent and the speed it was opened at; feed() is what the device sends.
_FAKE = """(present, refuse) => {
    const fake = {sent: [], bauds: [], asked: 0, ports: []};
    const listeners = {};
    const make = (vid, pid) => {
        let push = null;
        const port = {
            getInfo: () => ({usbVendorId: vid, usbProductId: pid}),
            readable: null, writable: null,
            open: async ({baudRate}) => {
                fake.bauds.push(baudRate);
                port.readable = new ReadableStream({start: (c) => { push = c; }});
                port.writable = new WritableStream({write: (chunk) => { fake.sent.push(Array.from(chunk)); }});
            },
            close: async () => { port.readable = null; port.writable = null; },
        };
        port.feed = (bytes) => push.enqueue(new Uint8Array(bytes));
        fake.ports.push(port);
        return port;
    };
    const board = make(0x303a, 0x1001);
    const adapter = make(0x1a86, 0x7523);
    fake.unplug = (i) => listeners.disconnect.forEach((f) => f({target: fake.ports[i]}));
    fake.plug = (i) => listeners.connect.forEach((f) => f({target: fake.ports[i]}));
    const serial = {
        getPorts: async () => [board],
        requestPort: async () => {
            fake.asked++;
            if (refuse) { const e = new Error('No port selected by the user.'); e.name = 'NotFoundError'; throw e; }
            return adapter;
        },
        addEventListener: (type, f) => { (listeners[type] = listeners[type] || []).push(f); },
    };
    Object.defineProperty(globalThis, 'navigator', {configurable: true, writable: true,
        value: present ? {serial} : {}});
    return fake;
}"""


def fresh(present=True, refuse=False):
    fake = js.eval(_FAKE)(present, refuse)
    page = js.eval(webserial._PAGE)()
    reg = endpointkit.Registry()
    webserial.register(reg, page)
    return fake, reg


async def settle(reg, rounds=4):
    for _ in range(rounds):
        await asyncio.sleep(0.01)
        reg.poll()


def labels(reg):
    return [(ep.label, ep.state) for ep in reg.endpoints("serial")]


@check
async def ports_allowed_before_are_listed_with_the_chooser(air):
    fake, reg = fresh()
    await settle(reg)
    expect(labels(reg) == [("Espressif (303a:1001)", "available"), ("Choose a serial port", "needs pairing")], "listed %r" % labels(reg))
    expect(fake.asked == 0, "the chooser opened before a tap")


@check
async def the_chooser_adds_the_port_picked(air):
    fake, reg = fresh()
    await settle(reg)
    reg.pair("webserial:ask")
    await settle(reg)
    expect(fake.asked == 1, "asked %d times" % fake.asked)
    expect([l for l, _ in labels(reg)] == ["Espressif (303a:1001)", "WCH (1a86:7523)", "Choose a serial port"], "listed %r" % labels(reg))


@check
async def a_chosen_port_opens_reads_and_writes(air):
    fake, reg = fresh()
    await settle(reg)
    reg.select("serial", "webserial:Espressif (303a:1001)")
    ep = reg.find("webserial:Espressif (303a:1001)")
    expect(ep.state == endpointkit.CONNECTED, "state %r" % ep.state)
    port = webserial.open(ep, baudrate=115200)
    for _ in range(20):
        if port.is_open():
            break
        await asyncio.sleep(0.01)
    expect(port.is_open(), "never opened")
    expect(list(fake.bauds) == [115200], "bauds %r" % list(fake.bauds))
    expect(port.read() is None, "read before anything arrived")
    fake.ports[0].feed([0x3E, 0x3E, 0x3E, 0x20])
    await asyncio.sleep(0.02)
    expect(port.any() == 4, "any %d" % port.any())
    expect(port.read(2) == b">>", "first two")
    expect(port.read() == b"> ", "the rest")
    expect(port.write(b"1+1\r") == 4, "write")
    await asyncio.sleep(0.02)
    expect([list(s) for s in fake.sent] == [[0x31, 0x2B, 0x31, 0x0D]], "sent %r" % [list(s) for s in fake.sent])
    port.close()
    await asyncio.sleep(0.02)
    expect(not port.is_open(), "still open after close")


@check
async def an_unplugged_port_leaves_and_comes_back(air):
    fake, reg = fresh()
    await settle(reg)
    fake.unplug(0)
    await settle(reg)
    expect([l for l, _ in labels(reg)] == ["Choose a serial port"], "after unplug %r" % labels(reg))
    fake.plug(0)
    await settle(reg)
    expect([l for l, _ in labels(reg)] == ["Espressif (303a:1001)", "Choose a serial port"], "after plug %r" % labels(reg))


@check
async def a_closed_chooser_says_why(air):
    fake, reg = fresh(refuse=True)
    await settle(reg)
    reg.pair("webserial:ask")
    await settle(reg)
    ask = reg.find("webserial:ask")
    expect("No port selected" in ask.caps.get("why", ""), "why %r" % ask.caps.get("why"))
    expect(len(labels(reg)) == 2, "listed %r" % labels(reg))


@check
async def no_web_serial_says_so(air):
    fake, reg = fresh(present=False)
    await settle(reg)
    eps = reg.endpoints("serial")
    expect(len(eps) == 1 and eps[0].state == endpointkit.UNAVAILABLE, "listed %r" % eps)
    expect("Web Serial" in eps[0].caps.get("why", ""), "why %r" % eps[0].caps.get("why"))
    reg.select("serial", eps[0].id)
    expect(reg.find(eps[0].id).error, "choosing it is refused")
