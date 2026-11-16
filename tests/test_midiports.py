# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""midiports: its package file, its contract on CPython and MicroPython, the
Linux port against a synthetic ALSA tree, and the Web MIDI port against fake
browser objects.

The contract (``midiports_contract.py``) runs with Adafruit's
``adafruit_midi``, fetched from the URLs ``midiports/package.json`` pins, so
the files a board would install are the files under test. They're cached in
the system temp directory by tag. Without a network the contract runs are
skipped loudly, and ``OMNIPYTHON_REQUIRE_NETWORK=1`` turns that into a
failure. The MicroPython run finds its interpreter as ``test_bledev`` does.
"""

from pathlib import Path
import asyncio
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest import mock
import urllib.request

from _mprun import need_micropython, run

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "midiports"
CONTRACT = Path(__file__).resolve().parent / "midiports_contract.py"
ADAFRUIT_PREFIX = "https://raw.githubusercontent.com/adafruit/Adafruit_CircuitPython_MIDI/"
OURS_PREFIX = "github:PyDevices/omnipython/"

sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(ROOT / "packages" / "_boardname"))

import midiports  # noqa: E402
from midiports import IN, OUT, WholeMessages, linux, webmidi  # noqa: E402


def _package_json():
    return json.loads((PACKAGE / "package.json").read_text(encoding="utf-8"))


def _adafruit_urls():
    return [(dest, url) for dest, url in _package_json()["urls"] if url.startswith(ADAFRUIT_PREFIX)]


_fetched = None


def adafruit_dir(case):
    """Where the pinned adafruit_midi files are, fetching them once."""
    global _fetched
    if _fetched is not None:
        return _fetched
    urls = _adafruit_urls()
    tag = urls[0][1][len(ADAFRUIT_PREFIX):].split("/", 1)[0]
    root = Path(tempfile.gettempdir()) / "midiports-adafruit_midi" / tag
    try:
        for dest, url in urls:
            target = root / dest
            if target.is_file():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with urllib.request.urlopen(url, timeout=30) as response:
                data = response.read()
            partial = target.with_suffix(".part")
            partial.write_bytes(data)
            partial.replace(target)
    except OSError as error:
        message = "could not fetch adafruit_midi ({}): the midiports contract did NOT run".format(error)
        if os.environ.get("OMNIPYTHON_REQUIRE_NETWORK") == "1":
            case.fail(message)
        sys.stderr.write("\n*** " + message + " ***\n")
        case.skipTest(message)
    _fetched = str(root)
    return _fetched


class PackageFile(unittest.TestCase):
    def test_every_module_is_listed_and_every_listed_file_exists(self):
        listed = {}
        for dest, url in _package_json()["urls"]:
            if url.startswith(OURS_PREFIX):
                listed[dest] = url[len(OURS_PREFIX):]
        modules = {"midiports/" + p.name for p in (PACKAGE / "midiports").glob("*.py")}
        self.assertEqual(set(listed), modules)
        for dest, path in listed.items():
            self.assertTrue((ROOT / path).is_file(), path)
            self.assertEqual(path, "packages/midiports/" + dest)

    def test_adafruit_midi_is_linked_at_one_release_tag(self):
        urls = _adafruit_urls()
        self.assertTrue(urls)
        tags = {url[len(ADAFRUIT_PREFIX):].split("/", 1)[0] for _, url in urls}
        self.assertEqual(len(tags), 1, tags)
        (tag,) = tags
        # A tag, never a branch: a branch moves under every board that installed it.
        self.assertRegex(tag, r"^\d+\.\d+\.\d+$")
        for dest, url in urls:
            self.assertTrue(dest.startswith("adafruit_midi/"), dest)
            self.assertTrue(url.endswith("/" + dest), url)

    def test_the_manifest_freezes_files_that_exist(self):
        text = (PACKAGE / "manifest.py").read_text(encoding="utf-8")
        start = text.index("files=(") + len("files=(")
        names = [n.strip().strip('"') for n in text[start:text.index(")", start)].split(",") if n.strip()]
        self.assertIn("__init__.py", names)
        for name in names:
            self.assertTrue((PACKAGE / "midiports" / name).is_file(), name)

    def test_versions_agree(self):
        self.assertEqual(_package_json()["version"], midiports.__version__)
        self.assertIn('version="{}"'.format(midiports.__version__),
                      (PACKAGE / "manifest.py").read_text(encoding="utf-8"))


class Contract(unittest.TestCase):
    def assertPasses(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(" 0 failed", result.stdout)

    def test_cpython(self):
        self.assertPasses(run([sys.executable, CONTRACT, "--adafruit=" + adafruit_dir(self)]))

    def test_micropython(self):
        interpreter = need_micropython(self)
        result = run([interpreter, CONTRACT, "--adafruit=" + adafruit_dir(self)])
        self.assertPasses(result)
        self.assertIn("(micropython)", result.stdout)

    def test_a_dropped_status_byte_fails_it(self):
        result = run([sys.executable, CONTRACT, "--adafruit=" + adafruit_dir(self), "--plant=drop-status"])
        self.assertIn("PLANTED drop-status", result.stdout)
        self.assertNotEqual(result.returncode, 0, "the plant went unnoticed:\n" + result.stdout)
        self.assertIn("FAIL", result.stdout)

    def test_a_clock_byte_left_unstamped_fails_it(self):
        result = run([sys.executable, CONTRACT, "--adafruit=" + adafruit_dir(self),
                      "--plant=skip-clock-stamp"])
        self.assertIn("PLANTED skip-clock-stamp", result.stdout)
        self.assertNotEqual(result.returncode, 0, "the plant went unnoticed:\n" + result.stdout)
        for port in ("WholeMessages", "uart", "usb_device", "usb_host", "windows", "webmidi"):
            self.assertIn("FAIL stamps: " + port, result.stdout)
        self.assertIn("FAIL stamps: usb_host all_ports --", result.stdout)

    def test_a_merge_that_switches_device_mid_message_fails_it(self):
        result = run([sys.executable, CONTRACT, "--adafruit=" + adafruit_dir(self), "--plant=interleave"])
        self.assertIn("PLANTED interleave", result.stdout)
        self.assertNotEqual(result.returncode, 0, "the plant went unnoticed:\n" + result.stdout)
        self.assertIn("FAIL usb_host all_ports: two devices merged whole", result.stdout)
        self.assertIn("FAIL usb_host all_ports: a SysEx that stops", result.stdout)


def _make_asound(root, entries):
    """A synthetic /proc/asound: ``entries`` maps (card, device) to the body
    of its per-device file. The assertions then hold on a laptop with a
    keyboard, in CI with none, and under WSL, where ALSA has no cards."""
    os.makedirs(root, exist_ok=True)
    lines = ["  0: [ 0]   : control", "  1:        : sequencer"]
    for card, device in entries:
        lines.append("  4: [ {}- {}]: raw midi".format(card, device))
        card_dir = "{}/card{}".format(root, card)
        os.makedirs(card_dir, exist_ok=True)
        with open("{}/midi{}".format(card_dir, device), "w") as handle:
            handle.write(entries[(card, device)])
    lines.append(" 33:        : timer")
    with open(root + "/devices", "w") as handle:
        handle.write("\n".join(lines) + "\n")
    return root


class LinuxPort(unittest.TestCase):
    """ALSA raw MIDI, against synthetic /proc and /dev trees."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.proc = self.tmp + "/asound"
        self.dev = self.tmp + "/snd"
        os.makedirs(self.dev)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_cards_is_an_empty_tuple(self):
        _make_asound(self.proc, {})
        self.assertEqual(linux.available(self.proc), ())
        self.assertEqual(linux.available(self.tmp + "/does-not-exist"), ())

    def test_a_two_way_device_is_listed_once_per_direction(self):
        _make_asound(self.proc, {(0, 0): "DONNER DMK25Pro\n\nOutput 0\n  Tx bytes : 0\nInput 0\n"})
        found = linux.available(self.proc)
        self.assertEqual({p.id for p in found}, {"in:0:0", "out:0:0"})
        self.assertEqual({p.name for p in found}, {"DONNER DMK25Pro"})
        for p in found:
            self.assertIsInstance(p, midiports.PortInfo)

    def test_one_way_unnamed_and_unknown_devices(self):
        _make_asound(self.proc, {(1, 2): "Some Synth\n\nOutput 0\n", (3, 1): "\n\nInput 0\n",
                                 (4, 0): "Mystery\n"})
        found = {p.id: p for p in linux.available(self.proc)}
        self.assertEqual(set(found), {"out:1:2", "in:3:1", "in:4:0", "out:4:0"})
        self.assertEqual(found["in:3:1"].name, "card 3 device 1")

    def test_find_is_case_insensitive_and_filters_direction(self):
        _make_asound(self.proc, {(0, 0): "DONNER DMK25Pro\n\nOutput 0\nInput 0\n",
                                 (1, 0): "Some Synth\n\nOutput 0\n"})
        self.assertEqual({p.id for p in linux.find("donner", proc=self.proc)}, {"in:0:0", "out:0:0"})
        self.assertEqual({p.id for p in linux.find("donner", IN, proc=self.proc)}, {"in:0:0"})

    def test_ids_carry_the_alsa_address_and_bad_ones_are_refused(self):
        self.assertEqual(linux._split_id("out:2:3"), (OUT, 2, 3))
        for bad in ("", "out:0", "0:0", "sideways:0:0", "in:x:0"):
            self.assertRaises(ValueError, linux._split_id, bad)

    def test_ports_reads_and_writes_whole_messages(self):
        _make_asound(self.proc, {(0, 0): "Loop\n\nOutput 0\nInput 0\n"})
        device = self.dev + "/midiC0D0"
        with open(device, "wb") as handle:
            handle.write(b"\x90\x3c\x64\x3e\x50")  # running status, as a 5-pin cable sends
        midi_in, midi_out = linux.ports("loop", proc=self.proc, dev=self.dev)
        try:
            self.assertIsInstance(midi_in, WholeMessages)
            before = midiports.ticks_us()
            self.assertEqual(midi_in.read(64), b"\x90\x3c\x64\x90\x3e\x50")
            after = midiports.ticks_us()
            self.assertIsNone(midi_in.read(64))
            # One arrival time per note, taken by the read that found them.
            stamps = [midi_in.take_timestamp() for _ in range(3)]
            self.assertIsNone(stamps[2])
            self.assertEqual(stamps[0], stamps[1])
            self.assertTrue(before <= stamps[0] <= after)
            self.assertEqual(midi_out.write(b"\xb0\x07\x7f\x00", 3), 3)
        finally:
            midi_in.close()
            midi_out.close()
        self.assertRaises(OSError, midi_in.read, 4)
        self.assertRaises(OSError, midi_out.write, b"\xfa")
        midi_out.close()  # twice is fine

    def test_no_matching_port_says_so(self):
        _make_asound(self.proc, {})
        self.assertRaises(OSError, linux.ports, "nothing", proc=self.proc, dev=self.dev)


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux serial ports")
class LinuxSerialPort(unittest.TestCase):
    """DIN MIDI on a serial port, with a pty pair standing in for the cable:
    what's written to the master arrives at the port as a UART's bytes would."""

    # Running status, data bytes a cooked tty would eat (CR, LF, ^C, XON,
    # XOFF), a clock inside a note, one inside a SysEx, active sensing
    # between two control changes, then start and a clock.
    WIRE = (b"\x90\x3c\x0d", b"\x0a\x03\x90", b"\x11\xf8\x13",
            b"\xf0\x7d\x0d\x0a\xf8", b"\x11\x13\xf7\xb0\x07", b"\x7f\xfe\x07\x00\xfa\xf8")
    WHOLE = (b"\x90\x3c\x0d" b"\x90\x0a\x03" b"\xf8" b"\x90\x11\x13"
             b"\xf0\x7d\x0d\x0a\x11\x13\xf7" b"\xf8" b"\xb0\x07\x7f" b"\xfe" b"\xb0\x07\x00" b"\xfa" b"\xf8")
    MESSAGES = 11

    def setUp(self):
        self.master, slave = os.openpty()
        self.path = os.ttyname(slave)
        os.close(slave)
        self.midi_in, self.midi_out = linux.serial_ports(self.path)

    def tearDown(self):
        self.midi_in.close()
        self.midi_out.close()
        os.close(self.master)

    def _read(self, want):
        got = b""
        deadline = time.monotonic() + 2
        while len(got) < want and time.monotonic() < deadline:
            chunk = self.midi_in.read(64)
            if chunk:
                got += chunk
        return got

    def test_the_port_is_raw_at_31250_baud(self):
        import fcntl
        import termios

        fd = self.midi_out._fd
        raw = fcntl.ioctl(fd, linux._TCGETS2, bytes(44))
        self.assertEqual(struct.unpack(linux._TERMIOS2, raw)[-2:], (31250, 31250))
        iflag, oflag, cflag, lflag, _, _, cc = termios.tcgetattr(fd)
        self.assertEqual(lflag & (termios.ICANON | termios.ECHO | termios.ISIG), 0)
        self.assertEqual(iflag & (termios.ICRNL | termios.IXON), 0)
        self.assertEqual(oflag & termios.OPOST, 0)
        self.assertEqual(cflag & (termios.CSIZE | termios.PARENB | termios.CSTOPB), termios.CS8)
        self.assertEqual((cc[termios.VMIN], cc[termios.VTIME]), (0, 0))

    def test_a_rate_termios_names_is_set_directly(self):
        import termios

        midi_in, midi_out = linux.serial_ports(self.path, baudrate=38400)
        try:
            self.assertEqual(termios.tcgetattr(midi_out._fd)[4:6], [termios.B38400, termios.B38400])
        finally:
            midi_in.close()
            midi_out.close()

    def test_bytes_off_the_wire_come_out_as_whole_messages(self):
        self.assertIsInstance(self.midi_in, WholeMessages)
        self.assertIsNone(self.midi_in.read(64))
        got = b""
        for piece in self.WIRE:
            os.write(self.master, piece)
            got += self._read(1)
        got += self._read(len(self.WHOLE) - len(got))
        self.assertEqual(got.hex(" "), self.WHOLE.hex(" "))
        self.assertEqual(self.midi_in.desync, 0)
        stamps = [self.midi_in.take_timestamp() for _ in range(self.MESSAGES + 1)]
        self.assertNotIn(None, stamps[:-1])
        self.assertIsNone(stamps[-1])

    def test_adafruit_midi_reads_every_message(self):
        sys.path.insert(0, adafruit_dir(self))
        try:
            import adafruit_midi
            # Each message type is known once its module is imported.
            import adafruit_midi.control_change  # noqa: F401
            import adafruit_midi.note_on  # noqa: F401
            import adafruit_midi.start  # noqa: F401
            import adafruit_midi.system_exclusive  # noqa: F401
            import adafruit_midi.timing_clock  # noqa: F401
        finally:
            sys.path.pop(0)
        midi = adafruit_midi.MIDI(midi_in=self.midi_in, midi_out=self.midi_out)
        os.write(self.master, b"".join(self.WIRE))
        names = []
        deadline = time.monotonic() + 2
        while len(names) < self.MESSAGES and time.monotonic() < deadline:
            msg = midi.receive()
            if msg is not None:
                names.append(type(msg).__name__)
        self.assertEqual(names, ["NoteOn", "NoteOn", "TimingClock", "NoteOn", "SystemExclusive",
                                 "TimingClock", "ControlChange", "MIDIUnknownEvent", "ControlChange",
                                 "Start", "TimingClock"])

    def test_what_is_written_reaches_the_wire_unchanged(self):
        sent = b"\x80\x0a\x0d\xb0\x03\x11\xf0\x13\x7f\xf7\xf8"
        self.assertEqual(self.midi_out.write(sent), len(sent))
        got = b""
        deadline = time.monotonic() + 2
        while len(got) < len(sent) and time.monotonic() < deadline:
            got += os.read(self.master, 64)
        self.assertEqual(got, sent)

    def test_a_path_that_is_not_a_serial_port_is_refused(self):
        with tempfile.NamedTemporaryFile() as plain:
            self.assertRaises(OSError, linux.serial_ports, plain.name)


