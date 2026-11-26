# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""MIDI between browser tabs, through endpointkit, over a real BroadcastChannel.

Runs on the MicroPython WebAssembly build under node (``wasm_node_run.mjs``).
This runtime is one tab; the others are more copies of the same JavaScript
`midiports.tabs` runs, on the same channel, driven from here. Each check is
a coroutine taking an ``Air``, as the runner expects.
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
from midiports import endpoints, tabs, webmidi

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


# No Web MIDI on this page: only the tabs offer ports.
js.eval("(() => { Object.defineProperty(globalThis, 'navigator', {value: {}, configurable: true, writable: true}); })")()

_open = []


def other_tab(name):
    """Another tab on the channel, named *name*."""
    tab = js.eval(tabs._TABS)(tabs.CHANNEL, webmidi.PAGE_LIMIT, 50, 400)
    tab.setName(name)
    _open.append(tab)
    return tab


def fresh(name="MIDI Controller"):
    """This tab, named *name*, in a new registry; every other tab closed."""
    while _open:
        _open.pop().close()
    if tabs._page:
        tabs._page.pop().close()
    tabs.name_of = None
    tabs.HERE_MS, tabs.GONE_MS = 50, 400
    webmidi._access.clear()
    endpoints._providers.clear()
    reg = endpointkit.Registry()
    endpoints.register(reg)
    tabs.set_name(name)
    return reg


async def settle(reg, rounds=6):
    for _ in range(rounds):
        await asyncio.sleep(0.02)
        reg.poll()


def labels(reg, kind):
    return [ep.label for ep in reg.endpoints(kind) if ep.provider.name.startswith("tabs-")]


def received(port):
    out = []
    while port.any():
        out.append(port.next())
    return out


@check
async def other_tabs_are_listed_by_name(air):
    reg = fresh()
    other_tab("Synth Station")
    await settle(reg)
    expect(labels(reg, "midi.out") == ["Tab: Synth Station"], "out: %r" % labels(reg, "midi.out"))
    expect(labels(reg, "midi.in") == ["Tab: Synth Station"], "in: %r" % labels(reg, "midi.in"))


@check
async def a_tab_hears_this_ones_name(air):
    reg = fresh("Backline")
    peer = other_tab("Synth Station")
    await settle(reg)
    expect("\tBackline" in str(peer.list()), "the other tab lists %r" % str(peer.list()))
    tabs.name_of = lambda: "midiEngine"
    reg.poll()
    tabs.changes()
    await settle(reg)
    expect("\tmidiEngine" in str(peer.list()), "after name_of: %r" % str(peer.list()))


@check
async def the_chosen_tab_plays_and_no_other(air):
    reg = fresh()
    synth = other_tab("Synth Station")
    drums = other_tab("Backline")
    await settle(reg)
    heard = synth.openIn(None)
    not_heard = drums.openIn(None)
    reg.select("midi.out", "tabs-midi-out:Tab: Synth Station")
    out = endpoints.fan_out()
    out.write(b"\x90\x3c")
    out.write(b"\x64")
    await settle(reg)
    expect(received(heard) == [0x90, 60, 100], "the synth tab got %r" % received(heard))
    expect(received(not_heard) == [], "the drum tab heard it too")


@check
async def a_chosen_tab_input_reads(air):
    reg = fresh("Synth Station")
    keys = other_tab("MIDI Controller")
    pads = other_tab("Backline")
    await settle(reg)
    reg.select("midi.in", "tabs-midi-in:Tab: MIDI Controller")
    merged = endpoints.merged_in()
    me = tabs._tabs().me()
    for tab, data in ((keys, (0x90, 64, 90)), (pads, (0x99, 36, 127))):
        port = tab.openOut(me)
        for b in data:
            port.put(b)
        port.send()
    await settle(reg)
    expect(merged.read() == b"\x90\x40\x5a", "read the chosen tab only")
    expect(merged.read() is None, "the other tab came through")


@check
async def page_in_hears_every_tab(air):
    reg = fresh("Synth Station")
    keys = other_tab("MIDI Controller")
    await settle(reg)
    every = tabs.page_in()
    expect(every.names == ["Tab: MIDI Controller"], "names %r" % (every.names,))
    port = keys.openOut(tabs._tabs().me())
    for b in (0xB0, 7, 100):
        port.put(b)
    port.send()
    await settle(reg)
    expect(every.read() == b"\xb0\x07\x64", "page_in")
    every.close()


@check
async def a_closed_tab_goes(air):
    reg = fresh()
    synth = other_tab("Synth Station")
    await settle(reg)
    reg.select("midi.out", "tabs-midi-out:Tab: Synth Station")
    synth.close()
    _open.remove(synth)
    await settle(reg)
    expect(labels(reg, "midi.out") == [], "still listed: %r" % labels(reg, "midi.out"))
    expect(reg.chosen("midi.out") == ["tabs-midi-out:Tab: Synth Station"], "the choice is kept")


@check
async def a_silent_tab_is_dropped(air):
    reg = fresh()
    # A tab that says hello once and then nothing, as a frozen page would.
    js.eval("""(name) => { const c = new BroadcastChannel(name);
        c.postMessage({type: 'hello', from: 'ghost', name: 'Ghost'}); c.close(); }""")(tabs.CHANNEL)
    await settle(reg)
    expect(labels(reg, "midi.out") == ["Tab: Ghost"], "listed first: %r" % labels(reg, "midi.out"))
    await asyncio.sleep(0.6)
    await settle(reg)
    expect(labels(reg, "midi.out") == [], "still listed: %r" % labels(reg, "midi.out"))
