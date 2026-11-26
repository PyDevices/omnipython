# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""A browser page's speakers and microphones in endpointkit, against a fake browser.

Runs on the MicroPython WebAssembly build under node (``wasm_node_run.mjs``),
where ``js`` is the real FFI and ``navigator.mediaDevices`` and the runtime's
``Module.omnipythonBridge`` are JavaScript stand-ins, so the device list
settles between the checks' awaits as it does on a page.
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
from audiodev import endpoints

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


# Two speakers and a microphone, labelled or not, and a runtime that routes.
_FAKE = """(labels, sinks, bridge) => {
    const devices = [
        {kind: 'audiooutput', deviceId: 'default', label: labels ? 'Default - Speakers' : ''},
        {kind: 'audiooutput', deviceId: 'spk', label: labels ? 'Speakers' : ''},
        {kind: 'audiooutput', deviceId: 'hp', label: labels ? 'Headphones' : ''},
        {kind: 'audioinput', deviceId: 'communications', label: ''},
        {kind: 'audioinput', deviceId: 'mic', label: labels ? 'USB Mic' : ''},
        {kind: 'videoinput', deviceId: 'cam', label: 'Camera'},
    ];
    const heard = new Set();
    const fake = {routes: [], errors: {}};
    fake.plug = (kind, deviceId, label) => { devices.push({kind, deviceId, label}); for (const fn of heard) fn(); };
    fake.unplug = (deviceId) => { const i = devices.findIndex((d) => d.deviceId === deviceId); devices.splice(i, 1); for (const fn of heard) fn(); };
    const media = {
        enumerateDevices: () => Promise.resolve(devices.map((d) => Object.assign({}, d))),
        addEventListener: (type, fn) => { if (type === 'devicechange') heard.add(fn); },
    };
    Object.defineProperty(globalThis, 'navigator', {value: {mediaDevices: media}, configurable: true, writable: true});
    globalThis.AudioContext = function () {};
    if (sinks) globalThis.AudioContext.prototype.setSinkId = () => Promise.resolve();
    // The runtime's own Module: only its bridge is a stand-in.
    globalThis.Module.omnipythonBridge = bridge ? {
        route: (way, id) => { fake.routes.push(way + ':' + id); },
        routeError: (way) => { const e = fake.errors[way] || null; fake.errors[way] = null; return e; },
    } : undefined;
    fake.routed = () => fake.routes.join(',');
    return fake;
}"""


def fresh(labels=True, sinks=True, bridge=True):
    fake = js.eval(_FAKE)(labels, sinks, bridge)
    del endpoints._providers[:]
    reg = endpointkit.Registry()
    endpoints.register(reg)
    return fake, reg


async def settle(reg, rounds=4):
    for _ in range(rounds):
        await asyncio.sleep(0.01)
        reg.poll()


def labels(reg, kind):
    return [ep.label for ep in reg.endpoints(kind)]


@check
async def speakers_and_microphones_are_listed(air):
    fake, reg = fresh()
    await settle(reg)
    expect(labels(reg, "audio.out") == ["System default", "Speakers", "Headphones"], "out: %r" % labels(reg, "audio.out"))
    expect(labels(reg, "audio.in") == ["System default", "USB Mic"], "in: %r" % labels(reg, "audio.in"))


@check
async def unnamed_devices_get_numbers(air):
    fake, reg = fresh(labels=False)
    await settle(reg)
    expect(labels(reg, "audio.out") == ["System default", "Speaker 1", "Speaker 2"], "out: %r" % labels(reg, "audio.out"))
    expect(labels(reg, "audio.in") == ["System default", "Microphone 1"], "in: %r" % labels(reg, "audio.in"))


@check
async def choosing_a_speaker_routes_the_page(air):
    fake, reg = fresh()
    await settle(reg)
    reg.select("audio.out", "page-out:Headphones")
    expect(fake.routed() == "out:hp", "routes %s" % fake.routed())
    reg.select("audio.out", "page-out:default")
    expect(fake.routed().endswith("out:"), "back to the default: %s" % fake.routed())
    reg.select("audio.in", "page-in:USB Mic")
    expect(fake.routed().endswith("in:mic"), "microphone: %s" % fake.routed())


@check
async def a_device_plugged_in_later_appears(air):
    fake, reg = fresh()
    await settle(reg)
    fake.plug("audiooutput", "bt", "Bluetooth Speaker")
    await settle(reg)
    expect("Bluetooth Speaker" in labels(reg, "audio.out"), "out: %r" % labels(reg, "audio.out"))
    fake.unplug("bt")
    await settle(reg)
    expect("Bluetooth Speaker" not in labels(reg, "audio.out"), "after unplugging: %r" % labels(reg, "audio.out"))


@check
async def a_saved_choice_routes_once_listed(air):
    fake, reg = fresh()
    reg.select("audio.out", "page-out:Headphones")  # before the list has come back
    await settle(reg)
    expect(fake.routed().endswith("out:hp"), "routes %s" % fake.routed())


@check
async def no_sink_choice_lists_the_default_alone(air):
    fake, reg = fresh(sinks=False)
    await settle(reg)
    eps = reg.endpoints("audio.out")
    expect([ep.label for ep in eps] == ["System default"], "out: %r" % labels(reg, "audio.out"))
    expect("default speaker" in eps[0].caps.get("why", ""), "why %r" % eps[0].caps.get("why"))
    expect(labels(reg, "audio.in") == ["System default", "USB Mic"], "microphones still: %r" % labels(reg, "audio.in"))


@check
async def an_older_runtime_lists_the_default_alone(air):
    fake, reg = fresh(bridge=False)
    await settle(reg)
    expect(labels(reg, "audio.out") == ["System default"], "out: %r" % labels(reg, "audio.out"))
    reg.select("audio.out", "page-out:default")
    expect(fake.routed() == "", "routed %s" % fake.routed())