class _Obj:
    def __init__(self, **fields):
        self.__dict__.update(fields)


class _Port:
    def __init__(self, id, name, type):
        self.id, self.name, self.type, self.state = id, name, type, "connected"
        self.onmidimessage = None
        self.sent = []

    def send(self, data):
        self.sent.append(bytes(data))

    def play(self, data, stamp):
        self.onmidimessage(_Obj(data=data, timeStamp=stamp))


class _Map:
    def __init__(self, ports):
        self.ports = ports

    def values(self):
        return iter(self.ports)


class _Access:
    def __init__(self, inputs=(), outputs=()):
        self.inputs = _Map(list(inputs))
        self.outputs = _Map(list(outputs))
        self.listeners = []

    def addEventListener(self, kind, fn):
        self.listeners.append((kind, fn))

    def removeEventListener(self, kind, fn):
        self.listeners.remove((kind, fn))

    def change(self, port, state):
        port.state = state
        for _, fn in list(self.listeners):
            fn(_Obj(port=port))


class _MessagePort:
    def __init__(self):
        self.listeners = []
        self.posted = []

    def addEventListener(self, kind, fn):
        self.listeners.append((kind, fn))

    def removeEventListener(self, kind, fn):
        self.listeners.remove((kind, fn))

    def postMessage(self, message):
        self.posted.append(message)

    def deliver(self, payload):
        for _, fn in list(self.listeners):
            fn(_Obj(data=payload))


