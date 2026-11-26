# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""A browser page's MIDI ports in endpointkit, against a fake Web MIDI.

Runs on the MicroPython WebAssembly build under node (``wasm_node_run.mjs``),
where ``js`` is the real FFI and the fake ``navigator.requestMIDIAccess`` is
JavaScript, so promises settle between the checks' awaits as they do on a
page. Each check is a coroutine taking an ``Air``, as the runner expects.
"""

import sys

try:
    _here = __file__
except NameError:  # pragma: no cover
    _here = sys.argv[0]
_dir = _here.rsplit("/", 1)[0] if "/" in _here else "."
sys.path.insert(0, _dir + "/../packages/endpointkit")
sys.path.insert(0, _dir + "/../packages/midiports")

import asyncio

import js

import endpointkit
from midiports import endpoints, webmidi

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


# A Web MIDI stand-in: two ports a direction, a permission, and an answer.
_FAKE = """(permission, answer, present) => {
    class Port {
        constructor(type, id, name) {
            Object.assign(this, {type, id, name, state: 'connected', sent: [], opened: 0});
            this.heard = {};
        }
        addEventListener(type, fn) { (this.heard[type] ||= new Set()).add(fn); }
        removeEventListener(type, fn) { this.heard[type]?.delete(fn); }
        open() { this.opened++; return Promise.resolve(this); }
        send(data) { this.sent.push(Array.from(data)); }
        fire(bytes, ms) { for (const fn of this.heard.midimessage || []) fn({data: new Uint8Array(bytes), timeStamp: ms}); }
    }
    const access = {
        inputs: new Map(), outputs: new Map(), heard: {},
        addEventListener(type, fn) { (this.heard[type] ||= new Set()).add(fn); },
        removeEventListener(type, fn) { this.heard[type]?.delete(fn); },
    };
    const fake = {access, asked: 0};
    const status = {state: permission, onchange: null};
    fake.grant = () => { status.state = 'granted'; if (status.onchange) status.onchange(); };
    fake.plug = (type, id, name) => {
        const map = type === 'input' ? access.inputs : access.outputs;
        let port = map.get(id);
        if (!port) { port = new Port(type, id, name); map.set(id, port); }
        port.state = 'connected';
        for (const fn of access.heard.statechange || []) fn({port});
        return port;
    };
    fake.unplug = (type, id) => {
        const port = (type === 'input' ? access.inputs : access.outputs).get(id);
        port.state = 'disconnected';
        for (const fn of access.heard.statechange || []) fn({port});
    };
    fake.sent = (id) => JSON.stringify(access.outputs.get(id).sent);
    fake.plug('input', 'i1', 'Keys');
    fake.plug('input', 'i2', 'Pads');
    fake.plug('output', 'o1', 'Synth');
    fake.plug('output', 'o2', 'Loopback');
    const nav = present ? {
        requestMIDIAccess: () => {
            fake.asked++;
            return answer === 'yes' ? Promise.resolve(access) : Promise.reject(new Error('Permission denied'));
        },
        permissions: {query: () => Promise.resolve(status)},
    } : {};
    Object.defineProperty(globalThis, 'navigator', {value: nav, configurable: true, writable: true});
    return fake;
}"""


def fresh(permission="prompt", answer="yes", present=True):
    """A new fake page and a new registry with the page's MIDI registered."""
    fake = js.eval(_FAKE)(permission, answer, present)
    webmidi._access.clear()
    endpoints._providers.clear()
    reg = endpointkit.Registry()
    ins, outs = endpoints.register(reg)
    return fake, reg, ins, outs


async def settle(reg, rounds=5):
    for _ in range(rounds):
        await asyncio.sleep(0.01)
        reg.poll()


def labels(reg, kind):
    return [(ep.label, ep.state) for ep in reg.endpoints(kind)]


@check
async def no_web_midi_says_so(air):
    fake, reg, ins, outs = fresh(present=False)
    await settle(reg)
    for kind in ("midi.in", "midi.out"):
        eps = reg.endpoints(kind)
        expect(len(eps) == 1, "%s lists %r" % (kind, eps))
        expect(eps[0].state == endpointkit.UNAVAILABLE, "%s is %s" % (kind, eps[0].state))
        expect(eps[0].caps.get("why") == "This browser has no Web MIDI", "why %r" % eps[0].caps.get("why"))
    reg.select("midi.in", "webmidi-midi-in:allow")
    expect(reg.find("webmidi-midi-in:allow").error, "choosing it is refused")


