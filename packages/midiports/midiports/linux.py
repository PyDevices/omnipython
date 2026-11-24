# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""MIDI through Linux's ALSA, from CPython or MicroPython.

A USB keyboard, a board plugged in as a MIDI device, a virtual port
(``snd-virmidi``), a Bluetooth MIDI device BlueZ has connected, or another
program's MIDI port is a port here::

    from midiports import linux

    midi_in, midi_out = linux.ports("DMK25")

``ports(name)`` opens the first input and the first output whose names
contain ``name`` (case doesn't matter); either is ``None`` if there's no such
port in that direction. Its input is wrapped in ``midiports.WholeMessages``,
since raw MIDI from a 5-pin interface can carry running status. ``available()`` lists every port, and ``open_port()``
opens one.

There are two kinds of port. A raw MIDI device (``/dev/snd/midiC*D*``) is
what a USB or 5-pin interface is. A sequencer port is what a program makes:
a DAW, a software synth, ``Midi Through``, and BlueZ, which turns each
BLE-MIDI device it connects to into a port named after the device, such as
``"THMI-MIDI Bluetooth"``. To reach a BLE-MIDI device that way, connect it
first, with ``bluetoothctl connect ADDRESS`` or your desktop's Bluetooth
settings, then open it by name. Sequencer ports owned by the kernel's sound
cards aren't listed, since the same device is listed as raw MIDI.

It reads the kernel's own files (``/proc/asound``, ``/dev/snd/midiC*D*`` and
``/dev/snd/seq``) rather than linking ``libasound``, so it needs no packages,
only membership of the ``audio`` group that owns them, which a desktop login
has. MicroPython's and CircuitPython's unix ports have no ``os.open`` or
``os.read``, so there a raw MIDI port is the builtin ``open()`` and
``select.poll`` tells an input when a read would find something: the same
ports, listed and opened the same way. A sequencer port needs ``ioctl``:
CPython has it in ``fcntl``, MicroPython's unix port reaches the C library's
through ``ffi``, and CircuitPython's unix port has neither, so it lists no
sequencer ports. (``serial_ports`` needs CPython's ``termios``.)

A 5-pin DIN socket wired to a serial port (a Raspberry Pi's UART, a USB
serial adapter) isn't an ALSA device. ``serial_ports(path)`` opens it at
MIDI's 31250 baud, raw, and wraps its input the same way::

    midi_in, midi_out = linux.serial_ports("/dev/ttyAMA0")

Ids are ``"in:CARD:DEVICE"`` and ``"out:CARD:DEVICE"`` for raw MIDI, the ALSA
address with the direction first, and ``"in:seq:CLIENT:PORT"`` and
``"out:seq:CLIENT:PORT"`` for a sequencer port.

Inputs open non-blocking, so a read on a silent instrument returns ``None``
instead of hanging your loop.

The input ``ports()`` returns stamps each message with its arrival time
(``take_timestamp()``, the package's contract) through ``WholeMessages``, at
the read that finds its first byte: as fine as how often you poll. A port
from ``open_port()`` is the raw byte stream and has no stamps until you wrap
it in ``WholeMessages`` too.
"""

import os
import struct

try:
    import select
except ImportError:  # only the unix ports of MicroPython and CircuitPython need it, and have it
    select = None

from . import IN, INOUT, OUT, PortIn, PortInfo, PortOut, WholeMessages, _count, message_length

PROC_ASOUND = "/proc/asound"
DEV_SND = "/dev/snd"
BAUDRATE = 31250

# struct termios2 and its ioctls, as x86, ARM and RISC-V Linux lay them out:
# the only way to ask a serial driver for a rate termios has no constant for.
_TERMIOS2 = "=4IB19s2I"
_TCGETS2 = 0x802C542A
_TCSETS2 = 0x402C542B
_CBAUD = 0o010017
_BOTHER = 0o010000
_IBSHIFT = 16


def _read_text(path):
    try:
        with open(path) as handle:
            return handle.read()
    except OSError:
        return ""


def _rawmidi_addresses(proc=PROC_ASOUND):
    """Card/device pairs offering raw MIDI, from ``/proc/asound/devices``.

    Lines look like ``  4: [ 0- 0]: raw midi``. Only the bracketed card and
    device are read; the spacing around them isn't worth depending on.
    """
    found = []
    for line in _read_text(proc + "/devices").splitlines():
        if "raw midi" not in line:
            continue
        start, end = line.find("["), line.find("]")
        if start < 0 or end < start:
            continue
        inner = line[start + 1:end].replace(" ", "")
        card, _, device = inner.partition("-")
        if card.isdigit() and device.isdigit():
            found.append((int(card), int(device)))
    return tuple(found)


def _describe(card, device, proc=PROC_ASOUND):
    """``(name, direction)`` for one raw MIDI endpoint.

    The per-device proc file starts with the hardware's name, then lists an
    ``Output`` and/or ``Input`` section. One that names neither is reported
    as both: not being able to read a capability isn't evidence it's missing,
    and opening it will say so honestly.
    """
    text = _read_text("{}/card{}/midi{}".format(proc, card, device))
    name = ""
    for line in text.splitlines():
        candidate = line.strip()
        # Skip the section headers, or a device with an empty name line
        # would be called "Output 0".
        if not candidate or candidate.startswith(("Output", "Input")):
            continue
        name = candidate
        break
    has_out = "Output" in text
    has_in = "Input" in text
    if has_out and not has_in:
        direction = OUT
    elif has_in and not has_out:
        direction = IN
    else:
        direction = INOUT
    return name or "card {} device {}".format(card, device), direction


def available(proc=PROC_ASOUND):
    """Every raw MIDI and sequencer port the kernel offers, as ``PortInfo``.

    A two-way endpoint is listed once per direction, because ALSA opens the
    two halves separately and you may want only one. Raw MIDI ports come
    first.
    """
    found = []
    for card, device in _rawmidi_addresses(proc):
        name, direction = _describe(card, device, proc)
        for way in (OUT, IN):
            if direction in (way, INOUT):
                found.append(PortInfo(
                    id="{}:{}:{}".format(way, card, device), name=name, direction=way))
    if _seq_io() is not None:
        for client, port, name, readable, writable in _seq_ports(proc):
            if writable:
                found.append(PortInfo(id="out:seq:{}:{}".format(client, port), name=name, direction=OUT))
            if readable:
                found.append(PortInfo(id="in:seq:{}:{}".format(client, port), name=name, direction=IN))
    return tuple(found)


def find(name, direction=None, proc=PROC_ASOUND):
    """Ports whose name contains ``name``, case-insensitively."""
    needle = name.lower()
    return tuple(p for p in available(proc)
                 if needle in (p.name or "").lower()
                 and (direction is None or p.direction == direction))


def ports(name="", proc=PROC_ASOUND, dev=DEV_SND):
    """``(midi_in, midi_out)`` for the first ports matching ``name``."""
    ins = find(name, IN, proc)
    outs = find(name, OUT, proc)
    if not ins and not outs:
        raise OSError("no MIDI port matching {!r}".format(name))
    return (WholeMessages(open_port(ins[0], dev)) if ins else None,
            open_port(outs[0], dev) if outs else None)


def serial_ports(path, baudrate=BAUDRATE):
    """``(midi_in, midi_out)`` over a serial port wired to MIDI jacks.

    The port is set raw, 8N1 with no flow control, at ``baudrate``. MIDI's
    31250 isn't one of termios' rates, so it's asked for through the
    driver's custom-rate call; a driver that can't come within 1% of it
    raises ``OSError``. A Raspberry Pi set up the older way, with its UART
    clock changed so that 38400 comes out as 31250, takes
    ``baudrate=38400``. Needs CPython's ``termios``.

    Args:
        path (str): The serial device, such as ``"/dev/ttyAMA0"`` or
            ``"/dev/ttyUSB0"``.
        baudrate (int): The rate to set.

    Returns:
        tuple: A `WholeMessages` input and an output port.
    """
    try:
        import fcntl
        import termios
    except ImportError:
        raise OSError("serial MIDI needs the termios module, which this Python lacks") from None
    info = PortInfo(id=path, name=path, direction=OUT)
    midi_out = LinuxMidiOut(info, path, os.O_NOCTTY)
    try:
        try:
            _set_serial(midi_out._fd, baudrate, fcntl, termios)
        except termios.error as error:
            raise OSError(error.args[0], "%s can't be set up as a serial port: %s" % (path, error.args[1])) from None
        midi_in = LinuxMidiIn(PortInfo(id=path, name=path, direction=IN), path, os.O_NOCTTY)
    except BaseException:
        midi_out.close()
        raise
    termios.tcflush(midi_in._fd, termios.TCIFLUSH)
    return WholeMessages(midi_in), midi_out


def _set_serial(fd, baudrate, fcntl, termios):
    """Make ``fd`` raw 8N1 with no flow control, at ``baudrate``."""
    iflag, oflag, cflag, lflag, ispeed, ospeed, cc = termios.tcgetattr(fd)
    iflag &= ~(termios.IGNBRK | termios.BRKINT | termios.PARMRK | termios.ISTRIP | termios.INLCR
               | termios.IGNCR | termios.ICRNL | termios.IXON | termios.IXOFF | termios.IXANY)
    oflag &= ~termios.OPOST
    lflag &= ~(termios.ECHO | termios.ECHONL | termios.ICANON | termios.ISIG | termios.IEXTEN)
    cflag &= ~(termios.CSIZE | termios.PARENB | termios.CSTOPB | termios.CRTSCTS)
    cflag |= termios.CS8 | termios.CLOCAL | termios.CREAD
    cc[termios.VMIN] = 0
    cc[termios.VTIME] = 0
    speed = getattr(termios, "B%d" % baudrate, None)
    if speed is not None:
        ispeed = ospeed = speed
    termios.tcsetattr(fd, termios.TCSANOW, [iflag, oflag, cflag, lflag, ispeed, ospeed, cc])
    if speed is not None:
        return
    raw = fcntl.ioctl(fd, _TCGETS2, bytes(struct.calcsize(_TERMIOS2)))
    iflag, oflag, cflag, lflag, line, cc, _, _ = struct.unpack(_TERMIOS2, raw)
    cflag &= ~(_CBAUD | (_CBAUD << _IBSHIFT))
    cflag |= _BOTHER | (_BOTHER << _IBSHIFT)
    fcntl.ioctl(fd, _TCSETS2, struct.pack(_TERMIOS2, iflag, oflag, cflag, lflag, line, cc, baudrate, baudrate))
    raw = fcntl.ioctl(fd, _TCGETS2, bytes(struct.calcsize(_TERMIOS2)))
    got = struct.unpack(_TERMIOS2, raw)[-1]
    if abs(got - baudrate) * 100 > baudrate:
        raise OSError("this serial port runs at %d baud when asked for %d" % (got, baudrate))


def _split_id(port_id):
    """``(direction, card, device, None)`` for raw MIDI, or
    ``(direction, client, port, "seq")`` for a sequencer port."""
    parts = str(port_id).split(":")
    kind = None
    if len(parts) == 4 and parts[1] == "seq":
        kind = parts.pop(1)
    if len(parts) != 3 or parts[0] not in (IN, OUT) \
            or not parts[1].isdigit() or not parts[2].isdigit():
        raise ValueError(
            "bad MIDI port id {!r}; expected 'in:CARD:DEVICE', 'out:CARD:DEVICE', "
            "'in:seq:CLIENT:PORT' or 'out:seq:CLIENT:PORT'".format(port_id))
    return parts[0], int(parts[1]), int(parts[2]), kind


def open_port(port, dev=DEV_SND):
    """Open one port, given a ``PortInfo`` or an id string."""
    info = port if isinstance(port, PortInfo) else None
    port_id = info.id if info is not None else port
    way, first, second, kind = _split_id(port_id)
    if kind == "seq":
        if info is None:
            info = PortInfo(id=port_id, name=_seq_name(first, second), direction=way)
        path = dev + "/seq"
        if way == OUT:
            return LinuxSeqOut(info, path, (first, second))
        return LinuxSeqIn(info, path, (first, second))
    if info is None:
        name, _ = _describe(first, second)
        info = PortInfo(id=port_id, name=name, direction=way)
    path = "{}/midiC{}D{}".format(dev, first, second)
    return LinuxMidiOut(info, path) if way == OUT else LinuxMidiIn(info, path)


def _closed():
    return OSError("MIDI port is closed")


#: Whether this interpreter has ``os.open`` and ``os.read`` (CPython does; the
#: unix ports of MicroPython and CircuitPython don't, and use ``open()``).
_FD_API = hasattr(os, "open") and hasattr(os, "O_NONBLOCK")


class LinuxMidiIn(PortIn):
    """The input half of an ALSA raw MIDI endpoint."""

    def __init__(self, info, path, flags=0):
        PortIn.__init__(self)
        self.info = info
        self._file = None
        self._poll = None
        if _FD_API:
            # Without O_NONBLOCK a read on a silent instrument blocks your loop.
            self._fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | flags)
        else:
            self._file = open(path, "rb")
            self._fd = self._file
            self._poll = select.poll()
            self._poll.register(self._file, select.POLLIN)

    def readinto(self, buf, nbytes=None):
        if self._fd is None:
            raise _closed()
        if self._poll is not None:
            # A byte at a time while poll says one is there: MicroPython's
            # read(n) and readinto() both wait until n bytes have come.
            size = _count(buf, nbytes)
            n = 0
            while n < size and self._poll.poll(0):
                byte = self._file.read(1)
                if not byte:
                    break                 # end of file
                buf[n] = byte[0]
                n += 1
            return n or None
        else:
            try:
                data = os.read(self._fd, _count(buf, nbytes))
            except OSError:
                return None               # EAGAIN: nothing waiting
        n = len(data)
        if not n:
            return None
        buf[:n] = data
        return n

    def close(self):
        fd, self._fd = self._fd, None
        if fd is None:
            return
        if self._poll is not None:
            self._poll.unregister(self._file)
            self._poll = None
            self._file.close()
        else:
            os.close(fd)

    deinit = close


class LinuxMidiOut(PortOut):
    """The output half of an ALSA raw MIDI endpoint."""

    def __init__(self, info, path, flags=0):
        self.info = info
        if _FD_API:
            self._fd = os.open(path, os.O_WRONLY | flags)
            self._file = None
        else:
            self._file = open(path, "wb")
            self._fd = self._file

    def write(self, buf, nbytes=None):
        if self._fd is None:
            raise _closed()
        n = _count(buf, nbytes)
        if self._file is not None:
            self._file.write(bytes(buf[:n]))
            return n
        return os.write(self._fd, bytes(buf[:n]))

    def close(self):
        fd, self._fd = self._fd, None
        if fd is None:
            return
        if self._file is not None:
            self._file.close()
        else:
            os.close(fd)

    deinit = close


# ---------------------------------------------------------------- the ALSA sequencer
#
# A sequencer port is reached through /dev/snd/seq: ioctls make this program a
# client with a port of its own, and the device's read() and write() carry
# struct snd_seq_event, 28 bytes each (include/uapi/sound/asequencer.h). A
# SysEx is a variable-length event, its bytes right after the header.

_EVENT = "<BBbBIIBBBB12s"   # type, flags, tag, queue, time (8), source, dest, data
_EVENT_SIZE = 28
_LENGTH_VARIABLE = 0x04
_LENGTH_MASK = 0x0C
_EXT_MASK = 0xC0000000
_QUEUE_DIRECT = 253

# Event types.
_NOTEON, _NOTEOFF, _KEYPRESS = 6, 7, 8
_CONTROLLER, _PGMCHANGE, _CHANPRESS, _PITCHBEND = 10, 11, 12, 13
_CONTROL14, _NONREGPARAM, _REGPARAM = 14, 15, 16
_SONGPOS, _SONGSEL, _QFRAME = 20, 21, 22
_START, _CONTINUE, _STOP, _CLOCK = 30, 31, 32, 36
_TUNE_REQUEST, _RESET, _SENSING = 40, 41, 42
_SYSEX = 130

# Status bytes with no data, and the event each one is.
_SIMPLE = {0xF6: _TUNE_REQUEST, 0xF8: _CLOCK, 0xFA: _START, 0xFB: _CONTINUE,
           0xFC: _STOP, 0xFE: _SENSING, 0xFF: _RESET}
_SIMPLE_BACK = {v: k for k, v in _SIMPLE.items()}
# Channel messages: high nibble -> event type, and back.
_VOICE = {0x8: _NOTEOFF, 0x9: _NOTEON, 0xA: _KEYPRESS, 0xB: _CONTROLLER,
          0xC: _PGMCHANGE, 0xD: _CHANPRESS, 0xE: _PITCHBEND}
_VOICE_BACK = {v: k for k, v in _VOICE.items()}

# Port capabilities.
_CAP_READ, _CAP_WRITE = 0x01, 0x02
_CAP_SUBS_READ, _CAP_SUBS_WRITE = 0x20, 0x40
_TYPE_MIDI_GENERIC, _TYPE_APPLICATION = 0x02, 0x100000

# struct snd_seq_client_info, snd_seq_port_info and snd_seq_port_subscribe.
# port_info holds a kernel pointer, so its size follows the pointer's.
_CLIENT_INFO = "<ii64sI8s32s4i56s"
_PORT_INFO = "<BB64s2x7i" + ("Q" if struct.calcsize("P") == 8 else "I") + "IBBB57s"
_SUBSCRIBE = "<BBBBIIB3x64s"


def _ioc(direction, nr, fmt):
    return (direction << 30) | (struct.calcsize(fmt) << 16) | (0x53 << 8) | nr  # 'S'


_IOCTL_CLIENT_ID = (2 << 30) | (4 << 16) | (0x53 << 8) | 0x01
_IOCTL_GET_CLIENT_INFO = _ioc(3, 0x10, _CLIENT_INFO)
_IOCTL_SET_CLIENT_INFO = _ioc(1, 0x11, _CLIENT_INFO)
_IOCTL_CREATE_PORT = _ioc(3, 0x20, _PORT_INFO)
_IOCTL_SUBSCRIBE_PORT = _ioc(1, 0x30, _SUBSCRIBE)

_O_RDONLY, _O_WRONLY, _O_NONBLOCK, _O_CLOEXEC = 0, 1, 0o4000, 0o2000000
_EAGAIN = 11
#: The name this program's sequencer client takes, as ``aconnect -l`` shows it.
CLIENT_NAME = "midiports"


def _seq_ports(proc=PROC_ASOUND):
    """``(client, port, name, readable, writable)`` for each sequencer port
    worth listing, from ``/proc/asound/seq/clients``.

    That's every port that can be subscribed to, of user clients (programs,
    BlueZ) and of the kernel's own clients below 16 (``Midi Through``), but
    not client 0 (the system's timer and announcements) or the kernel's
    sound-card clients, which are the raw MIDI ports again. A line reads
    ``  Port   0 : "THMI-MIDI Bluetooth" (RWe-) [In/Out]``: ``R`` and ``W``
    are a port others may subscribe to read from and write to, and ``e``
    one that isn't hidden.
    """
    found = []
    keep = False
    client = -1
    for line in _read_text(proc + "/seq/clients").splitlines():
        if line.startswith("Client "):
            head, _, rest = line.partition(":")
            number = head[7:].strip()
            if not number.isdigit():
                keep = False
                continue
            client = int(number)
            kernel = "[Kernel" in rest
            keep = client != 0 and (not kernel or client < 16)
            continue
        text = line.strip()
        if not keep or not text.startswith("Port "):
            continue
        head, _, rest = text.partition(":")
        number = head[5:].strip()
        first, last = rest.find('"'), rest.rfind('"')
        caps_at = rest.find("(", last)
        if not number.isdigit() or first < 0 or last <= first or caps_at < 0:
            continue
        caps = rest[caps_at + 1:caps_at + 5]
        if len(caps) < 3 or caps[2] != "e" or (caps[0] != "R" and caps[1] != "W"):
            continue
        found.append((client, int(number), rest[first + 1:last], caps[0] == "R", caps[1] == "W"))
    return tuple(found)


def _seq_name(client, port, proc=PROC_ASOUND):
    for c, p, name, _, _ in _seq_ports(proc):
        if (c, p) == (client, port):
            return name
    return "sequencer {}:{}".format(client, port)


class _FcntlIO:
    """/dev/snd/seq through CPython's ``os`` and ``fcntl``."""

    def __init__(self, fcntl):
        self._fcntl = fcntl

    def open(self, path, flags):
        return os.open(path, flags)

    def ioctl(self, fd, request, buf):
        self._fcntl.ioctl(fd, request, buf, True)

    def read(self, fd, buf):
        try:
            return os.readv(fd, [buf])
        except BlockingIOError:
            return 0

    def write(self, fd, data):
        return os.write(fd, data)

    def close(self, fd):
        os.close(fd)


class _FfiIO:
    """/dev/snd/seq through the C library, from MicroPython's unix port."""

    def __init__(self, ffi):
        libc = None
        for name in ("libc.so.6", "libc.so"):
            try:
                libc = ffi.open(name)
                break
            except OSError:
                pass
        if libc is None:
            raise OSError("no C library for ffi to open")
        self._open = libc.func("i", "open", "si")
        self._ioctl = libc.func("i", "ioctl", "iip")
        self._read = libc.func("i", "read", "ipi")
        self._write = libc.func("i", "write", "ipi")
        self._close = libc.func("i", "close", "i")

    @staticmethod
    def _check(result, what):
        if result < 0:
            raise OSError(os.errno(), what)
        return result

    def open(self, path, flags):
        return self._check(self._open(path, flags), path)

    def ioctl(self, fd, request, buf):
        self._check(self._ioctl(fd, request, buf), "ioctl")

    def read(self, fd, buf):
        n = self._read(fd, buf, len(buf))
        if n < 0:
            if os.errno() == _EAGAIN:
                return 0
            raise OSError(os.errno(), "read")
        return n

    def write(self, fd, data):
        return self._check(self._write(fd, data, len(data)), "write")

    def close(self, fd):
        self._close(fd)


_IO = []


def _seq_io():
    """How this interpreter reaches ``/dev/snd/seq``, or ``None`` if it can't."""
    if not _IO:
        io = None
        try:
            import fcntl
            if hasattr(os, "readv"):
                io = _FcntlIO(fcntl)
        except ImportError:
            pass
        if io is None:
            try:
                import ffi
                io = _FfiIO(ffi)
            except (ImportError, OSError):
                pass
        _IO.append(io)
    return _IO[0]


class _SeqClient:
    """This program as a sequencer client with one port, on its own handle."""

    def __init__(self, path, flags, caps, port_name):
        io = _seq_io()
        if io is None:
            raise OSError("ALSA sequencer ports need ioctl, which this Python has neither "
                          "fcntl nor ffi for")
        self._io = io
        self.fd = io.open(path, flags | _O_CLOEXEC)
        try:
            buf = bytearray(4)
            io.ioctl(self.fd, _IOCTL_CLIENT_ID, buf)
            self.client = struct.unpack("<i", buf)[0]
            info = bytearray(struct.calcsize(_CLIENT_INFO))
            struct.pack_into("<i", info, 0, self.client)
            io.ioctl(self.fd, _IOCTL_GET_CLIENT_INFO, info)
            fields = list(struct.unpack(_CLIENT_INFO, info))
            fields[2] = CLIENT_NAME.encode()
            info[:] = struct.pack(_CLIENT_INFO, *fields)
            io.ioctl(self.fd, _IOCTL_SET_CLIENT_INFO, info)
            port = bytearray(struct.pack(
                _PORT_INFO, self.client, 0, port_name.encode()[:63], caps,
                _TYPE_MIDI_GENERIC | _TYPE_APPLICATION, 16, 0, 0, 0, 0, 0, 0, 0, 0, 0, b""))
            io.ioctl(self.fd, _IOCTL_CREATE_PORT, port)
            self.port = port[1]
        except BaseException:
            io.close(self.fd)
            raise

    def subscribe(self, sender, dest):
        buf = bytearray(struct.pack(_SUBSCRIBE, sender[0], sender[1], dest[0], dest[1], 0, 0, 0, b""))
        self._io.ioctl(self.fd, _IOCTL_SUBSCRIBE_PORT, buf)

    def read(self, buf):
        return self._io.read(self.fd, buf)

    def write(self, data):
        return self._io.write(self.fd, data)

    def close(self):
        fd, self.fd = self.fd, None
        if fd is not None:
            self._io.close(fd)


def _event(kind, source, dest, data=b"", flags=0):
    """One event, sent at once (no queue) from ``source`` port to ``dest``."""
    return struct.pack(_EVENT, kind, flags, 0, _QUEUE_DIRECT, 0, 0, source[0], source[1], dest[0], dest[1], data)


def _note(channel, note, velocity):
    return struct.pack("<BBBBI4x", channel, note, velocity, 0, 0)


def _ctrl(channel, param, value):
    return struct.pack("<B3xIi", channel, param, value)


def encode_message(message, source=(0, 0), dest=(0, 0)):
    """The sequencer event for one whole MIDI message, as bytes, or ``b""``
    for one the sequencer has no event for (an undefined status byte)."""
    status = message[0]
    if status == 0xF0:
        return _event(_SYSEX, source, dest, struct.pack("<I8x", len(message)), _LENGTH_VARIABLE) + bytes(message)
    if status in _SIMPLE:
        return _event(_SIMPLE[status], source, dest)
    d1 = message[1] if len(message) > 1 else 0
    d2 = message[2] if len(message) > 2 else 0
    if status == 0xF1:
        return _event(_QFRAME, source, dest, _ctrl(0, 0, d1))
    if status == 0xF2:
        return _event(_SONGPOS, source, dest, _ctrl(0, 0, d1 | d2 << 7))
    if status == 0xF3:
        return _event(_SONGSEL, source, dest, _ctrl(0, 0, d1))
    kind = _VOICE.get(status >> 4)
    if kind is None or status >= 0xF0:
        return b""
    channel = status & 0x0F
    if kind in (_NOTEON, _NOTEOFF, _KEYPRESS):
        return _event(kind, source, dest, _note(channel, d1, d2))
    if kind == _CONTROLLER:
        return _event(kind, source, dest, _ctrl(channel, d1, d2))
    if kind == _PITCHBEND:
        return _event(kind, source, dest, _ctrl(channel, 0, (d1 | d2 << 7) - 8192))
    return _event(kind, source, dest, _ctrl(channel, 0, d1))  # program change, channel pressure


def decode_events(data, out):
    """Append the MIDI bytes of the events in ``data`` (what a read of
    ``/dev/snd/seq`` returned) to the bytearray ``out``; events with no MIDI
    meaning (port announcements, echoes) are skipped. Returns how many bytes
    of ``data`` were whole events."""
    pos = 0
    end = len(data)
    while pos + _EVENT_SIZE <= end:
        kind, flags = data[pos], data[pos + 1]
        body = pos + 16
        size = _EVENT_SIZE
        if flags & _LENGTH_MASK == _LENGTH_VARIABLE:
            extra = struct.unpack_from("<I", data, body)[0] & ~_EXT_MASK
            if pos + _EVENT_SIZE + extra > end:
                break
            size += extra
            if kind == _SYSEX:
                out.extend(data[pos + _EVENT_SIZE:pos + size])
        elif kind in _SIMPLE_BACK:
            out.append(_SIMPLE_BACK[kind])
        elif kind in (_NOTEON, _NOTEOFF, _KEYPRESS):
            channel, note, velocity = data[body], data[body + 1], data[body + 2]
            out.extend(bytes((_VOICE_BACK[kind] << 4 | channel & 0x0F, note & 0x7F, velocity & 0x7F)))
        elif _CONTROLLER <= kind <= _REGPARAM or _SONGPOS <= kind <= _QFRAME:
            channel, param, value = struct.unpack_from("<B3xIi", data, body)
            _ctrl_bytes(kind, channel & 0x0F, param, value, out)
        pos += size
    return pos


def _ctrl_bytes(kind, channel, param, value, out):
    if kind == _CONTROLLER:
        out.extend(bytes((0xB0 | channel, param & 0x7F, value & 0x7F)))
    elif kind in (_PGMCHANGE, _CHANPRESS):
        out.extend(bytes((_VOICE_BACK[kind] << 4 | channel, value & 0x7F)))
    elif kind == _PITCHBEND:
        value = max(0, min(16383, value + 8192))
        out.extend(bytes((0xE0 | channel, value & 0x7F, value >> 7)))
    elif kind == _CONTROL14:
        if param < 32:
            out.extend(bytes((0xB0 | channel, param, value >> 7 & 0x7F, 0xB0 | channel, param + 32, value & 0x7F)))
        else:
            out.extend(bytes((0xB0 | channel, param & 0x7F, value & 0x7F)))
    elif kind in (_NONREGPARAM, _REGPARAM):
        msb, lsb = (99, 98) if kind == _NONREGPARAM else (101, 100)
        status = 0xB0 | channel
        out.extend(bytes((status, msb, param >> 7 & 0x7F, status, lsb, param & 0x7F,
                          status, 6, value >> 7 & 0x7F, status, 38, value & 0x7F)))
    elif kind == _SONGPOS:
        out.extend(bytes((0xF2, value & 0x7F, value >> 7 & 0x7F)))
    elif kind == _SONGSEL:
        out.extend(bytes((0xF3, value & 0x7F)))
    elif kind == _QFRAME:
        out.extend(bytes((0xF1, value & 0x7F)))


class LinuxSeqIn(PortIn):
    """The input half of an ALSA sequencer port: this program subscribes a
    port of its own to it and reads what it sends."""

    #: The most a read of ``/dev/snd/seq`` takes in; a longer SysEx event grows it.
    READ_SIZE = 4096

    def __init__(self, info, path, address):
        PortIn.__init__(self)
        self.info = info
        self.address = address
        self._seq = _SeqClient(path, _O_RDONLY | _O_NONBLOCK, _CAP_WRITE | _CAP_SUBS_WRITE, "in")
        try:
            self._seq.subscribe(address, (self._seq.client, self._seq.port))
        except BaseException:
            self._seq.close()
            raise
        self._raw = bytearray(self.READ_SIZE)
        self._bytes = bytearray()
        self._pos = 0

    def readinto(self, buf, nbytes=None):
        if self._seq.fd is None:
            raise _closed()
        if self._pos >= len(self._bytes):
            self._bytes = bytearray()
            self._pos = 0
            self._fill()
        size = _count(buf, nbytes)
        n = min(size, len(self._bytes) - self._pos)
        if n <= 0:
            return None
        buf[:n] = self._bytes[self._pos:self._pos + n]
        self._pos += n
        return n

    def _fill(self):
        while True:
            try:
                got = self._seq.read(self._raw)
            except OSError as e:
                if e.args and e.args[0] == 28:  # ENOSPC: one event is bigger than the buffer
                    self._raw = bytearray(2 * len(self._raw))
                    continue
                raise
            if not got:
                return
            decode_events(memoryview(self._raw)[:got], self._bytes)
            if got < len(self._raw) - _EVENT_SIZE:
                return

    def close(self):
        if self._seq.fd is not None:
            self._seq.close()

    deinit = close


class LinuxSeqOut(PortOut):
    """The output half of an ALSA sequencer port. Takes plain MIDI bytes,
    running status and all, and sends each message as its event."""

    def __init__(self, info, path, address):
        self.info = info
        self.address = address
        self._seq = _SeqClient(path, _O_WRONLY, _CAP_READ | _CAP_SUBS_READ, "out")
        self._source = (self._seq.client, self._seq.port)
        self._status = 0      # running status carried across writes
        self._sysex = None    # a SysEx waiting for its 0xF7
        self._partial = bytearray()

    def write(self, buf, nbytes=None):
        if self._seq.fd is None:
            raise _closed()
        n = _count(buf, nbytes)
        events = bytearray()
        partial = self._partial
        for i in range(n):
            b = buf[i]
            if b >= 0xF8:
                events.extend(encode_message(bytes((b,)), self._source, self.address))
                continue
            if self._sysex is not None:
                if b < 0x80:
                    self._sysex.append(b)
                    continue
                sysex, self._sysex = self._sysex, None
                sysex.append(0xF7)  # a status byte ends a SysEx, as the spec says
                events.extend(encode_message(sysex, self._source, self.address))
                if b == 0xF7:
                    continue
            if b == 0xF0:
                self._status = 0
                self._sysex = bytearray(b"\xf0")
                partial[:] = b""
                continue
            if b >= 0x80:
                self._status = b if b < 0xF0 else 0
                partial[:] = bytes((b,))
            elif partial:
                partial.append(b)
            elif self._status:
                partial[:] = bytes((self._status, b))
            else:
                continue          # a data byte with no status: nothing to send
            if len(partial) > message_length(partial[0]):
                events.extend(encode_message(partial, self._source, self.address))
                partial[:] = b""
        if events:
            self._seq.write(bytes(events))
        return n

    def close(self):
        if self._seq.fd is not None:
            self._seq.close()

    deinit = close
