# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""Checks of the desktop endpointkit providers, runnable on MicroPython and CPython.

    python tests/endpoint_providers_checks.py           # from the repo root, or
    micropython tests/endpoint_providers_checks.py

Each provider runs against a stand-in for its hardware, then once against
the host to show it lists without failing. test_endpoint_providers.py runs
this under both interpreters.
"""

import os
import sys

_root = os.getcwd()
for _p in ("lib", "utils", "packages/endpointkit", "packages/midiports", "packages/castdisplay"):
    sys.path.insert(0, _root + "/" + _p)

import endpointkit  # noqa: E402
from endpointkit import Registry  # noqa: E402

FAILS = []


def check(cond, what):
    if not cond:
        FAILS.append(what)
        print("FAIL", what)


def ids(eps):
    return [ep.id for ep in eps]


# -- MIDI ------------------------------------------------------------------------


class FakePortIn:
    def __init__(self, data):
        self.data = list(data)
        self.closed = False

    def readinto(self, buf, nbytes=None):
        if not self.data:
            return None
        chunk = self.data.pop(0)
        buf[: len(chunk)] = chunk
        return len(chunk)

    def any(self):
        return sum(len(c) for c in self.data)

    def take_timestamp(self):
        return 7

    def close(self):
        self.closed = True


class FakePortOut:
    def __init__(self):
        self.sent = []
        self.closed = False

    def write(self, buf, nbytes=None):
        self.sent.append(bytes(buf[:nbytes]))
        return nbytes

    def close(self):
        self.closed = True


class FakeMidiBackend:
    __name__ = "midiports.fakemidi"

    def __init__(self):
        from midiports import PortInfo

        self.PortInfo = PortInfo
        self.ports = [
            PortInfo("in:0", "Keys", "in"),
            PortInfo("in:1", "Pad", "in"),
            PortInfo("in:2", "Pad", "in"),
            PortInfo("out:0", "Synth", "out"),
            PortInfo("out:1", "Drums", "out"),
        ]
        self.opened = {}

    def available(self):
        return tuple(self.ports)

    def open_port(self, info):
        port = FakePortIn([b"\x90\x3c\x40"]) if info.direction == "in" else FakePortOut()
        self.opened[info.id] = port
        return port


def t_midi():
    from midiports import IN, OUT
    from midiports.endpoints import FanOut, HostMidi, Merged

    r = Registry()
    be = FakeMidiBackend()
    ins = r.register(HostMidi(IN, be, rescan_ms=0))
    outs = r.register(HostMidi(OUT, be, rescan_ms=0))
    check(ids(r.endpoints("midi.in")) == ["fakemidi-midi-in:Keys", "fakemidi-midi-in:Pad", "fakemidi-midi-in:Pad #2"], "MIDI inputs by name, twins numbered")
    check(ids(r.endpoints("midi.out")) == ["fakemidi-midi-out:Synth", "fakemidi-midi-out:Drums"], "MIDI outputs")
    r.select("midi.in", ["fakemidi-midi-in:Keys", "fakemidi-midi-in:Pad #2"])
    check(sorted(be.opened) == ["in:0", "in:2"], "choosing opens the ports")
    merged = Merged(ins)
    buf = bytearray(8)
    got = [merged.readinto(buf), merged.readinto(buf), merged.readinto(buf)]
    check(got == [3, 3, None], "merged input reads every chosen port")
    check(merged.take_timestamp() == 7, "merged stamps come from the port read")
    r.select("midi.out", ["fakemidi-midi-out:Synth", "fakemidi-midi-out:Drums"])
    FanOut(outs).write(b"\x80\x3c\x00")
    check(be.opened["out:0"].sent == [b"\x80\x3c\x00"] and be.opened["out:1"].sent == [b"\x80\x3c\x00"], "fan-out writes to each")
    r.select("midi.in", "fakemidi-midi-in:Keys")
    check(be.opened["in:2"].closed and not be.opened["in:0"].closed, "letting go closes the port")
    from midiports import PortInfo

    be.ports.append(PortInfo("in:3", "Late keyboard", "in"))
    r.poll()
    check("fakemidi-midi-in:Late keyboard" in ids(r.endpoints("midi.in")), "a port plugged in later is found")
    be.ports = [p for p in be.ports if p.name != "Keys"]
    r.poll()
    check(be.opened["in:0"].closed, "an unplugged chosen port is closed")
    check(r.selection("midi.in") == ["fakemidi-midi-in:Keys"], "and stays chosen")


# -- audio -----------------------------------------------------------------------


def t_audio():
    from audiodev.endpoints import HostAudio, device, devices

    names = {False: ["Speakers", "Headphones"], True: ["Microphone"]}
    r = Registry()
    out = r.register(HostAudio(False, "win_audio", lambda b, c: names[c], rescan_ms=0))
    r.register(HostAudio(True, "win_audio", lambda b, c: names[c], rescan_ms=0))
    check(ids(r.endpoints("audio.out")) == ["win_audio-out:default", "win_audio-out:Speakers", "win_audio-out:Headphones"], "outputs with the default first")
    check(ids(r.endpoints("audio.in")) == ["win_audio-in:default", "win_audio-in:Microphone"], "inputs")
    check(device("audio.out", r) is None, "nothing chosen plays on the default")
    r.select("audio.out", ["win_audio-out:Headphones", "win_audio-out:Speakers"])
    check(device("audio.out", r) == "Headphones", "device is the first choice's name")
    check(devices("audio.out", r) == ["Headphones", "Speakers"], "devices lists every choice")
    names[False].append("USB card")
    check(r.poll() and "win_audio-out:USB card" in ids(r.endpoints("audio.out")), "a device plugged in later is found")

    def broken(b, c):
        raise OSError("no audio service")

    r2 = Registry()
    r2.register(HostAudio(False, "win_audio", broken))
    check(ids(r2.endpoints("audio.out")) == ["win_audio-out:default"], "a backend that can't list still offers the default")
    del out


# -- cast ------------------------------------------------------------------------


class FakeUdp:
    def __init__(self):
        self.inbox = []
        self.sent = 0

    def sendto(self, data, dest):
        self.sent += 1

    def recv(self, n):
        if not self.inbox:
            raise OSError(11)
        return self.inbox.pop(0)

    def close(self):
        pass


def answer(host, serial=None):
    usn = b"USN: uuid:roku:ecp:%s\r\n" % serial.encode() if serial else b""
    return b"HTTP/1.1 200 OK\r\nST: roku:ecp\r\n" + usn + b"LOCATION: http://%s:8060/\r\n\r\n" % host.encode()


def t_cast():
    from castdisplay import endpoints as ce

    infos = {"10.0.0.5": {"serial": "X1", "name": "Den TV", "model": "Roku Ultra"}}
    asked = []

    def info(host):
        asked.append(host)
        if host not in infos:
            raise OSError("no answer")
        return infos[host]

    sock = FakeUdp()
    r = Registry()
    roku = r.register(ce.Rokus(rescan_ms=0, info=info, sock=sock, ask=lambda h: h != "10.0.0.8"))
    check(r.endpoints("cast.target") == [] and sock.sent == 1, "the first scan asks the network")
    sock.inbox = [answer("10.0.0.5"), answer("10.0.0.5"), b"junk", answer("10.0.0.9", "S9"), answer("10.0.0.8", "S8")]
    r.poll()
    eps = r.endpoints("cast.target")
    check(ids(eps) == ["roku:X1", "roku:S9", "roku:S8"] and eps[0].label == "Roku: Den TV", "Rokus appear by serial, one with its name")
    check(eps[1].label == "Roku at 10.0.0.9", "a Roku that won't say its name is listed by address")
    check("10.0.0.8" not in asked, "a Roku ask refuses is never asked")
    for _ in range(ce.MISSES + 1):
        sock.inbox = [answer("10.0.0.5")]
        r.poll()
    eps = r.endpoints("cast.target")
    check(eps[0].caps == {"host": "10.0.0.5", "model": "Roku Ultra", "type": "roku"}, "caps hold the host")
    check(asked.count("10.0.0.5") == 1, "its name is asked once")
    r.select("cast.target", "roku:X1")
    # A round is judged by the next search, so MISSES quiet rounds take one poll more.
    for _ in range(ce.MISSES):
        r.poll()
    check(ids(r.endpoints("cast.target")) == ["roku:X1"], "a Roku survives a few quiet rounds")
    r.poll()
    check(ids(r.endpoints("cast.target")) == [] and r.selection("cast.target") == ["roku:X1"], "a Roku gone too long goes; the choice stays")
    infos["10.0.0.7"] = infos["10.0.0.5"]
    sock.inbox = [answer("10.0.0.7")]
    r.poll()
    check(r.selected("cast.target")[0].caps["host"] == "10.0.0.7", "a TV at a new address is still the chosen one")
    del roku


# -- input -----------------------------------------------------------------------


def t_input():
    from displaydev.endpoints import Fixed, Gamepads

    pads = ["Xbox Controller", "Xbox Controller"]
    r = Registry()
    r.register(Fixed("keys", "host-keys", "keyboard", "Computer keyboard"))
    r.register(Gamepads(lambda: pads, rescan_ms=0))
    check(ids(r.endpoints("keys")) == ["host-keys:keyboard"], "the keyboard is always there")
    check(ids(r.endpoints("gamepad")) == ["host-gamepad:Xbox Controller", "host-gamepad:Xbox Controller #2"], "twin gamepads numbered")
    pads.pop()
    check(r.poll() and len(r.endpoints("gamepad")) == 1, "a gamepad gone is noticed")


# -- network ---------------------------------------------------------------------


def t_net():
    import hostnet

    r = Registry()
    addr = ["192.168.9.9"]
    net = r.register(hostnet.HostNet(lambda: addr[0], lambda: ["eth0", "wlan0"], rescan_ms=0))
    eps = r.endpoints("net")
    check(ids(eps) == ["host-net:default", "host-net:eth0", "host-net:wlan0"], "default link first, then interfaces")
    check(eps[0].state == endpointkit.CONNECTED and eps[0].label == "Network (192.168.9.9)", "the default link shows its address")
    r.select("net", "host-net:eth0")
    check(r.find("host-net:eth0").error is not None, "choosing another link is refused")
    r.select("net", "host-net:default")
    check(r.find("host-net:default").error is None, "the default link can be chosen")
    addr[0] = None
    r.poll()
    check(r.find("host-net:default").state == endpointkit.UNAVAILABLE, "no route shows as unavailable")
    del net


# -- the real host ---------------------------------------------------------------


def t_host():
    import hostnet
    from displaydev.endpoints import joystick_names

    a = hostnet.default_address()
    check(a is None or a.count(".") == 3, "default_address is an address or None: %r" % (a,))
    check(isinstance(joystick_names(), list), "joystick_names lists")
    r = Registry()
    hostnet.register(r)
    check(r.selection("net") == ["host-net:default"], "registering adopts the host's network")
    try:
        from audiodev.endpoints import HostAudio

        p = r.register(HostAudio(False))
        check(r.endpoints("audio.out")[0].local_id == "default", "the host's audio lists: %r" % ids(r.endpoints("audio.out")))
        print("host audio outputs:", [ep.label for ep in r.endpoints("audio.out")])
        del p
    except ImportError as exc:
        print("no audio backend here:", exc)


def test_all():
    del FAILS[:]
    for name, fn in sorted(globals().items()):
        if name.startswith("t_"):
            fn()
    assert not FAILS, FAILS


if __name__ == "__main__":
    test_all()
    print("endpoint providers: all checks passed on", sys.implementation.name)
