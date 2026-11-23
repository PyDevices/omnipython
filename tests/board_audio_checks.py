# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""A board's audio_out following the ``audio.out`` choice, runnable on MicroPython and CPython.

    python tests/board_audio_checks.py        # from the repo root, or
    micropython tests/board_audio_checks.py

The board, its codec, a USB sound card and btclassic are stand-ins:
`audiodev.endpoints.route` and `audiodev.bt_audio` run on top of them as
they would on a board. BOARD_AUDIO_PLANT names a fault to plant; each one
fails these checks. test_board_audio.py runs this under both interpreters,
and every plant.
"""

import os
import sys

_root = os.getcwd()
for _p in ("lib", "utils", "packages/endpointkit"):
    sys.path.insert(0, _root + "/" + _p)

FAILS = []


def check(cond, what):
    if cond:
        print("ok   ", what)
    else:
        FAILS.append(what)
        print("FAIL ", what)


# -- a stand-in btclassic -----------------------------------------------------------


class Radio:
    """btclassic.Bluetooth: one radio, off until something turns it on."""

    made = 0

    def __init__(self):
        Radio.made += 1
        self.on = False
        self.inquiries = []
        self.answers = []
        self.looking = False

    def active(self, on=None):
        if on is not None:
            self.on = bool(on)
        return self.on

    def inquiry(self, duration_ms=10240):
        if not self.on:
            raise OSError("the radio is off")
        self.inquiries.append(duration_ms)
        self.looking = True

    def inquiring(self):
        return self.looking

    def found(self):
        return list(self.answers)


class Source:
    """btclassic.AudioSource: connects later, takes PCM while it streams."""

    sink_running = False
    made = []

    def __init__(self, bt, rate=44100, channels=2, buffer_ms=None):
        if Source.sink_running:
            raise OSError("an AudioSink is running")
        bt.active(True)
        Source.made.append(self)
        self.bt = bt
        self.rate = rate
        self.channels = channels
        self.connected = False
        self.streaming = False
        self.peer = None
        self.peer_name = ""
        self.status = None
        self.volume = 64
        self.asked = None
        self.capacity = 4096
        self.buffered = b""
        self.sent = b""
        self.closed = False

    def connect(self, addr=None):
        self.asked = addr

    def link_up(self, name):
        self.connected = True
        self.streaming = True
        self.peer = self.asked
        self.peer_name = name

    def link_down(self):
        self.connected = self.streaming = False
        self.peer = None

    def write(self, buf):
        if self.streaming:
            self.sent += bytes(buf)
            return len(buf)
        room = self.capacity - len(self.buffered)
        take = bytes(buf[:room]) if room > 0 else b""
        self.buffered += take
        return len(take)

    def stats(self):
        return {"buffered": len(self.buffered) // 4, "capacity": self.capacity // 4, "underruns": 0}

    def deinit(self):
        self.closed = True
        self.link_down()


class Btclassic:
    Bluetooth = Radio
    AudioSource = Source


sys.modules["btclassic"] = Btclassic

try:
    import audiocore  # noqa: F401
except ImportError:
    # AudioOut only loads audiocore here; nothing is pulled through it. CI's
    # CPython has no audiodsp installed.
    class _Audiocore:
        pass

    sys.modules["audiocore"] = _Audiocore

import endpointkit  # noqa: E402
from endpointkit.fake import FakeProvider  # noqa: E402

from audiodev import AudioCapability, AudioFactory, AudioFormat, I2SWire  # noqa: E402
from audiodev import bt_audio, endpoints  # noqa: E402
from audiodev.sample_out import AudioOut  # noqa: E402

PLANT = os.getenv("BOARD_AUDIO_PLANT")
if PLANT == "route_ignores_choice":
    endpoints.RoutedAudioOut.__call__ = lambda self, *a, **k: self.board.factory(*a, **k)
elif PLANT == "plays_before_link":
    def _any_chosen(registry=None):
        for ep in (registry or endpointkit.registry).selected("audio.out"):
            if hasattr(ep.provider, "open_out"):
                return ep
        return None
    endpoints.playing_on = _any_chosen
elif PLANT == "radio_at_register":
    _scan = bt_audio.BluetoothOut.scan

    def _always_looks(self):
        self._scans = max(self._scans, 1)
        return _scan(self)
    bt_audio.BluetoothOut.scan = _always_looks
elif PLANT == "no_drop_before_stream":
    bt_audio.SourceOutput._write = lambda self, buf: self.source.write(buf)
elif PLANT == "capability_lost":
    _init = endpoints.RoutedAudioOut.__init__

    def _no_cap(self, board, registry, capability=None):
        _init(self, board, registry, None)
    endpoints.RoutedAudioOut.__init__ = _no_cap

FMT = AudioFormat(44100, 2, 16)
SPEAKER = b"\xaa\xbb\xcc\x00\x11\x22"
PHONE = b"\x10\x20\x30\x40\x50\x60"


class Board:
    """A board_peripherals module: an I2S codec's audio_out, as a factory role."""

    def __init__(self):
        self.CAP = AudioCapability(FMT, wire=I2SWire(0, sck=1, ws=2, sd=3))
        self.opened = []

        def opens(format=None, **kwargs):
            self.opened.append((format, kwargs))
            return ("codec", format)

        self.audio_out = AudioFactory(opens, self.CAP)
        self.PERIPHERALS = frozenset({"audio_out"})
        self.FACTORY_ROLES = frozenset({"audio_out"})


