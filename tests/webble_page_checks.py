# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Bluetooth MIDI devices a browser page chooses (`midiports.webble`) in
endpointkit, against a stand-in for the browser's chooser and the device.

Runs on the MicroPython WebAssembly build under node (``wasm_node_run.mjs``),
where the links run on the page's own asyncio, as they do on a page.
"""

import sys

try:
    _here = __file__
except NameError:  # pragma: no cover
    _here = sys.argv[0]
_dir = _here.rsplit("/", 1)[0] if "/" in _here else "."
sys.path.insert(0, _dir + "/../packages/endpointkit")
sys.path.insert(0, _dir + "/../packages/midiports")
sys.path.insert(0, _dir + "/../lib")

import asyncio

import endpointkit
from midiports import IN, OUT, webble
from midiports.endpoints import HostMidi

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


class Device:
    def __init__(self, name):
        self.name = name
        self.address = "00:11:22:33:44:55"


class Connection:
    def __init__(self, device):
        self.device = device
        self.up = True

    def is_connected(self):
        return self.up


class Port:
    """A connected BLE-MIDI device: what it sends, and what it was sent."""

    def __init__(self, device):
        self.connection = Connection(device)
        self.name = device.name
        self.error = None
        self.dropped = 0
        self.sent = []
        self.inbox = []

    def take(self):
        return self.inbox.pop(0) if self.inbox else None

    def write(self, buf, nbytes=None):
        data = bytes(buf[: len(buf) if nbytes is None else nbytes])
        self.sent.append(data)
        return len(data)

    def close(self):
        self.connection.up = False


class Chooser:
    """The browser's chooser and the device it gives, or a refusal."""

    def __init__(self, name="Pulse", refuse=None):
        self.device = Device(name)
        self.refuse = refuse
        self.calls = []
        self.ports = []

    async def connect(self, ble, device=None, **kw):
        self.calls.append("again" if device is not None else "choose")
        if self.refuse is not None and device is None:
            raise OSError(self.refuse)
        port = Port(device or self.device)
        self.ports.append(port)
        return port

    def link(self):
        return webble.PageBleIn(ble=object(), connect=self.connect)


def fresh(present=True):
    webble.forget()
    webble._available = lambda: present
    reg = endpointkit.Registry()
    ins = reg.register(HostMidi(IN, webble))
    outs = reg.register(HostMidi(OUT, webble))
    return reg, ins, outs


async def settle(reg, rounds=4):
    for _ in range(rounds):
        await asyncio.sleep(0.02)
        reg.poll()


def labels(reg, kind):
    return [ep.label for ep in reg.endpoints(kind)]


@check
async def the_chooser_is_offered_until_a_device_is_chosen(air):
    reg, ins, outs = fresh()
    await settle(reg)
    expect(labels(reg, "midi.in") == [webble.ASK], "in: %r" % labels(reg, "midi.in"))
    expect(labels(reg, "midi.out") == [webble.ASK], "out: %r" % labels(reg, "midi.out"))
    expect(reg.endpoints("midi.in")[0].state == endpointkit.NEEDS_PAIRING, "state %r" % reg.endpoints("midi.in")[0].state)


@check
async def a_chosen_device_plays_both_ways(air):
    reg, ins, outs = fresh()
    chooser = Chooser("Pulse")
    webble.request(chooser.link)
    await settle(reg)
    expect(chooser.calls == ["choose"], "calls %r" % chooser.calls)
    expect(labels(reg, "midi.in") == [webble.ASK, "Pulse"], "in: %r" % labels(reg, "midi.in"))
    expect(labels(reg, "midi.out") == [webble.ASK, "Pulse"], "out: %r" % labels(reg, "midi.out"))
    reg.select("midi.in", ins.name + ":Pulse")
    reg.select("midi.out", outs.name + ":Pulse")
    chooser.ports[0].inbox.append((0, b"\x90\x3c\x64"))
    await settle(reg, 2)
    got = ins.open["Pulse"].read()
    expect(got == b"\x90\x3c\x64", "read %r" % (got,))
    outs.open["Pulse"].write(b"\x80\x3c\x00")
    expect(chooser.ports[0].sent == [b"\x80\x3c\x00"], "sent %r" % chooser.ports[0].sent)
    reg.select("midi.in", [])
    outs.open["Pulse"].write(b"\x90\x40\x40")  # the output still has its link
    expect(len(chooser.ports[0].sent) == 2, "sent %r" % chooser.ports[0].sent)


@check
async def a_dropped_link_comes_back_without_the_chooser(air):
    reg, ins, outs = fresh()
    chooser = Chooser("Pulse")
    webble.request(chooser.link)
    await settle(reg)
    chooser.ports[0].connection.up = False
    await asyncio.sleep(0.3)
    expect(chooser.calls[:2] == ["choose", "again"], "calls %r" % chooser.calls)
    expect(labels(reg, "midi.in") == [webble.ASK, "Pulse"], "still listed: %r" % labels(reg, "midi.in"))


@check
async def a_closed_chooser_lists_nothing_and_says_why_once(air):
    reg, ins, outs = fresh()
    chooser = Chooser(refuse="User cancelled the requestDevice() chooser.")
    webble.request(chooser.link)
    await settle(reg)
    expect(labels(reg, "midi.in") == [webble.ASK], "in: %r" % labels(reg, "midi.in"))
    expect("cancelled" in (webble.why() or ""), "why")
    expect(webble.why() is None, "said twice")
    expect(webble.state() == "idle", "state %r" % webble.state())


@check
async def no_web_bluetooth_says_so(air):
    reg, ins, outs = fresh(present=False)
    await settle(reg)
    eps = reg.endpoints("midi.in")
    expect([ep.label for ep in eps] == [webble.ASK], "in: %r" % labels(reg, "midi.in"))
    expect(eps[0].state == endpointkit.UNAVAILABLE, "state %r" % eps[0].state)
    expect("Web Bluetooth" in eps[0].caps.get("why", ""), "why %r" % eps[0].caps.get("why"))