class WebMidiPort(unittest.TestCase):
    """Web MIDI, against fake MIDIAccess, MIDIPort and MessagePort objects."""

    def test_the_ring_keeps_whole_messages_and_drops_whole_ones_when_full(self):
        midi_in = webmidi._RingIn(ring=8)
        self.assertIsNone(midi_in.read(16))
        self.assertEqual(midi_in.any(), 0)
        for note in range(4):
            midi_in.push(bytes((0x90, note, 0x40)), note * 1000)
        self.assertEqual(midi_in.overflows, 2)  # 7 bytes fit: two notes, never a part
        self.assertEqual(midi_in.any(), 6)
        self.assertEqual(midi_in.read(4), b"\x90\x00\x40\x90")
        self.assertEqual(midi_in.any(), 2)
        buf = bytearray(8)
        self.assertEqual(midi_in.readinto(buf, 8), 2)
        self.assertEqual(bytes(buf[:2]), b"\x01\x40")
        self.assertEqual([midi_in.take_timestamp() for _ in range(3)], [0, 1000, None])
        for _ in range(5):  # wraps round the ring
            midi_in.push(b"\xb0\x07\x7f")
            self.assertEqual(midi_in.read(16), b"\xb0\x07\x7f")
        midi_in.close()
        self.assertRaises(OSError, midi_in.read, 4)
        self.assertRaises(OSError, midi_in.any)

    def test_timestamps_pair_with_messages_and_stale_ones_are_forgotten(self):
        midi_in = webmidi._RingIn(ring=16)
        midi_in.push(b"\x90\x3c\x64", 5250)
        before = midiports.ticks_us()
        midi_in.push(b"\xf8")  # no time given: stamped on arrival
        after = midiports.ticks_us()
        midi_in.push(b"\x80\x3c\x00", 9000)
        self.assertEqual(midi_in.take_timestamp(), 5250)
        self.assertTrue(before <= midi_in.take_timestamp() <= after)
        self.assertEqual(midi_in.take_timestamp(), 9000)
        self.assertIsNone(midi_in.take_timestamp())
        self.assertEqual(midi_in.read(16), b"\x90\x3c\x64\xf8\x80\x3c\x00")
        # A reader that never takes timestamps loses nothing else.
        for i in range(500):
            midi_in.push(b"\xf8", i)
            self.assertEqual(midi_in.read(4), b"\xf8")
        self.assertEqual(midi_in.overflows, 0)
        kept = len(midi_in._stamps)
        self.assertEqual(kept, 16 + 64)  # the ring stays its size
        self.assertEqual(midi_in.take_timestamp(), 500 - kept)  # the newest kept

    def test_ports_attach_by_name_and_merge_inputs(self):
        keys = _Port("i1", "Keystation 49", "input")
        pads = _Port("i2", "Pad Controller", "input")
        synth = _Port("o1", "Some Synth", "output")
        access = _Access([keys, pads], [synth])
        midi_in, midi_out = webmidi.ports(access, "KEYSTATION")
        self.assertEqual(midi_in.names, ["Keystation 49"])
        self.assertIsNone(pads.onmidimessage)
        self.assertIsNone(midi_out.name)
        midi_out.write(b"\x90\x3c\x64")
        self.assertEqual(midi_out.dropped, 1)
        both_in, both_out = webmidi.ports(access)
        keys.play(b"\x90\x3c\x64", 1.0)
        pads.play(b"\x99\x24\x7f", 2.0)
        self.assertEqual(both_in.read(16), b"\x90\x3c\x64\x99\x24\x7f")
        self.assertEqual(both_out.name, "Some Synth")
        both_out.write(b"\xb0\x07\x7f\xc0\x05")
        self.assertEqual(synth.sent, [b"\xb0\x07\x7f\xc0\x05"])

    def test_statechange_reattaches_a_port_that_comes_back(self):
        keys = _Port("i1", "Keys", "input")
        synth = _Port("o1", "Keys", "output")
        access = _Access([keys], [synth])
        midi_in, midi_out = webmidi.ports(access, "keys")
        access.change(keys, "disconnected")
        access.change(synth, "disconnected")
        self.assertIsNone(keys.onmidimessage)
        self.assertEqual(midi_in.names, [])
        self.assertIsNone(midi_out.name)
        access.change(keys, "connected")
        access.change(keys, "connected")  # opening fires another; still one handler
        access.change(synth, "connected")
        self.assertEqual(midi_in.names, ["Keys"])
        keys.play(b"\x90\x3c\x64", 3.0)
        self.assertEqual(midi_in.read(16), b"\x90\x3c\x64")
        self.assertEqual(midi_in.take_timestamp(), 3000)
        midi_out.write(b"\xfa")
        self.assertEqual(synth.sent, [b"\xfa"])
        late = _Port("i9", "Keys 2", "input")
        access.change(late, "connected")
        self.assertEqual(sorted(midi_in.names), ["Keys", "Keys 2"])
        other = _Port("i8", "Drums", "input")
        access.change(other, "connected")
        self.assertIsNone(other.onmidimessage)

    def test_closing_both_lets_go_of_every_port(self):
        keys = _Port("i1", "Keys", "input")
        access = _Access([keys], [_Port("o1", "Keys", "output")])
        midi_in, midi_out = webmidi.ports(access)
        midi_in.close()
        self.assertIsNone(keys.onmidimessage)
        self.assertEqual(len(access.listeners), 1)
        access.change(keys, "connected")  # a closed input attaches nothing
        self.assertIsNone(keys.onmidimessage)
        midi_out.close()
        midi_out.close()
        self.assertEqual(access.listeners, [])
        self.assertRaises(OSError, midi_out.write, b"\xfa")

    def test_open_requests_access_and_says_so_without_web_midi(self):
        access = _Access([_Port("i1", "Keys", "input")], [])
        asked = []

        async def fake_request(sysex):
            asked.append(sysex)
            return access

        real = webmidi._request_access
        webmidi._request_access = fake_request
        try:
            midi_in, _ = asyncio.run(webmidi.open("keys", sysex=True))
        finally:
            webmidi._request_access = real
        self.assertEqual(asked, [True])
        self.assertEqual(midi_in.names, ["Keys"])
        # Outside a browser there's no js module at all.
        self.assertRaises(ImportError, asyncio.run, webmidi.open())

    def _page_in(self, *messages, why=None, names="Keys"):
        """page_in() over a stand-in for the page's side of it."""
        waiting = [b for message in messages for b in message]
        closed = []
        page = _Obj(
            any=lambda: len(waiting),
            next=lambda: waiting.pop(0),
            names=lambda: names,
            why=lambda: why,
            overflows=lambda: 0,
            close=lambda: closed.append(True),
        )
        js = types.ModuleType("js")
        js.eval = lambda source: lambda name, limit: page
        with mock.patch.dict(sys.modules, {"js": js}):
            return webmidi.page_in("keys"), waiting, closed

    def test_page_in_reads_what_the_page_holds_and_no_more(self):
        midi_in, waiting, closed = self._page_in(b"\x90\x3c\x64", b"\x80\x3c\x00")
        self.assertEqual(midi_in.names, ["Keys"])
        self.assertEqual(midi_in.any(), 6)
        buf = bytearray(4)
        self.assertEqual(midi_in.readinto(buf), 4)
        self.assertEqual(bytes(buf), b"\x90\x3c\x64\x80")
        self.assertEqual(midi_in.read(16), b"\x3c\x00")
        self.assertIsNone(midi_in.readinto(buf))
        midi_in.close()
        self.assertEqual(closed, [True])
        self.assertRaises(OSError, midi_in.any)

    def test_page_in_says_when_it_has_nothing(self):
        midi_in, _, _ = self._page_in(why="NotAllowedError", names="")
        self.assertEqual(midi_in.names, [])
        self.assertEqual(midi_in.why, "NotAllowedError")

    @unittest.skipUnless(shutil.which("node"), "needs node")
    def test_page_in_javascript_follows_the_ports(self):
        script = """
const port = (name) => ({type: 'input', id: name, name, state: 'connected', onmidimessage: null});
const keys = port('Keys'), pads = port('Pads'), late = port('Late Keys');
const access = {inputs: new Map([['Keys', keys], ['Pads', pads]]), onstatechange: null};
Object.defineProperty(globalThis, 'navigator', {value: {requestMIDIAccess: async () => access}});
(async () => {
    const page = (%s)('KEYS', 6);
    const out = {before: page.names()};
    await null; await null;
    out.names = page.names();
    keys.onmidimessage({data: new Uint8Array([0x90, 60, 100])});
    out.pads = pads.onmidimessage;
    out.any = page.any();
    keys.onmidimessage({data: new Uint8Array([0x80, 60, 0])});
    keys.onmidimessage({data: new Uint8Array([0xf8])});
    out.full = [page.any(), page.overflows()];
    out.first = page.next();
    access.onstatechange({port: late});
    out.joined = page.names();
    keys.state = 'disconnected';
    access.onstatechange({port: keys});
    out.left = [page.names(), keys.onmidimessage];
    page.close();
    out.closed = [page.any(), late.onmidimessage, access.onstatechange];
    console.log(JSON.stringify(out));
})();
""" % webmidi._PAGE_IN
        got = json.loads(subprocess.run(
            ["node", "-e", script], capture_output=True, text=True, check=True, timeout=30).stdout)
        self.assertEqual(got["before"], "")
        self.assertEqual(got["names"], "Keys")  # "KEYS" matched, ignoring case; Pads didn't
        self.assertIsNone(got["pads"])
        self.assertEqual(got["any"], 3)
        self.assertEqual(got["full"], [6, 1])  # the third message would pass the limit
        self.assertEqual(got["first"], 0x90)
        self.assertEqual(got["joined"], "Keys\nLate Keys")
        self.assertEqual(got["left"], ["Late Keys", None])
        self.assertEqual(got["closed"], [0, None, None])

    @unittest.skipUnless(shutil.which("node"), "needs node")
    def test_page_in_javascript_reports_a_browser_without_web_midi(self):
        script = "Object.defineProperty(globalThis, 'navigator', {value: {}});" \
            "console.log((%s)('', 6).why())" % webmidi._PAGE_IN
        out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True, timeout=30).stdout
        self.assertIn("no Web MIDI", out)

    def _page_out(self, connected=True, accepts=True):
        """page_out() over a stand-in for the page's side of it."""
        page = _Obj(pending=[], sent=[], closed=[])

        def send():
            data, page.pending[:] = bytes(page.pending), []
            if not (connected and accepts):
                return False
            page.sent.append(data)
            return True

        page.put = page.pending.append
        page.send = send
        page.name = lambda: "Synth" if connected else None
        page.names = lambda: "Synth\nSynth 2" if connected else ""
        page.why = lambda: None if accepts else "InvalidAccessError"
        page.close = lambda: page.closed.append(True)
        js = types.ModuleType("js")
        js.eval = lambda source: lambda name: page
        with mock.patch.dict(sys.modules, {"js": js}):
            return webmidi.page_out("synth"), page

    def test_page_out_sends_whole_messages_to_the_page(self):
        midi_out, page = self._page_out()
        self.assertEqual(midi_out.name, "Synth")
        self.assertEqual(midi_out.names, ["Synth", "Synth 2"])
        self.assertEqual(midi_out.write(b"\x90\x3c"), 2)  # half a note waits
        self.assertEqual(page.sent, [])
        midi_out.write(b"\x64\xb0\x07\x7f")
        self.assertEqual(page.sent, [b"\x90\x3c\x64\xb0\x07\x7f"])
        midi_out.write(bytearray(b"\xf8"))
        self.assertEqual(page.sent[-1], b"\xf8")
        self.assertEqual(midi_out.dropped, 0)
        midi_out.close()
        self.assertEqual(page.closed, [True])
        self.assertRaises(OSError, midi_out.write, b"\xf8")
        midi_out.close()  # twice is fine
        self.assertEqual(page.closed, [True])

    def test_page_out_counts_what_has_nowhere_to_go(self):
        midi_out, page = self._page_out(connected=False)
        self.assertIsNone(midi_out.name)
        self.assertEqual(midi_out.names, [])
        midi_out.write(b"\x90\x3c\x64\x80\x3c\x00")
        self.assertEqual((page.sent, page.pending, midi_out.dropped), ([], [], 1))
        refused, _ = self._page_out(accepts=False)
        refused.write(b"\xf0\x7d\x01\xf7")
        self.assertEqual((refused.dropped, refused.why), (1, "InvalidAccessError"))

    @unittest.skipUnless(shutil.which("node"), "needs node")
    def test_page_out_javascript_follows_the_ports(self):
        script = """
const port = (name) => {
    const p = {type: 'output', id: name, name, state: 'connected', sent: []};
    p.send = (data) => { if (name === 'Picky') throw new TypeError('no SysEx'); p.sent.push(Array.from(data)); };
    return p;
};
const keys = port('Keys Out'), synth = port('Synth A'), spare = port('Synth B'), late = port('Synth C');
const outputs = new Map([['Keys Out', keys], ['Synth A', synth], ['Synth B', spare]]);
let listener = null;
const access = {
    outputs,
    addEventListener: (kind, fn) => { listener = fn; },
    removeEventListener: (kind, fn) => { if (fn === listener) listener = null; },
};
Object.defineProperty(globalThis, 'navigator', {value: {requestMIDIAccess: async () => access}});
const write = (page, bytes) => { for (const b of bytes) page.put(b); return page.send(); };
(async () => {
    const page = (%s)('SYNTH');
    const out = {before: [page.name(), page.names(), write(page, [0x90, 60, 100])]};
    await null; await null;
    out.name = page.name();
    out.names = page.names();
    out.sent = write(page, [0x90, 60, 100, 0xb0, 7, 127]);
    out.synth = synth.sent;
    out.keys = keys.sent;
    synth.state = 'disconnected';
    listener({port: synth});
    out.moved = [page.name(), page.names()];
    spare.state = 'disconnected';
    listener({port: spare});
    out.gone = [page.name(), write(page, [0xf8])];
    outputs.set('Synth C', late);
    listener({port: late});
    out.joined = page.name();
    write(page, [0xfa]);
    out.late = late.sent;
    page.close();
    out.closed = [page.name(), listener];
    const picky = (%s)('picky');
    outputs.set('Picky', port('Picky'));
    await null; await null;
    out.refused = [write(picky, [0xf0, 0x7d, 0xf7]), picky.why()];
    console.log(JSON.stringify(out));
})();
""" % (webmidi._PAGE_OUT, webmidi._PAGE_OUT)
        got = json.loads(subprocess.run(
            ["node", "-e", script], capture_output=True, text=True, check=True, timeout=30).stdout)
        self.assertEqual(got["before"], [None, "", False])  # nothing until the person says yes
        self.assertEqual(got["name"], "Synth A")  # "SYNTH" matched, ignoring case; Keys Out didn't
        self.assertEqual(got["names"], "Synth A\nSynth B")
        self.assertTrue(got["sent"])
        self.assertEqual(got["synth"], [[0x90, 60, 100, 0xB0, 7, 127]])
        self.assertEqual(got["keys"], [])
        self.assertEqual(got["moved"], ["Synth B", "Synth B"])  # another match takes the lost one's place
        self.assertEqual(got["gone"], [None, False])
        self.assertEqual(got["joined"], "Synth C")
        self.assertEqual(got["late"], [[0xFA]])
        self.assertEqual(got["closed"], [None, None])
        self.assertEqual(got["refused"], [False, "TypeError: no SysEx"])

    @unittest.skipUnless(shutil.which("node"), "needs node")
    def test_page_out_javascript_reports_a_browser_without_web_midi(self):
        script = "Object.defineProperty(globalThis, 'navigator', {value: {}});" \
            "console.log((%s)('').why())" % webmidi._PAGE_OUT
        out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True, timeout=30).stdout
        self.assertIn("no Web MIDI", out)

    def test_relay_input_takes_page_messages_with_their_timestamps(self):
        port = _MessagePort()
        midi_in, _ = webmidi.relay_ports(port)
        port.deliver(_Obj(data=b"\x90\x3c\x64", timeStamp=41.5))
        before = midiports.ticks_us()
        port.deliver(_Obj(data=b"\xf8"))  # no timeStamp: stamped on arrival
        after = midiports.ticks_us()
        port.deliver(_Obj(other=1))  # not MIDI: ignored
        self.assertEqual(midi_in.any(), 4)
        self.assertEqual(midi_in.read(16), b"\x90\x3c\x64\xf8")
        self.assertEqual(midi_in.take_timestamp(), 41500)
        self.assertTrue(before <= midi_in.take_timestamp() <= after)
        self.assertIsNone(midi_in.take_timestamp())
        midi_in.close()
        self.assertEqual(port.listeners, [])

    def test_relay_output_posts_whole_messages(self):
        port = _MessagePort()
        _, midi_out = webmidi.relay_ports(port)
        self.assertEqual(midi_out.write(b"\x3c\x90\x3c", 3), 3)  # a stray data byte, then half a note
        self.assertEqual(port.posted, [])
        midi_out.write(b"\x64\xf8\xf0\x7d")
        self.assertEqual(port.posted, [{"data": b"\x90\x3c\x64\xf8"}])
        midi_out.write(bytearray(b"\x01\x02\xf7\xb0\x07\x7f"))
        self.assertEqual(port.posted[-1], {"data": b"\xf0\x7d\x01\x02\xf7\xb0\x07\x7f"})
        midi_out.write(b"\xf0" + bytes(webmidi.PENDING_LIMIT))  # a SysEx that never ends
        self.assertEqual(midi_out.dropped, 1)
        midi_out.write(b"\xfa")
        self.assertEqual(port.posted[-1], {"data": b"\xfa"})



