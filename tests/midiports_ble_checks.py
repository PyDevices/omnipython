# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""midiports' BLE MIDI port, checked over ``bledev.fake``.

A plain script, not unittest, so the same file runs on CPython and on
MicroPython::

    python tests/midiports_ble_checks.py
    micropython tests/midiports_ble_checks.py
    python tests/midiports_ble_checks.py --plant=no-release   # must FAIL

The board's side is ``midiports.ble.ports()`` on a fake peripheral; the other
side is ``bledev.midi.connect()`` on a fake central, the way a controller or a
phone connects. The packet format itself (timestamps, running status, SysEx
across packets) is checked against hand-worked vectors in
``bledev_midi_codec.py``; these checks follow it through to the port: whole
messages out, arrival stamps that keep a packet's spacing, and notes let go
when the link drops.

``--plant=NAME`` breaks the port one way (see ``PLANTS``) to show a check
catches it. ``tests/test_midiports.py`` runs this every way.
"""

import sys

try:
    _here = __file__
except NameError:  # pragma: no cover
    _here = sys.argv[0]
_sep = "\\" if "\\" in _here else "/"
_dir = _here.rsplit(_sep, 1)[0] if _sep in _here else "."
sys.path.insert(0, _dir + _sep + ".." + _sep + "lib")
sys.path.insert(0, _dir + _sep + ".." + _sep + "packages" + _sep + "midiports")

import asyncio

from bledev import midi
from bledev.fake import Air, FakeBLE

import midiports
from midiports import ble

MICROPYTHON = sys.implementation.name == "micropython"
CHECK_TIMEOUT_S = 10
NAME = "synth"

#: Faults the checks must catch.
PLANTS = ("no-release", "flat-stamps", "split-message")

TESTS = []


def check(fn):
    TESTS.append(fn)
    return fn


class Failed(Exception):
    pass


def expect(cond, message="expectation failed"):
    if not cond:
        raise Failed(message)


def equal(a, b, what="value"):
    if a != b:
        raise Failed("%s: %r != %r" % (what, a, b))


def _plant(name):
    if name == "no-release":
        ble._Held.release = lambda self: []
    elif name == "flat-stamps":
        ble._ticks_add = lambda t, d: t
    elif name == "split-message":
        def take(self, _take=midi.Port.take):
            item = _take(self)
            if item is not None and len(item[1]) == 3:
                return item[0], item[1][:2]
            return item

        midi.Port.take = take
    else:
        raise SystemExit("no plant %r" % name)


async def pair(air, mtu=midi.MTU):
    """The board's ports and a controller connected to them."""
    board = FakeBLE(air=air)
    controller = FakeBLE(air=air, peripheral=False)
    midi_in, midi_out = ble.ports(NAME, adapter=board)
    expect(not midi_in._pump, "ports() inside a loop leaves the loop to run the tasks")
    equal(midi_in.state, "advertising", "state before a connection")
    client = await midi.connect(controller, name=NAME, mtu=mtu, timeout_ms=2000)
    await until(lambda: midi_in.state == "connected")
    return midi_in, midi_out, client, controller


async def until(cond, ms=2000):
    for _ in range(ms):
        if cond():
            return
        await asyncio.sleep(0.001)
    raise Failed("waited %d ms" % ms)


async def messages(port, n, ms=3000, buf=None):
    """``n`` whole messages read from ``port``."""
    buf = buf or bytearray(64)
    out = []
    for _ in range(ms):
        while True:
            k = port.readinto(buf)
            if not k:
                break
            out.extend(split(bytes(buf[:k])))
        if len(out) >= n:
            return out
        await asyncio.sleep(0.001)
    raise Failed("%d of %d messages came" % (len(out), n))


def split(data):
    """Whole messages from bytes a port handed out, checking each is whole."""
    out = []
    i = 0
    while i < len(data):
        status = data[i]
        expect(status >= 0x80, "a read starts with a status byte, not %02x" % status)
        if status == 0xF0:
            end = data.index(b"\xf7", i) + 1
        else:
            end = i + 1 + midiports.message_length(status)
        expect(end <= len(data), "a message split across reads: %s" % data[i:].hex() if hasattr(data, "hex") else "split")
        out.append(data[i:end])
        i = end
    return out


@check
async def available_is_false_without_a_radio(air):
    import sys as _sys

    has = False
    for name in ("bluetooth", "_bleio"):
        try:
            __import__(name)
            has = True
        except ImportError:
            pass
    equal(ble.available(), has and _sys.implementation.name != "cpython", "available()")