class UsbCard(FakeProvider):
    """A sound card on the host port: connected while chosen, opened by open_out."""

    def __init__(self):
        FakeProvider.__init__(self, "audio.out", "usb-audio-out", [("0d8c-0014-i1", "USB Audio Device")])
        self.opened = []

    def apply(self, endpoint, chosen):
        FakeProvider.apply(self, endpoint, chosen)
        endpoint.state = endpointkit.CONNECTED if chosen else endpointkit.AVAILABLE

    def open_out(self, endpoint, format=None, **kwargs):
        self.opened.append((endpoint.id, format, kwargs))
        return ("usb", format)


def t_route():
    bp = Board()
    own = bp.audio_out
    reg = endpointkit.Registry()
    board = endpoints.route(bp, reg)
    check(isinstance(bp.audio_out, endpoints.RoutedAudioOut), "route puts a routed audio_out in the board's place")
    check(bp.audio_out.capability is bp.CAP, "it keeps the codec's capability")
    check(endpoints.route(bp, reg) is board, "routing again returns the same provider")
    eps = reg.endpoints("audio.out")
    check([e.id for e in eps] == ["board-out:main"], "the board's own output is listed: %r" % [e.id for e in eps])
    check(eps and eps[0].resources == ("i2s.0",), "it takes the codec's I2S port")
    check("device" not in eps[0].caps, "it names no device, so an app passes no device= to a board")

    got = bp.audio_out(FMT, latency="buffered")
    check(got == ("codec", FMT) and bp.opened[-1][1] == {"latency": "buffered"},
          "nothing chosen: audio_out opens the codec, with its arguments")

    usb = UsbCard()
    reg.register(usb)
    opens = []

    def follow(event, kind):
        # What mp3 and midiEngine do when audio.out moves: open audio_out again.
        if event in (endpointkit.SELECTION, endpointkit.STATE):
            opens.append(bp.audio_out(FMT, latency="buffered"))

    reg.subscribe("audio.out", follow)
    reg.select("audio.out", "usb-audio-out:0d8c-0014-i1")
    check(opens and opens[-1] == ("usb", FMT), "choosing the USB card: the app's reopen plays there (%r)" % opens[-1:])
    check(usb.opened and usb.opened[-1][2] == {"latency": "buffered"}, "with the app's keywords")
    check(bp.audio_out(FMT) == ("usb", FMT), "board_peripherals.audio_out opens the USB card now")

    reg.select("audio.out", ["board-out:main", "usb-audio-out:0d8c-0014-i1"])
    check(bp.audio_out(FMT) == ("codec", FMT), "the first chosen endpoint that's connected plays")
    reg.select("audio.out", "board-out:main")
    check(reg.find("board-out:main").state == endpointkit.CONNECTED, "the board's output, chosen, is connected")
    check(bp.audio_out(FMT) == ("codec", FMT), "choosing the board's own output plays on the codec")
    check(own is board.factory, "the board's own factory is the one it opens")

    fake = FakeProvider("audio.out", "fake", [("x", "Stand-in")])
    reg.register(fake)
    fake_ep = reg.find("fake:x")
    reg.select("audio.out", "fake:x")
    fake_ep.state = endpointkit.CONNECTED
    try:
        bp.audio_out(FMT)
        raised = None
    except ValueError as exc:
        raised = str(exc)
    check(raised and "can't open" in raised, "a chosen output a board can't open says so (%r)" % raised)
    reg.select("audio.out", None)

    flat = Board()
    flat.FACTORY_ROLES = frozenset()
    try:
        endpoints.route(flat, endpointkit.Registry())
        raised = None
    except ValueError as exc:
        raised = str(exc)
    check(raised and "factory" in raised, "a board whose audio_out isn't a factory can't be routed (%r)" % raised)
    return bp, reg


def _opened(bp):
    """What audio_out opens now, or the error it raised."""
    try:
        return bp.audio_out(FMT)
    except Exception as exc:  # noqa: BLE001 - a check reports it
        return repr(exc)