class UsbHostPort(unittest.TestCase):
    """midiports.usb_host on a fake usb.core device: packets in, bytes out."""

    @classmethod
    def setUpClass(cls):
        import types

        usb = types.ModuleType("usb")
        core = types.ModuleType("usb.core")

        class USBTimeoutError(OSError):
            pass

        core.USBTimeoutError = USBTimeoutError
        usb.core = core
        cls._saved = {k: sys.modules.get(k) for k in ("usb", "usb.core")}
        sys.modules["usb"], sys.modules["usb.core"] = usb, core
        sys.modules.pop("midiports.usb_host", None)
        from midiports import usb_host

        cls.usb_host, cls.core = usb_host, core

    @classmethod
    def tearDownClass(cls):
        for k, v in cls._saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v

    def _dev(self, incoming):
        core = self.core
        # A MIDIStreaming interface (class 1, subclass 3) with bulk 0x81/0x02.
        cfg = bytes((9, 2, 32, 0, 1, 1, 0, 0x80, 50, 9, 4, 1, 0, 2, 1, 3, 0, 0,
                     7, 5, 0x81, 2, 64, 0, 0, 7, 5, 0x02, 2, 64, 0, 0))

        class Dev:
            sent = []
            reads = []

            def configuration_descriptor(self):
                return cfg

            def read(self, ep, buf, timeout, raise_on_timeout=True):
                self.reads.append((timeout, raise_on_timeout))
                if not incoming:
                    if raise_on_timeout:
                        raise core.USBTimeoutError(110)
                    return 0
                pkt = incoming.pop(0)
                buf[:len(pkt)] = pkt
                return len(pkt)

            def write(self, ep, data, timeout):
                self.sent.append((ep, bytes(data)))
                return len(data)

            def _release_all(self):
                pass

        return Dev()

    def test_packets_read_as_whole_messages(self):
        # A note-on and the start of a SysEx in one packet, its end in the next.
        dev = self._dev([bytes((0x09, 0x90, 60, 100, 0x04, 0xF0, 0x7E, 0x7F)),
                         bytes((0x07, 0x06, 0x02, 0xF7))])
        midi_in, _ = self.usb_host.ports(dev)
        got = b""
        for _ in range(6):
            got += midi_in.read() or b""
        self.assertEqual(got, bytes((0x90, 60, 100, 0xF0, 0x7E, 0x7F, 0x06, 0x02, 0xF7)))

    def test_an_empty_poll_neither_waits_nor_raises(self):
        # A raise allocates on MicroPython and retires the transfer, and a
        # wait costs the whole poll: an idle keyboard would cost both.
        dev = self._dev([])
        midi_in, _ = self.usb_host.ports(dev)
        self.assertIsNone(midi_in.read())
        self.assertEqual(midi_in.any(), 0)
        self.assertTrue(dev.reads)
        self.assertEqual(set(dev.reads), {(-1, False)})

    def test_poll_ms_still_waits_when_asked(self):
        dev = self._dev([])
        midi_in, _ = self.usb_host.ports(dev, poll_ms=2)
        self.assertIsNone(midi_in.read())
        self.assertEqual(set(dev.reads), {(2, False)})

    def test_bytes_written_as_packets(self):
        dev = self._dev([])
        _, midi_out = self.usb_host.ports(dev)
        # Running status, a clock inside a note, then a short SysEx.
        midi_out.write(bytes((0x90, 60, 100, 62, 0xF8, 90, 0xF0, 0x7E, 0x7F, 0x06, 0x01, 0xF7)))
        (ep, data), = dev.sent
        self.assertEqual(ep, 0x02)
        self.assertEqual(data, bytes((0x09, 0x90, 60, 100, 0x0F, 0xF8, 0, 0, 0x09, 0x90, 62, 90,
                                      0x04, 0xF0, 0x7E, 0x7F, 0x07, 0x06, 0x01, 0xF7)))

    def test_all_ports_finds_every_midi_device(self):
        a = self._dev([bytes((0x09, 0x90, 60, 100))])
        b = self._dev([bytes((0x09, 0x91, 62, 90))])
        keyboard = self._dev([])
        keyboard.configuration_descriptor = lambda: bytes((9, 2, 18, 0, 1, 1, 0, 0x80, 50, 9, 4, 0, 0, 0, 3, 1, 1, 0))
        for k, dev in enumerate((a, keyboard, b)):
            dev._id = k + 1
        asked = []

        def find(find_all=False, custom_match=None):
            asked.append(find_all)
            return iter([d for d in (a, keyboard, b) if custom_match(d)])

        self.core.find = find
        try:
            midi_in, midi_out = self.usb_host.all_ports(rescan_ms=0)
        finally:
            del self.core.find
        self.assertEqual(asked, [True])
        self.assertEqual(midi_in.devices, [a, b])
        got = b""
        for _ in range(6):
            got += midi_in.read() or b""
        self.assertEqual(sorted((got[:3], got[3:])), [bytes((0x90, 60, 100)), bytes((0x91, 62, 90))])
        midi_out.write(bytes((0xC0, 5)))
        for dev in (a, b):
            self.assertEqual(dev.sent, [(0x02, bytes((0x0C, 0xC0, 5, 0)))])

    def test_a_device_without_midi_is_refused(self):
        dev = self._dev([])
        dev.configuration_descriptor = lambda: bytes((9, 2, 18, 0, 1, 1, 0, 0x80, 50, 9, 4, 0, 0, 0, 3, 1, 1, 0))
        self.assertFalse(self.usb_host.is_midi(dev))
        with self.assertRaises(ValueError):
            self.usb_host.ports(dev)