@check
async def asks_only_when_tapped(air):
    fake, reg, ins, outs = fresh(permission="prompt")
    await settle(reg)
    expect(fake.asked == 0, "the browser was asked before anyone tapped")
    allow = reg.endpoints("midi.in")
    expect(len(allow) == 1 and allow[0].state == endpointkit.NEEDS_PAIRING, "before: %r" % allow)
    expect(allow[0].caps.get("grant") is True, "it's a browser grant")
    reg.pair(allow[0].id)
    await settle(reg)
    expect(fake.asked == 1, "asked %d times" % fake.asked)
    expect(labels(reg, "midi.in") == [("Keys", "available"), ("Pads", "available")], "in: %r" % labels(reg, "midi.in"))
    expect(labels(reg, "midi.out") == [("Synth", "available"), ("Loopback", "available")], "out: %r" % labels(reg, "midi.out"))


@check
async def allowed_before_lists_at_once(air):
    fake, reg, ins, outs = fresh(permission="granted")
    await settle(reg)
    expect(fake.asked == 1, "asked %d times" % fake.asked)
    expect([l for l, _ in labels(reg, "midi.in")] == ["Keys", "Pads"], "in: %r" % labels(reg, "midi.in"))


@check
async def allowed_elsewhere_lists_at_once(air):
    fake, reg, ins, outs = fresh(permission="prompt")
    await settle(reg)
    expect(fake.asked == 0, "asked before anything allowed it")
    fake.grant()  # another request on the page, or the site settings
    await settle(reg)
    expect([l for l, _ in labels(reg, "midi.out")] == ["Synth", "Loopback"], "out: %r" % labels(reg, "midi.out"))


@check
async def refused_says_why(air):
    fake, reg, ins, outs = fresh(answer="no")
    await settle(reg)
    reg.pair("webmidi-midi-out:allow")
    await settle(reg)
    ep = reg.find("webmidi-midi-out:allow")
    expect(ep is not None and ep.state == endpointkit.UNAVAILABLE, "after no: %r" % ep)
    expect("denied" in ep.caps.get("why", ""), "why %r" % ep.caps.get("why"))


@check
async def chosen_input_reads_with_stamps(air):
    fake, reg, ins, outs = fresh(permission="granted")
    await settle(reg)
    reg.select("midi.in", "webmidi-midi-in:Pads")
    merged = endpoints.merged_in()
    expect(reg.find("webmidi-midi-in:Pads").state == endpointkit.CONNECTED, "Pads connected")
    fake.access.inputs.get("i1").fire([0x90, 60, 100], 1.0)  # Keys isn't chosen
    fake.access.inputs.get("i2").fire([0x90, 64, 90], 2.5)
    fake.access.inputs.get("i2").fire([0x80, 64, 0], 3.0)
    got = merged.read()
    expect(got == b"\x90\x40\x5a\x80\x40\x00", "read %r" % (got,))
    expect(merged.take_timestamp() == 2500, "first stamp")
    expect(merged.take_timestamp() == 3000, "second stamp")
    expect(fake.access.inputs.get("i2").opened >= 1, "the port was opened")


@check
async def replugged_input_is_read_again(air):
    fake, reg, ins, outs = fresh(permission="granted")
    await settle(reg)
    reg.select("midi.in", "webmidi-midi-in:Keys")
    merged = endpoints.merged_in()
    fake.unplug("input", "i1")
    await settle(reg)
    expect(reg.find("webmidi-midi-in:Keys") is None, "gone while unplugged")
    expect(reg.chosen("midi.in") == ["webmidi-midi-in:Keys"], "still chosen")
    fake.plug("input", "i1", "Keys")
    await settle(reg)
    fake.access.inputs.get("i1").fire([0xB0, 7, 127], 9.0)
    expect(merged.read() == b"\xb0\x07\x7f", "read after the replug")


@check
async def chosen_outputs_hear_whole_messages(air):
    fake, reg, ins, outs = fresh(permission="granted")
    await settle(reg)
    reg.select("midi.out", ["webmidi-midi-out:Synth", "webmidi-midi-out:Loopback"])
    out = endpoints.fan_out()
    out.write(b"\x90\x3c")  # half a note: held
    expect(fake.sent("o1") == "[]", "half a message went out")
    out.write(b"\x64")
    expect(fake.sent("o1") == "[[144,60,100]]", "Synth got %s" % fake.sent("o1"))
    expect(fake.sent("o2") == "[[144,60,100]]", "Loopback got %s" % fake.sent("o2"))
    reg.select("midi.out", "webmidi-midi-out:Synth")
    out.write(b"\x80\x3c\x00")
    expect(fake.sent("o2") == "[[144,60,100]]", "a port let go still hears")