@check
async def nothing_waits_before_a_connection(air):
    midi_in, midi_out, client, _ = await pair(air)
    equal(midi_in.any(), 0, "any() with nothing sent")
    equal(midi_in.read(), None, "read() with nothing sent")
    equal(midi_in.readinto(bytearray(8)), None, "readinto() with nothing sent")
    equal(midi_in.take_timestamp(), None, "no stamp with nothing sent")
    equal(midi_in.links, 1, "one link")
    midi_in.close()


@check
async def running_status_comes_out_whole(air):
    midi_in, _, client, _ = await pair(air)
    client.write(b"\x90\x3c\x64\x3e\x50\xc0\x05\x07")  # running status, and a one-byte one
    got = await messages(midi_in, 4)
    equal(got, [b"\x90\x3c\x64", b"\x90\x3e\x50", b"\xc0\x05", b"\xc0\x07"], "messages")
    for _ in range(4):
        expect(midi_in.take_timestamp() is not None, "a stamp for each message")
    equal(midi_in.take_timestamp(), None, "no more stamps than messages")
    midi_in.close()


@check
async def a_packets_spacing_survives_in_its_stamps(air):
    midi_in, _, client, _ = await pair(air)
    # Three notes in one packet, stamped 0, 10 and 30 ms apart on the
    # sender's clock, across the 13-bit wrap.
    for ts, note in ((8180, 60), (8190, 64), (18, 67)):
        client.send(bytes((0x90, note, 100)), timestamp=ts)
    await messages(midi_in, 3)
    a, b, c = midi_in.take_timestamp(), midi_in.take_timestamp(), midi_in.take_timestamp()
    equal(midiports.ticks_diff(b, a), 10000, "10 ms between the first two")
    equal(midiports.ticks_diff(c, b), 20000, "20 ms, across the wrap")
    midi_in.close()


@check
async def sysex_across_packets_is_one_message(air):
    midi_in, _, client, _ = await pair(air, mtu=23)
    sysex = bytes([0xF0] + [i % 128 for i in range(300)] + [0xF7])
    client.write(sysex + b"\x90\x40\x40")
    got = await messages(midi_in, 2, buf=bytearray(400))
    equal(got, [sysex, b"\x90\x40\x40"], "a 302-byte SysEx at MTU 23, then a note")
    midi_in.close()


@check
async def four_hundred_notes_and_a_hundred_chords_arrive(air):
    midi_in, _, client, _ = await pair(air)
    sent = []
    for i in range(400):
        sent.append(bytes((0x90 | (i % 16), 36 + i % 60, 1 + i % 127)))
        sent.append(bytes((0x80 | (i % 16), 36 + i % 60, 0)))
    for i in range(100):
        root = 40 + i % 30
        for k in (0, 4, 7, 12):
            sent.append(bytes((0x91, root + k, 90)))
        for k in (0, 4, 7, 12):
            sent.append(bytes((0x81, root + k, 0)))
    got = []
    for i in range(0, len(sent), 16):
        client.write(b"".join(sent[i:i + 16]))
        got.extend(await messages(midi_in, 0, ms=1))
        await asyncio.sleep(0.002)
    await client.drain()
    got.extend(await messages(midi_in, len(sent) - len(got)))
    equal(len(got), len(sent), "message count")
    equal(got, sent, "every message, in order")
    equal(midi_in.dropped, 0, "dropped")
    midi_in.close()


@check
async def a_dropped_link_lets_every_held_note_go(air):
    midi_in, _, client, controller = await pair(air)
    client.write(b"\x90\x3c\x64\x40\x64\xb0\x40\x7f\x92\x43\x50\x90\x3e\x40\x80\x3e\x00\x93\x30\x40\x93\x30\x00")
    await messages(midi_in, 7)
    while midi_in.take_timestamp() is not None:
        pass
    await client.aclose()  # the controller goes, notes 60 and 64 (pedal down) and 67 still on
    got = await messages(midi_in, 4)
    equal(got, [b"\x80\x3c\x00", b"\x80\x40\x00", b"\xb0\x40\x00", b"\x82\x43\x00"], "note-offs and pedal up after the drop")
    expect(midi_in.take_timestamp() is not None, "the note-offs are stamped")
    await until(lambda: midi_in.state == "advertising")
    # It advertises again, and the next controller plays.
    client = await midi.connect(controller, name=NAME, timeout_ms=2000)
    await until(lambda: midi_in.state == "connected")
    equal(midi_in.links, 2, "a second link")
    client.write(b"\x90\x45\x60")
    equal(await messages(midi_in, 1), [b"\x90\x45\x60"], "the next controller's note")
    midi_in.close()
    equal(midi_in.state, "closed", "state after close")
    equal(await messages(midi_in, 1), [b"\x80\x45\x00"], "the note-off closing left")
    equal(midi_in.any(), 0, "then a closed port has nothing")