class LoopbackName(unittest.TestCase):
    def test_the_name_is_one_constant(self):
        self.assertEqual(midiports.LOOPBACK, "PyDevices Loopback")

    def test_windows_finds_the_port_by_that_name(self):
        fake = types.SimpleNamespace(
            midiOutGetNumDevs=lambda: 2, midiInGetNumDevs=lambda: 2,
            midiOutGetDevName=lambda i: ("Microsoft GS Wavetable Synth", midiports.LOOPBACK)[i],
            midiInGetDevName=lambda i: ("DMK25", midiports.LOOPBACK.lower())[i],
        )
        with mock.patch.dict(sys.modules, {"uwin32": fake}):
            sys.modules.pop("midiports.windows", None)
            try:
                from midiports import windows
                found = windows.find(midiports.LOOPBACK)
                self.assertEqual([(p.id, p.direction) for p in found], [("out:1", OUT), ("in:1", IN)])
            finally:
                sys.modules.pop("midiports.windows", None)
                midiports.__dict__.pop("windows", None)

    def test_a_missing_loopback_says_how_to_make_it(self):
        fake = types.SimpleNamespace(
            midiOutGetNumDevs=lambda: 0, midiInGetNumDevs=lambda: 0,
            midiOutGetDevName=None, midiInGetDevName=None,
        )
        with mock.patch.dict(sys.modules, {"uwin32": fake}):
            sys.modules.pop("midiports.windows", None)
            try:
                from midiports import windows
                with self.assertRaises(OSError) as caught:
                    windows.ports(midiports.LOOPBACK)
                self.assertIn("python -m midiports.loopback", str(caught.exception))
                with self.assertRaises(OSError) as other:
                    windows.ports("loopMIDI")
                self.assertNotIn("midiports.loopback", str(other.exception))
            finally:
                sys.modules.pop("midiports.windows", None)
                midiports.__dict__.pop("windows", None)


