# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""``midiports.linux`` against a synthetic ALSA tree, runnable on CPython,
unix MicroPython and unix CircuitPython::

    python tests/midiports_linux_checks.py SCRATCH_DIR [FIFO [--adafruit=DIR]]

WSL has no ``snd-virmidi`` and CI has no sound card, so ``SCRATCH_DIR`` gets a
fake ``/proc/asound`` and a ``/dev/snd`` of plain files, which the port reads
and writes the way it would a raw MIDI device. With ``FIFO`` (a named pipe the
caller holds open for writing) it also proves an empty input returns at once
instead of blocking, then reads what the caller writes. With ``--adafruit=DIR`` too (where
``adafruit_midi/`` is), it then prints ``SYSEX`` and reads `SYSEX_STREAM`,
which the caller writes in parts, through ``adafruit_midi``: the 1 KB SysEx
must come out as one message. MicroPython's and
CircuitPython's ``os`` have no ``open``, so there this goes through the
builtin ``open()`` and ``select.poll``.

Prints one PASS/FAIL line per check and ``N checks, M failed (interpreter)``.
"""

import sys

try:
    _here = __file__
except NameError:  # pragma: no cover
    _here = sys.argv[0]
_sep = "\\" if "\\" in _here else "/"
_dir = _here.rsplit(_sep, 1)[0] if _sep in _here else "."
sys.path.insert(0, _dir + _sep + ".." + _sep + "packages" + _sep + "midiports")

import os
import time

import midiports
from midiports import linux

ARGS = [a for a in sys.argv[1:] if not a.startswith("--adafruit=")]
ADAFRUIT = [a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--adafruit=")]
SCRATCH = ARGS[0]
FIFO = ARGS[1] if len(ARGS) > 1 else None
if ADAFRUIT:
    sys.path.insert(0, ADAFRUIT[0])

#: What the caller writes after ``SYSEX``: a note, a 1 KB SysEx, a note-off.
SYSEX_1K = bytes([0xF0, 0x7D] + [i % 128 for i in range(1021)] + [0xF7])
SYSEX_STREAM = bytes((0x90, 0x3C, 0x64)) + SYSEX_1K + bytes((0x80, 0x3C, 0x00))
FAILED = 0
COUNT = 0


def check(name, condition, detail=""):
    global FAILED, COUNT
    COUNT += 1
    if condition:
        print("PASS", name)
    else:
        FAILED += 1
        print("FAIL", name, detail)


def write(path, data):
    with open(path, "wb") as handle:
        handle.write(data)


def tree():
    proc = SCRATCH + "/asound"
    dev = SCRATCH + "/snd"
    for folder in (proc, proc + "/card0", proc + "/card1", dev):
        try:
            os.mkdir(folder)
        except OSError:
            pass
    write(proc + "/devices", b"  0: [ 0]   : control\n  4: [ 0- 0]: raw midi\n  4: [ 1- 0]: raw midi\n")
    write(proc + "/card0/midi0", b"DONNER DMK25Pro\n\nOutput 0\nInput 0\n")
    write(proc + "/card1/midi0", b"Some Synth\n\nOutput 0\n")
    return proc, dev


def sysex_whole(port):
    """A 1 KB SysEx written to the pipe in parts reaches adafruit_midi whole."""
    import adafruit_midi
    # Importing a message's module is what teaches adafruit_midi to read it.
    import adafruit_midi.note_off  # noqa: F401
    import adafruit_midi.note_on  # noqa: F401
    import adafruit_midi.system_exclusive  # noqa: F401

    midi = adafruit_midi.MIDI(midi_in=midiports.WholeMessages(port), in_channel=0, in_buf_size=1100)
    print("SYSEX")
    sys.stdout.flush()
    got = []
    for _ in range(500):
        msg = midi.receive()
        if msg is None:
            if len(got) >= 3:
                break
            time.sleep(0.01)
        else:
            got.append(msg)
    names = [type(m).__name__ for m in got]
    check("a 1 KB SysEx written in parts reaches adafruit_midi whole",
          names == ["NoteOn", "SystemExclusive", "NoteOff"], names)
    if len(got) == 3:
        check("the SysEx's body is the one sent",
              bytes(got[1].manufacturer_id) == b"\x7d" and bytes(got[1].data) == SYSEX_1K[2:-1],
              len(got[1].data))


def sequencer(proc):
    """The ALSA sequencer half: its listing, its event codec, and how this
    interpreter reaches ``/dev/snd/seq`` (``fcntl``, ``ffi`` or nothing)."""
    try:
        os.mkdir(proc + "/seq")
    except OSError:
        pass
    write(proc + "/seq/clients", b'Client   0 : "System" [Kernel Legacy]\n  Port   0 : "Timer" (Rwe-)\n'
          b'Client 128 : "THMI-MIDI" [User Legacy]\n  Port   0 : "THMI-MIDI Bluetooth" (RWe-) [In/Out]\n')
    check("BlueZ's sequencer port is read from the listing",
          linux._seq_ports(proc) == ((128, 0, "THMI-MIDI Bluetooth", True, True),), linux._seq_ports(proc))
    messages = [bytes((0x90, 0x3C, 0x64)), bytes((0xE5, 0x7F, 0x7F)), bytes((0xF2, 0x10, 0x20)), bytes((0xF8,)),
                bytes([0xF0, 0x7D] + [i % 128 for i in range(300)] + [0xF7])]
    stream = b"".join(linux.encode_message(m, (130, 0), (128, 0)) for m in messages)
    out = bytearray()
    used = linux.decode_events(memoryview(stream), out)
    check("MIDI survives the sequencer's event codec", used == len(stream) and bytes(out) == b"".join(messages))
    io = linux._seq_io()
    if sys.implementation.name == "circuitpython":
        check("CircuitPython lists no sequencer ports (no ioctl)",
              io is None and not [p for p in linux.available(proc) if ":seq:" in p.id])
        return
    check("this interpreter can reach /dev/snd/seq", io is not None, sys.implementation.name)
    if io is None:
        return
    check("sequencer ports are listed", [p.id for p in linux.available(proc) if ":seq:" in p.id]
          == ["out:seq:128:0", "in:seq:128:0"])
    # The C library calls, on a plain file: what an ALSA sequencer is read and written with.
    path = SCRATCH + "/seqfile"
    write(path, b"")
    fd = io.open(path, 1)  # O_WRONLY
    check("a write goes through", io.write(fd, b"abc") == 3)
    io.close(fd)
    fd = io.open(path, 0 | 0o4000)
    buf = bytearray(8)
    n = io.read(fd, buf)
    check("a read comes back", n == 3 and bytes(buf[:3]) == b"abc", n)
    try:
        io.ioctl(fd, linux._IOCTL_CLIENT_ID, bytearray(4))
        refused = False
    except OSError:
        refused = True
    check("an ioctl the file doesn't know raises OSError", refused)
    io.close(fd)


def main():
    proc, dev = tree()
    found = linux.available(proc)
    check("a two-way device is listed once per direction",
          sorted(p.id for p in found) == ["in:0:0", "out:0:0", "out:1:0"], found)
    check("find ignores case and filters direction",
          [p.id for p in linux.find("donner", midiports.IN, proc)] == ["in:0:0"])

    write(dev + "/midiC0D0", b"")
    midi_in, midi_out = linux.ports("donner", proc=proc, dev=dev)
    # Opened first (opening for output empties a plain file, which a device ignores), then filled.
    write(dev + "/midiC0D0", bytes((0x90, 0x3C, 0x64, 0x3E, 0x50, 0xF8)))  # running status, then a clock
    try:
        before = midiports.ticks_us()
        got = midi_in.read(64)
        after = midiports.ticks_us()
        check("running status comes out as whole messages and the clock after",
              got == bytes((0x90, 0x3C, 0x64, 0x90, 0x3E, 0x50, 0xF8)), got)
        check("an empty read is None", midi_in.read(64) is None)
        stamps = [midi_in.take_timestamp() for _ in range(4)]
        check("one arrival time per message, taken by the read that found them",
              stamps[3] is None and stamps[0] is not None
              and midiports.ticks_diff(stamps[0], before) >= 0 and midiports.ticks_diff(after, stamps[0]) >= 0, stamps)
        check("write returns the count it took", midi_out.write(bytes((0xB0, 0x07, 0x7F, 0x00)), 3) == 3)
    finally:
        midi_in.close()
        midi_out.close()
    check("the output wrote to the device file",
          open(dev + "/midiC0D0", "rb").read()[:3] == bytes((0xB0, 0x07, 0x7F)))
    try:
        midi_in.read(4)
        closed = False
    except OSError:
        closed = True
    check("a closed input raises OSError", closed)
    midi_out.close()  # twice is fine
    try:
        linux.ports("nothing", proc=proc, dev=dev)
        said = False
    except OSError:
        said = True
    check("no matching port says so", said)
    sequencer(proc)

    if FIFO:
        info = midiports.PortInfo(id="in:9:9", name="fifo", direction=midiports.IN)
        port = linux.LinuxMidiIn(info, FIFO)
        try:
            start = time.time()
            check("an empty pipe returns at once, not blocked", port.read(8) is None and time.time() - start < 1)
            print("READY")
            sys.stdout.flush()
            data = None
            for _ in range(500):
                data = port.read(8)
                if data:
                    break
                time.sleep(0.01)
            check("what the writer sent arrives", data == bytes((0x90, 0x40, 0x7F)), data)
            if ADAFRUIT:
                sysex_whole(port)
        finally:
            port.close()
    print("%d checks, %d failed (%s)" % (COUNT, FAILED, sys.implementation.name))
    sys.exit(1 if FAILED else 0)


main()
