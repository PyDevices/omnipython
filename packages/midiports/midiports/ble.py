# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""MIDI over Bluetooth LE: the board as a BLE-MIDI instrument that a keyboard,
a phone or a computer connects to and plays.

::

    from midiports import ble

    if ble.available():
        midi_in, midi_out = ble.ports("Synth")

The board advertises the standard BLE-MIDI service as ``name`` (the board's
name when you pass none), and a BLE-MIDI controller, a phone app or a
computer's MIDI settings connect to it. When the link drops, the board
advertises again, so the next connection needs nothing from your program.
Nothing about Bluetooth starts until you call `ports`: `available` only asks
whether the firmware has it.

The ports keep the package's contract. ``read``, ``readinto`` and ``any``
never block and hand out whole messages, running status expanded, SysEx in
one piece. When a link drops with notes still sounding, the input hands out a
note-off for each of them, and a sustain-pedal release for each channel that
had the pedal down, so no note is left hanging; so does closing the port, or
the link stopping on an error, and those last messages can still be read. ``take_timestamp`` gives each
message's arrival time: the time the board picked up its packet, less how much
earlier the sender stamped it than the packet's last message, so notes sent
together in one packet keep their spacing.

Bluetooth here runs on ``asyncio``, as ``bledev`` does. A program with no event
loop of its own, such as an app polling from a timer, needs nothing more: each
``any()`` runs the loop's waiting tasks once, at most every ``pump_ms``. A
program that runs an event loop calls `ports` from inside it, and the loop runs
the tasks.

``state`` says what the link is doing: ``"advertising"``, ``"connected"`` or
``"closed"``. ``error`` holds what stopped it, if something did, and
``any()`` raises it once what arrived before it has been read.