def t_bluetooth(bp, reg):
    Radio.made = 0
    bt = bt_audio.BluetoothOut()
    reg.register(bt)
    check(Radio.made == 0 and bt.bt is None, "registering touches no radio")
    check(not reg.endpoints("audio.out")[-1:] or reg.endpoints("audio.out")[-1].provider is not bt,
          "and lists no speaker before a scan")

    reg.refresh("audio.out")
    check(bt.bt is not None and bt.bt.on and bt.bt.inquiries == [bt_audio.INQUIRY_MS], "a scan turns the radio on and looks")
    bt.bt.answers = [(SPEAKER, "Desk speaker", 0x240414, -50), (PHONE, "Phone", 0x5A020C, -60)]
    bt.bt.looking = False
    reg.poll()
    found = [e for e in reg.endpoints("audio.out") if e.provider is bt]
    check([e.label for e in found] == ["Desk speaker"], "a scan lists speakers and leaves phones out: %r" % [e.label for e in found])
    sid = "bt-out:aabbcc001122"
    check(found and found[0].id == sid and found[0].resources == ("bt.a2dp",), "its id is its address; it takes A2DP")

    heard = []
    reg.subscribe("audio.out", lambda event, kind: heard.append(event))
    reg.select("audio.out", sid)
    src = bt.source
    check(src is not None and src.asked == SPEAKER, "choosing it connects to that speaker")
    check(reg.find(sid).state == endpointkit.AVAILABLE, "it isn't connected until the link is up")
    check(_opened(bp) == ("codec", FMT), "until then the codec plays: %r" % (_opened(bp),))

    src.link_up("Desk speaker")
    del heard[:]
    reg.poll()
    check(reg.find(sid).state == endpointkit.CONNECTED and endpointkit.STATE in heard,
          "the link coming up is a state change a following app hears")
    out = bp.audio_out(FMT, latency="buffered")
    check(isinstance(out, AudioOut) and isinstance(out.transport, bt_audio.SourceOutput),
          "once connected, audio_out is an AudioOut on the speaker")
    check(out.transport.source is src and out.chunk_ms == 40, "on the provider's source")

    pcm = out.transport
    tone = bytes([0x00, 0x40] * 64)  # 16384 in every sample
    pcm.write(tone)
    check(src.sent == tone and src.status == "playing", "PCM reaches the speaker as written")
    pcm.set_volume(50)
    pcm.write(tone)
    half = src.sent[len(tone):len(tone) + 2]
    check(len(half) == 2 and abs((half[0] | half[1] << 8) - 8192) <= 1, "volume is applied in software: %r" % half)
    check(src.volume == 64, "and leaves the speaker's own volume alone")

    src.link_down()
    reg.poll()
    check(reg.find(sid).state == endpointkit.AVAILABLE, "a dropped link is AVAILABLE again")
    check(_opened(bp) == ("codec", FMT), "and the codec plays until it's back: %r" % (_opened(bp),))
    try:
        bt.open_out(reg.find(sid), FMT)
        raised = None
    except OSError as exc:
        raised = str(exc)
    check(raised and "isn't connected" in raised, "opening a speaker that isn't connected says so (%r)" % raised)

    waiting = bt_audio.SourceOutput(src, FMT)
    try:
        waiting.write(bytes(4096 + 1024))
        failed = None
    except OSError as exc:
        failed = str(exc)
    check(failed is None and waiting.dropped == 1024 and len(src.buffered) == 4096,
          "before the stream runs, the source holds what fits and the rest is dropped and counted (%r, %d)"
          % (failed, waiting.dropped))
    check(waiting.stats()["dropped"] == 1024, "stats() counts what was dropped")
    try:
        bt_audio.SourceOutput(src, AudioFormat(44100, 2, 32))
        raised = None
    except ValueError as exc:
        raised = str(exc)
    check(raised and "16-bit" in raised, "a speaker takes 16-bit PCM only (%r)" % raised)

    reg.select("audio.out", None)
    check(src.closed and bt.source is None, "letting the speaker go stops the source")

    Source.sink_running = True
    del heard[:]
    reg.select("audio.out", sid)
    check(reg.find(sid).error and endpointkit.ERROR in heard,
          "while the board is a Bluetooth speaker, choosing one fails with the reason on it: %r" % reg.find(sid).error)
    Source.sink_running = False
    reg.select("audio.out", None)

    bt.bt.answers.append((b"\x01\x02\x03\x04\x05\x06", "Headphones", 0x240404, -40))
    reg.refresh("audio.out")
    bt.bt.looking = False
    reg.poll()
    try:
        reg.select("audio.out", [sid, "bt-out:010203040506"])
        raised = None
    except endpointkit.Conflict as exc:
        raised = exc
    check(raised is not None and "bt.a2dp" in raised.resources, "two speakers at once conflict over A2DP")
    reg.unregister(bt)


def t_register():
    reg = endpointkit.Registry()
    bt_audio._registered[:] = []
    first = bt_audio.register(reg)
    check(isinstance(first, bt_audio.BluetoothOut) and bt_audio.register(reg) is first, "register makes one provider, once")
    reg.unregister(first)
    bt_audio._registered[:] = []
    saved = Btclassic.AudioSource
    del Btclassic.AudioSource
    try:
        bt_audio.register(endpointkit.Registry())
        raised = None
    except OSError as exc:
        raised = str(exc)
    Btclassic.AudioSource = saved
    check(raised and "AudioSource" in raised, "btclassic without an A2DP source: register says so (%r)" % raised)


bp, reg = t_route()
t_bluetooth(bp, reg)
t_register()

if FAILS:
    print("%d failed" % len(FAILS))
    sys.exit(1)
print("all checks passed on %s" % sys.implementation.name)