@check
async def closing_lets_every_held_note_go(air):
    midi_in, _, client, _ = await pair(air)
    client.write(b"\x90\x3c\x64\xb3\x40\x7f")
    await messages(midi_in, 2)
    midi_in.close()  # notes 60 and the pedal on channel 4 still down
    equal(await messages(midi_in, 2), [b"\x80\x3c\x00", b"\xb3\x40\x00"], "note-off and pedal up after close")
    equal(midi_in.any(), 0, "then nothing")


@check
async def the_output_reaches_the_controller(air):
    midi_in, midi_out, client, _ = await pair(air)
    midi_out.write(b"\xb0\x07\x40")
    ts, message = await client.receive(timeout_ms=1000)
    equal(message, b"\xb0\x07\x40", "board -> controller")
    midi_in.close()
    try:
        midi_out.write(b"\x90\x3c\x40")
    except OSError:
        pass
    else:
        raise Failed("a write with nothing connected raises")


@check
async def a_failure_is_raised_not_hidden(air):
    class Broken(FakeBLE):
        async def advertise(self, *args, **kwargs):
            raise OSError(19, "radio gone")

    midi_in, _ = ble.ports(NAME, adapter=Broken(air=air))
    await asyncio.sleep(0.01)
    expect(midi_in.state.startswith("stopped"), "state says it stopped: %r" % midi_in.state)
    for _ in range(2):  # and keeps saying so
        try:
            midi_in.any()
        except OSError:
            pass
        else:
            raise Failed("any() raises what stopped the link")


def pumped(air):
    """With no loop running, ``any()`` runs the link's tasks itself, as an
    app polling from a timer needs (MicroPython: one event loop for all)."""
    board = FakeBLE(air=air)
    controller = FakeBLE(air=air, peripheral=False)
    midi_in, _ = ble.ports(NAME, adapter=board, pump_ms=0)
    expect(midi_in._pump, "ports() outside a loop runs the tasks itself")
    box = {}

    async def play():
        client = await midi.connect(controller, name=NAME, timeout_ms=2000)
        client.write(b"\x90\x3c\x64\x40\x64")
        await client.drain()
        box["client"] = client

    task = asyncio.create_task(play())
    got = []
    buf = bytearray(16)
    for _ in range(5000):
        k = midi_in.readinto(buf)
        if k:
            got.extend(split(bytes(buf[:k])))
        if len(got) >= 2:
            break
    equal(got, [b"\x90\x3c\x64", b"\x90\x40\x64"], "notes read by polling alone")
    equal(midi_in.state, "connected", "state")
    task.cancel()
    midi_in.close()


def run(only=None):
    failed = 0
    count = 0
    for fn in TESTS:
        if only and fn.__name__ not in only:
            continue
        count += 1
        if MICROPYTHON:
            asyncio.new_event_loop()
        try:
            asyncio.run(asyncio.wait_for(fn(Air()), CHECK_TIMEOUT_S))
        except Exception as e:
            failed += 1
            print("FAIL", fn.__name__, "-", type(e).__name__, e)
        else:
            print("PASS", fn.__name__)
    if MICROPYTHON and (not only or "pumped" in only):
        count += 1
        asyncio.new_event_loop()
        try:
            pumped(Air())
        except Exception as e:
            failed += 1
            print("FAIL pumped -", type(e).__name__, e)
        else:
            print("PASS pumped")
    print("%d checks, %d failed (%s)" % (count, failed, sys.implementation.name))
    return failed


def main(argv):
    only = []
    for arg in argv:
        if arg.startswith("--plant="):
            _plant(arg.split("=", 1)[1])
            print("PLANTED", arg.split("=", 1)[1])
        else:
            only.append(arg)
    sys.exit(1 if run(only) else 0)


if __name__ == "__main__":
    main(sys.argv[1:])