Needs ``bledev`` and a firmware with Bluetooth LE: MicroPython with
``aioble``, or CircuitPython. A computer's own Bluetooth MIDI devices
appear among its MIDI ports instead (the ``windows`` and ``linux`` modules
here), once the operating system has paired them.
"""

import sys
import time

import asyncio

from . import INOUT, PortIn, PortOut, Stamps, _stamp, ticks_us
from . import ticks_add as _ticks_add

#: Messages waiting for a reader before the oldest are dropped and counted.
QUEUE_LIMIT = 256
#: The shortest time between two runs of the event loop's waiting tasks.
PUMP_MS = 4
#: How often the link is checked for a drop, in milliseconds.
WATCH_MS = 100

_MASK = 0x1FFF  # BLE-MIDI timestamps: 13 bits of milliseconds


if hasattr(time, "ticks_ms"):
    _ticks_ms = time.ticks_ms
    _ms_since = time.ticks_diff
else:

    def _ticks_ms():
        return int(time.monotonic() * 1000)

    def _ms_since(end, start):
        return end - start


def available():
    """True when this board's firmware has Bluetooth LE for `ports`.

    It imports the firmware's Bluetooth module and starts nothing. On a
    computer or in a browser it's False: there, a Bluetooth MIDI device the
    system has paired is one of its MIDI ports.
    """
    if sys.implementation.name not in ("micropython", "circuitpython"):
        return False
    if sys.platform in ("webassembly", "emscripten"):
        return False
    for name in ("bluetooth", "_bleio"):
        try:
            __import__(name)
            return True
        except ImportError:
            pass
    return False


def _loop_running():
    try:
        if hasattr(asyncio, "get_running_loop"):
            asyncio.get_running_loop()
        else:
            asyncio.current_task()
        return True
    except RuntimeError:
        return False


if hasattr(asyncio, "sleep_ms"):
    _sleep_ms = asyncio.sleep_ms
else:

    def _sleep_ms(ms):
        return asyncio.sleep(ms / 1000)


async def _yield():
    await _sleep_ms(0)


class _Held:
    """Which notes are sounding and which channels hold the sustain pedal, from
    the messages handed out, so a dropped link can let them all go."""

    def __init__(self):
        self.notes = bytearray(16 * 16)  # a bit per note, 16 bytes per channel
        self.pedal = 0  # a bit per channel

    def see(self, msg):
        status = msg[0]
        kind = status & 0xF0
        ch = status & 0x0F
        if kind == 0x90 and len(msg) == 3:
            i = ch * 16 + (msg[1] >> 3)
            bit = 1 << (msg[1] & 7)
            if msg[2]:
                self.notes[i] |= bit
            else:
                self.notes[i] &= ~bit & 0xFF
        elif kind == 0x80 and len(msg) == 3:
            self.notes[ch * 16 + (msg[1] >> 3)] &= ~(1 << (msg[1] & 7)) & 0xFF
        elif kind == 0xB0 and len(msg) == 3:
            if msg[1] == 64:
                if msg[2] >= 64:
                    self.pedal |= 1 << ch
                else:
                    self.pedal &= ~(1 << ch)
            elif msg[1] in (120, 123):  # all sound off, all notes off
                for i in range(ch * 16, ch * 16 + 16):
                    self.notes[i] = 0

    def release(self):
        """The messages that let go of everything held, and forget it."""
        out = []
        notes = self.notes
        for ch in range(16):
            for i in range(16):
                bits = notes[ch * 16 + i]
                if bits:
                    for b in range(8):
                        if bits & (1 << b):
                            out.append(bytes((0x80 | ch, i * 8 + b, 0)))
                    notes[ch * 16 + i] = 0
            if self.pedal & (1 << ch):
                out.append(bytes((0xB0 | ch, 64, 0)))
        self.pedal = 0
        return out


class BleIn(PortIn):
    """The input port `ports` makes, and the link behind both ports.

    ``name`` is what the board advertises, ``state`` what the link is doing,
    ``peer`` the address of the device connected (``None`` when none is),
    ``links`` how many connections it has had, ``dropped`` how many messages
    were lost because nothing read them, and ``error`` what stopped the link.
    """

    def __init__(self, name, ble, *, pump=None, pump_ms=PUMP_MS, queue_limit=QUEUE_LIMIT, stamps=64):
        PortIn.__init__(self)
        import bledev.midi

        self._midi = bledev.midi
        self.name = name
        self.direction = INOUT
        self.state = "advertising"
        self.peer = None
        self.links = 0
        self.dropped = 0
        self.error = None
        self.queue_limit = queue_limit
        self._ble = ble
        self._port = None
        self._held = _Held()
        self._msgs = []
        self._pending = b""
        self._pos = 0
        self._waiting = 0
        self._stamps = Stamps(stamps)
        self._closed = False
        #: Whether closing turns the radio off: `ports` found it off.
        self.radio_off = False
        self._pump = (not _loop_running()) if pump is None else pump
        if self._pump and sys.implementation.name not in ("micropython", "circuitpython"):
            raise RuntimeError("on CPython, open BLE MIDI ports from inside a running asyncio loop")
        self._pump_ms = pump_ms
        self._pumped = _ticks_ms()
        self._task = asyncio.create_task(self._keep())
        if self._pump:
            asyncio.run(_yield())  # starts advertising now, not at the first poll

    # -- the link

    async def _keep(self):
        midi = self._midi
        try:
            while not self._closed:
                self.state = "advertising"
                port = await midi.serve(self._ble, name=self.name)
                if self._closed:
                    port.close()
                    break
                self._port = port
                self.peer = port.connection.device.address
                self.links += 1
                self.state = "connected"
                while not self._closed and port.connection.is_connected():
                    await _sleep_ms(WATCH_MS)
                self._drain()  # what arrived before the drop comes first
                self._port = None
                self.peer = None
                self.dropped += port.dropped
                port.close()
                self._queue(self._held.release(), ticks_us())
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001 - kept, said by state, and raised by any()
            self.error = e
            self.state = "stopped: %s" % (e,)
            self._queue(self._held.release(), ticks_us())

    def _queue(self, messages, now):
        held = self._held
        for msg in messages:
            if len(self._msgs) >= self.queue_limit:
                self.dropped += 1
                continue
            held.see(msg)
            self._msgs.append(msg)
            self._waiting += len(msg)
            _stamp(self._stamps, msg[0], now)

    def _drain(self):
        """Take what the link has into the queue, each message stamped with
        when its packet came, less how much earlier its sender stamped it."""
        port = self._port
        if port is None:
            return
        item = port.take()
        if item is None:
            return
        now = ticks_us()
        items = []
        while item is not None:
            items.append(item)
            item = port.take()
        newest = items[-1][0]
        held = self._held
        for ts, msg in items:
            if len(self._msgs) >= self.queue_limit:
                self.dropped += 1
                continue
            held.see(msg)
            self._msgs.append(msg)
            self._waiting += len(msg)
            _stamp(self._stamps, msg[0], _ticks_add(now, -((newest - ts) & _MASK) * 1000))

    def _service(self):
        if self._pump and not self._closed:
            now = _ticks_ms()
            if _ms_since(now, self._pumped) >= self._pump_ms:
                self._pumped = now
                asyncio.run(_yield())
        self._drain()

    # -- the port contract

    def any(self):
        """How many MIDI bytes are waiting, after running the link's tasks.
        Raises what stopped the link once nothing is left to read."""
        if not self._closed and self.error is None:
            self._service()
        if not self._waiting and self.error is not None:
            raise self.error
        return self._waiting

    def readinto(self, buf, nbytes=None):
        """Waiting MIDI bytes into ``buf``, whole messages only; how many, or
        ``None``. A message bigger than the buffer comes out in parts."""
        if not self._waiting and not self.any():
            return None
        size = len(buf) if nbytes is None or nbytes > len(buf) else nbytes
        n = 0
        while n < size:
            pending = self._pending
            pos = self._pos
            if pos >= len(pending):
                if not self._msgs:
                    break
                if n and len(self._msgs[0]) > size - n:
                    break  # the next message won't fit whole: leave it for the next read
                pending = self._pending = self._msgs.pop(0)
                pos = 0
            end = min(len(pending), pos + size - n)
            while pos < end:
                buf[n] = pending[pos]
                n += 1
                pos += 1
            self._pos = pos
        self._waiting -= n
        return n or None

    def read(self, nbytes=None):
        """Waiting MIDI bytes as ``bytes``, or ``None``. A SysEx comes out in
        one piece when ``nbytes`` allows: the read buffer grows to hold the
        next message, so ``adafruit_midi``, which can't join a SysEx handed
        out in parts, gets a long one whole."""
        if not self._waiting and not self.any():
            return None
        pending = self._pending
        need = len(pending) - self._pos if self._pos < len(pending) else len(self._msgs[0])
        n = need if need > len(self._scratch) else len(self._scratch)
        return self._read(n if nbytes is None or nbytes > n else nbytes)

    def write(self, buf, nbytes=None):
        port = self._port
        if port is None:
            raise OSError("BLE MIDI: no device connected")
        return port.write(buf, nbytes)

    def close(self):
        """Stop advertising and drop the link. A note still sounding gets
        its note-off, left to be read. The radio goes back off if `ports`
        found it off."""
        if self._closed:
            return
        self._closed = True
        self.state = "closed"
        self._drain()
        port = self._port
        self._port = None
        if port is not None:
            port.close()
        self._queue(self._held.release(), ticks_us())
        self._task.cancel()
        if self._pump:
            try:
                asyncio.run(_yield())  # lets the cancel and the disconnect run
            except Exception:  # noqa: BLE001 - closing either way
                pass
        if self.radio_off:
            _radio_stop(self._ble)

    deinit = close


class BleOut(PortOut):
    """The output port `ports` makes: it writes to whatever is connected, and
    raises ``OSError`` when nothing is."""

    def __init__(self, link):
        self.link = link

    def write(self, buf, nbytes=None):
        return self.link.write(buf, nbytes)

    def close(self):
        self.link.close()

    deinit = close


def ports(name=None, *, adapter=None, pump=None, pump_ms=PUMP_MS, queue_limit=QUEUE_LIMIT):
    """``(midi_in, midi_out)``: advertise BLE-MIDI as ``name`` and serve
    every connection, one at a time.

    Args:
        name: what the board advertises; the board's name when ``None``.
        adapter: a ``bledev`` adapter; ``bledev.auto.adapter()`` when ``None``.
        pump: whether ``any()`` runs the event loop's waiting tasks. ``None``
            decides from whether a loop is running when `ports` is called.
        pump_ms: the shortest time between two of those runs.
        queue_limit: messages kept for a reader that isn't reading.

    A radio that was off is turned on here, and turned off again when the
    input closes or fails to start, so its memory goes back to the board.

    Raises:
        ImportError: ``bledev`` (or MicroPython's ``aioble``) isn't installed.
    """
    import bledev.midi  # noqa: F401 - raises here, before anything starts, when it's missing

    was_on = _radio_on()
    try:
        if adapter is None:
            import bledev.auto

            adapter = bledev.auto.adapter()
        if name is None:
            import boarddev

            name = boarddev.name()
        link = BleIn(name, adapter, pump=pump, pump_ms=pump_ms, queue_limit=queue_limit)
    except Exception:
        # A radio that failed to start keeps what it took, internal RAM
        # the board's other drivers need, until it's turned off again.
        if was_on is False:
            _radio_stop(adapter)
        raise
    link.radio_off = was_on is False
    return link, BleOut(link)


def _radio_on():
    """Whether the radio is on, or None where asking would turn it on."""
    if sys.implementation.name != "micropython":
        return None
    try:
        import bluetooth
    except ImportError:  # a stand-in adapter on a build without a radio
        return None
    return bool(bluetooth.BLE().active())


def _radio_stop(adapter):
    if adapter is not None:
        adapter.close()
    else:
        import bluetooth

        bluetooth.BLE().active(False)
