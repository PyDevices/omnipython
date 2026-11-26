# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""A browser page's gamepads in endpointkit, against a fake Gamepad API.

Runs on the MicroPython WebAssembly build under node (``wasm_node_run.mjs``),
where ``js`` is the real FFI and ``navigator.getGamepads`` is a JavaScript
stand-in.
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
from displaydev import endpoints

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


_FAKE = """(present) => {
    const pads = [];
    const fake = {};
    fake.plug = (index, id) => { pads[index] = {index, id, connected: true, mapping: 'standard', buttons: [], axes: []}; };
    fake.unplug = (index) => { pads[index] = null; };
    Object.defineProperty(globalThis, 'navigator', {configurable: true, writable: true,
        value: present ? {getGamepads: () => pads.slice()} : {}});
    return fake;
}"""


def fresh(present=True):
    fake = js.eval(_FAKE)(present)
    del endpoints._providers[:]
    reg = endpointkit.Registry()
    endpoints.register(reg)
    for p in endpoints._providers:
        p.rescan_ms = 0
    return fake, reg


async def settle(reg, rounds=3):
    for _ in range(rounds):
        await asyncio.sleep(0.01)
        reg.poll()


def labels(reg):
    return [ep.label for ep in reg.endpoints("gamepad")]


@check
async def no_pads_until_a_button_is_pressed(air):
    fake, reg = fresh()
    await settle(reg)
    expect(labels(reg) == [], "pads: %r" % labels(reg))


@check
async def pads_the_browser_shows_are_listed(air):
    fake, reg = fresh()
    fake.plug(0, "Xbox Wireless Controller")
    fake.plug(2, "8BitDo Pro 2")
    await settle(reg)
    expect(labels(reg) == ["Xbox Wireless Controller", "8BitDo Pro 2"], "pads: %r" % labels(reg))


@check
async def two_of_the_same_pad_are_told_apart(air):
    fake, reg = fresh()
    fake.plug(0, "Pad")
    fake.plug(1, "Pad")
    await settle(reg)
    expect(labels(reg) == ["Pad", "Pad #2"], "pads: %r" % labels(reg))


@check
async def an_unplugged_pad_goes_and_its_choice_stays(air):
    fake, reg = fresh()
    fake.plug(0, "Xbox Wireless Controller")
    await settle(reg)
    reg.select("gamepad", "host-gamepad:Xbox Wireless Controller")
    fake.unplug(0)
    await settle(reg)
    expect(labels(reg) == [], "pads: %r" % labels(reg))
    expect(reg.chosen("gamepad") == ["host-gamepad:Xbox Wireless Controller"], "chosen %r" % reg.chosen("gamepad"))


@check
async def no_gamepad_api_lists_none(air):
    fake, reg = fresh(present=False)
    await settle(reg)
    expect(labels(reg) == [], "pads: %r" % labels(reg))