TABLE_WITH = (
    "\r\nWindows MIDI Services Console\r\n\r\nBasic MIDI 1.0 Loopback Endpoints\r\n"
    "\u2500\u2500\u2500\r\n"
    "\u256d\u2500\u2500\u252c\u2500\u2500\u256e\r\n"
    "\u2502 Association Id                         \u2502 Name               \u2502\r\n"
    "\u251c\u2500\u2500\u253c\u2500\u2500\u2524\r\n"
    "\u2502 {ff66db7e-6ea0-4745-ae42-413f79032ac3} \u2502 PyDevices Loopback \u2502\r\n"
    "\u2502 {00000000-0000-0000-0000-000000000000} \u2502 Other              \u2502\r\n"
    "\u2570\u2500\u2500\u2534\u2500\u2500\u256f\r\n"
)
TABLE_WITHOUT = "\r\nWindows MIDI Services Console\r\n\r\nNo basic loopback endpoints.\r\n"


class FakeMidiExe:
    """Stands in for ``subprocess.run`` on midi.exe: a list that ``create`` grows."""

    def __init__(self, present=False, saves=False, fail=None):
        self.present = present
        self.saves = saves
        self.fail = fail
        self.calls = []

    def __call__(self, argv, cwd=None, capture_output=None, check=None):
        self.calls.append((argv[1:], cwd))
        if self.fail:
            return subprocess.CompletedProcess(argv, 1, b"", self.fail.encode())
        if argv[1:3] == ["basic-loopback", "list"]:
            text = TABLE_WITH if self.present else TABLE_WITHOUT
        else:
            assert argv[1:3] == ["basic-loopback", "create"], argv
            assert argv[3:] == ["--name", midiports.LOOPBACK, "--save-to-config"], argv
            self.present = True
            text = ("\r\nWindows MIDI Services Console\r\n\r\nLoopback created.\r\n"
                    "  > Association Id                       {a0d834f0-d2fd-4d94-8861-b4b4f94a20a3}\r\n"
                    "  > Saved to Config                      " + ("Yes" if self.saves else "No") + "\r\n")
        return subprocess.CompletedProcess(argv, 0, text.encode("utf-8"), b"")


class LoopbackCommand(unittest.TestCase):
    def setUp(self):
        from midiports import loopback
        self.loopback = loopback
        self.programs = tempfile.TemporaryDirectory()
        self.addCleanup(self.programs.cleanup)
        tools = Path(self.programs.name, "Windows MIDI Services", "Tools")
        tools.mkdir(parents=True)
        (tools / "midi.exe").write_bytes(b"")
        self.said = []

    def _run(self, fake, **kw):
        kw.setdefault("platform", "win32")
        with mock.patch.object(self.loopback.subprocess, "run", fake):
            code = self.loopback.run(program_files=self.programs.name, out=self.said.append, **kw)
        return code

    def test_the_table_is_read_by_its_name_column(self):
        self.assertEqual(self.loopback.listed_names(TABLE_WITH), ["PyDevices Loopback", "Other"])
        self.assertEqual(self.loopback.listed_names(TABLE_WITHOUT), [])

    def test_a_present_port_is_left_alone(self):
        fake = FakeMidiExe(present=True)
        self.assertEqual(self._run(fake), 0)
        self.assertEqual(self.said, ["PyDevices Loopback: present"])
        self.assertEqual([c[0][1] for c in fake.calls], ["list"])

    def test_a_missing_port_is_created_and_the_unsaved_config_is_said(self):
        fake = FakeMidiExe()
        self.assertEqual(self._run(fake), 0)
        self.assertEqual([c[0][1] for c in fake.calls], ["list", "create", "list"])
        self.assertEqual(self.said[0], "PyDevices Loopback: created")
        self.assertEqual(len(self.said), 2)
        self.assertIn("midisettings.exe", self.said[1])
        self.assertIn("administrator", self.said[1])

    def test_a_saved_port_has_no_hint(self):
        self.assertEqual(self._run(FakeMidiExe(saves=True)), 0)
        self.assertEqual(self.said, ["PyDevices Loopback: created"])

    def test_check_reports_and_creates_nothing(self):
        fake = FakeMidiExe()
        self.assertEqual(self._run(fake, check=True), 1)
        self.assertEqual([c[0][1] for c in fake.calls], ["list"])
        self.assertIn("missing", self.said[0])
        self.assertEqual(self._run(FakeMidiExe(present=True), check=True), 0)

    def test_midi_exe_is_started_from_its_own_folder(self):
        fake = FakeMidiExe(present=True)
        self._run(fake)
        self.assertTrue(fake.calls[0][1].endswith("Tools"))

    def test_no_midi_exe_says_what_to_install(self):
        with tempfile.TemporaryDirectory() as empty:
            with self.assertRaises(self.loopback.LoopbackError) as caught:
                self.loopback.midi_exe(empty)
        self.assertIn("aka.ms/midi", str(caught.exception))
        code = self.loopback.run(platform="win32", program_files=tempfile.gettempdir() + "/nowhere", out=self.said.append)
        self.assertEqual(code, 2)
        self.assertIn("Install Windows MIDI Services", self.said[0])

    def test_a_midi_exe_failure_is_loud(self):
        self.assertEqual(self._run(FakeMidiExe(fail="service not running")), 2)
        self.assertIn("service not running", self.said[0])

    def test_other_systems_get_their_own_advice_and_nothing_is_run(self):
        for platform, word in (("linux", "snd-virmidi"), ("darwin", "IAC Driver")):
            self.said.clear()
            fake = FakeMidiExe()
            self.assertEqual(self._run(fake, platform=platform), 2)
            self.assertIn(word, self.said[0])
            self.assertEqual(fake.calls, [])

    def test_the_command_line_takes_check(self):
        with mock.patch.object(self.loopback, "run", return_value=1) as run:
            self.assertEqual(self.loopback.main(["--check"]), 1)
            run.assert_called_once_with(check=True)
            self.loopback.main([])
            self.assertFalse(run.call_args.kwargs["check"])


if __name__ == "__main__":
    unittest.main()
