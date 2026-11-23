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

import binascii
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

    def read(self, nbytes=None):
        buf = bytearray(64)
        n = self.readinto(buf, nbytes)
        return bytes(buf[:n]) if n else None

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


class _Raw:
    """A raw byte source that hands its bytes out ``step`` at a time."""

    def __init__(self, data, step):
        self.data = bytes(data)
        self.step = step

    def readinto(self, buf, nbytes=None):
        n = min(self.step, len(self.data), len(buf) if nbytes is None else nbytes)
        if not n:
            return None
        buf[:n] = self.data[:n]
        self.data = self.data[n:]
        return n


def t_merged_sysex():
    from midiports import WholeMessages
    from midiports.endpoints import Merged

    sysex = b"\xf0" + bytes(i % 128 for i in range(298)) + b"\xf7"
    note = b"\x90\x40\x7f"

    class One:
        open = {"a": WholeMessages(_Raw(note + sysex, 20))}

    merged = Merged(One())
    got = [merged.read(), merged.read(), merged.read()]
    check(got == [note, sysex, None], "merged read() hands a 300-byte SysEx out whole")


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
    r.select("midi.in", ["fakemidi-midi-in:Keys", "fakemidi-midi-in:Pad"])  # Pad opens fresh
    got = [Merged(ins).read(), Merged(ins).read()]
    check(got == [b"\x90\x3c\x40", None], "merged read() reads a chosen port")
    r.select("midi.in", ["fakemidi-midi-in:Keys", "fakemidi-midi-in:Pad #2"])
    t_merged_sysex()
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


class FakeStation:
    """wifi_manager's radio: networks in range, the one it's on, and joins
    that work with the right password ("wrong password" otherwise)."""

    def __init__(self, seen, passwords, on=None):
        self.seen = seen
        self.passwords = passwords
        self.on = on
        self.joins = []
        self.surveys = 0

    def survey(self):
        self.surveys += 1
        return dict(self.seen)

    def ssid(self):
        return self.on

    def ip(self):
        return "10.0.0.7" if self.on else None

    def join(self, ssid, password, timeout):
        self.joins.append(ssid)
        if ssid not in self.seen:
            return "network not found"
        if self.passwords.get(ssid, "") != password:
            return "wrong password"
        self.on = ssid
        return None


def t_wifi():
    import wifi_manager
    import wifinet

    store = [{"ssid": "Home", "password": "homepw"}]
    saved = (wifi_manager._known, wifi_manager._remember)
    wifi_manager._known = lambda module="secrets": list(store)

    def remember(ssid, password, hidden=False):
        store[:] = [n for n in store if n["ssid"] != ssid]
        store.insert(0, {"ssid": ssid, "password": password})

    wifi_manager._remember = remember
    try:
        seen = {"Home": (-50, True), "Cafe": (-70, True), "Library": (-60, False), "Office": (-40, True)}
        radio = FakeStation(seen, {"Home": "homepw", "Cafe": "espresso", "Office": "officepw"}, on="Home")
        r = Registry()
        wifinet._provider[:] = []
        rescan, wifinet.RESCAN_MS = wifinet.RESCAN_MS, 0
        wifinet.register(r, radio)
        wifinet.RESCAN_MS = rescan
        check(r.selection("net") == ["wifi:Home"], "registering adopts the network the board is on")
        check(radio.surveys == 0, "registering doesn't scan: it holds the interpreter")
        check(ids(r.endpoints("net")) == ["wifi:Home"], "before a scan only the joined network shows")
        r.poll()
        check(radio.surveys == 1, "the first poll after a scan was asked for scans")
        check(ids(r.endpoints("net")) == ["wifi:Office", "wifi:Home", "wifi:Library", "wifi:Cafe"], "networks list strongest first")
        states = dict((ep.local_id, ep.state) for ep in r.endpoints("net"))
        check(states["Home"] == endpointkit.CONNECTED, "the joined network is connected")
        check(states["Library"] == endpointkit.AVAILABLE, "an open network needs no password")
        check(states["Cafe"] == endpointkit.NEEDS_PAIRING and r.find("wifi:Cafe").asks == endpointkit.PASSWORD, "a new secured network asks for its password")
        check(r.find("wifi:Home").caps["address"] == "10.0.0.7", "the joined network carries the board's address")
        r.poll()
        check(radio.surveys == 1, "polling doesn't scan again until asked")
        try:
            r.pair("wifi:Cafe", "latte")
            check(False, "a wrong password is refused")
        except ValueError as exc:
            check(str(exc) == "Wrong password for Cafe", "the refusal says the password was wrong: %s" % exc)
        check(r.find("wifi:Cafe").state == endpointkit.NEEDS_PAIRING and "Cafe" not in [n["ssid"] for n in store], "a failed join remembers nothing")
        ep = r.pair("wifi:Cafe", "espresso")
        check(ep.state == endpointkit.CONNECTED, "the right password joins")
        check(store[0] == {"ssid": "Cafe", "password": "espresso"}, "a joined network is remembered for the next boot")
        check(r.find("wifi:Home").state == endpointkit.AVAILABLE, "the network it left is still known")
        r.select("net", "wifi:Cafe")
        check(r.find("wifi:Cafe").error is None and radio.joins[-1] == "Cafe", "choosing the network it's on joins nothing more")
        net = r.providers("net")[0]
        net.rescan_ms = 60000
        r.poll()  # the scan pair() asked for
        r.select("net", "wifi:Home")
        check(radio.on == "Home" and r.find("wifi:Home").error is None, "choosing a known network joins it with its saved password")
        r.poll()
        check(r.find("wifi:Home").state == endpointkit.CONNECTED, "the next poll shows the network it joined, without waiting rescan_ms")
        net.rescan_ms = 0
        r.select("net", "wifi:Office")
        check(radio.on == "Home" and "join it first" in (r.find("wifi:Office").error or ""), "choosing an unknown secured network is refused")
        r.select("net", "wifi:Library")
        check(radio.on == "Library", "choosing an open network joins it")
        radio.on = None
        r.poll()
        check(all(ep.state != endpointkit.CONNECTED for ep in r.endpoints("net")), "a dropped link shows within a poll")
        r.refresh("net")
        del seen["Cafe"]
        r.poll()
        check("wifi:Cafe" not in ids(r.endpoints("net")), "a scan asked for by refresh drops networks out of range")
    finally:
        wifi_manager._known, wifi_manager._remember = saved
        wifinet._provider[:] = []


# -- ESP-NOW ---------------------------------------------------------------------


class FakeAir:
    """Radios in range of each other: what one sends, the others hear."""

    def __init__(self):
        self.radios = []


class FakeEspNow:
    """MicroPython's espnow.ESPNow in the air: a unicast needs its peer added
    first, a broadcast reaches every other radio, and recv is never asked
    to wait."""

    BROADCAST = b"\xff" * 6

    def __init__(self, air, mac):
        self.air = air
        self.mac = mac
        self.peers = []
        self.queue = []
        self.sent = []
        self.waits = []
        self.peers_table = {}
        air.radios.append(self)

    def add_peer(self, mac):
        if mac in self.peers:
            raise OSError(-12395, "ESP_ERR_ESPNOW_EXIST")
        self.peers.append(mac)

    def del_peer(self, mac):
        if mac not in self.peers:
            raise OSError(-12393, "ESP_ERR_ESPNOW_NOT_FOUND")
        self.peers.remove(mac)

    def send(self, mac, msg, sync=True):
        if mac not in self.peers:
            raise OSError(-12393, "ESP_ERR_ESPNOW_NOT_FOUND")
        self.sent.append((mac, bytes(msg), sync))
        for radio in self.air.radios:
            if radio is not self and mac in (self.BROADCAST, radio.mac):
                radio.queue.append((self.mac, bytes(msg)))
        return True

    def recv(self, timeout_ms=None):
        if timeout_ms != 0:
            self.waits.append(timeout_ms)
        if not self.queue:
            return None, None
        mac, msg = self.queue.pop(0)
        self.peers_table[mac] = [-42, 0]
        return mac, msg


def t_espnow():
    import espnowpeers
    from endpointkit.fake import FakeProvider

    clock = [1000]
    saved = (espnowpeers._ticks_ms, espnowpeers._ticks_diff)
    espnowpeers._ticks_ms = lambda: clock[0]
    espnowpeers._ticks_diff = lambda a, b: a - b
    try:
        air = FakeAir()
        mac_a, mac_b, mac_c = b"\xdc\xda\x0c\x00\x00\x0a", b"\xdc\xda\x0c\x00\x00\x0b", b"\xdc\xda\x0c\x00\x00\x0c"
        ra, rb, rc = FakeEspNow(air, mac_a), FakeEspNow(air, mac_b), FakeEspNow(air, mac_c)
        stranger = FakeEspNow(air, b"\x12\x34\x56\x78\x9a\xbc")
        a, b, c = Registry(), Registry(), Registry()
        espnowpeers._provider[:] = []
        pa = espnowpeers.register(a, ra, "kitchen")
        check(endpointkit.KINDS["espnow.peer"] == endpointkit.MANY and endpointkit.title("espnow.peer") == "ESP-NOW peers", "registering makes the kind known")
        check(espnowpeers.register(a) is pa and len(a.providers("espnow.peer")) == 1, "registering again returns the same provider")
        pb = b.register(espnowpeers.EspNowPeers(rb, "desk"))
        pc = c.register(espnowpeers.EspNowPeers(rc, "porch"))
        check(a.endpoints("espnow.peer") == [], "nothing is listed before anything is heard")
        a.poll()
        b.poll()
        c.poll()
        a.poll()
        desk, porch, kitchen = "espnow:dcda0c00000b", "espnow:dcda0c00000c", "espnow:dcda0c00000a"
        check(ids(a.endpoints("espnow.peer")) == [desk, porch], "boards are listed by name after one poll each: %r" % ids(a.endpoints("espnow.peer")))
        check([ep.label for ep in a.endpoints("espnow.peer")] == ["desk", "porch"], "labels are the boards' names")
        check(kitchen in ids(b.endpoints("espnow.peer")), "each board lists the others")
        ep = a.find(desk)
        check(ep.state == endpointkit.AVAILABLE and ep.caps["mac"] == "dc:da:0c:00:00:0b" and ep.caps["rssi"] == -42, "a peer carries its MAC and signal: %r" % (ep.caps,))
        sent = len(ra.sent)
        a.poll()
        check(len(ra.sent) == sent, "no beacon before beacon_ms")
        clock[0] += espnowpeers.BEACON_MS
        a.poll()
        check(len(ra.sent) == sent + 1 and ra.sent[-1][0] == FakeEspNow.BROADCAST and ra.sent[-1][2] is False, "a beacon every beacon_ms, broadcast, not waited on")
        check(ra.waits == [], "reads never wait: %r" % ra.waits)
        stranger.add_peer(FakeEspNow.BROADCAST)
        stranger.send(FakeEspNow.BROADCAST, b"another program's message")
        ignored = pa.ignored
        a.poll()
        check(ids(a.endpoints("espnow.peer")) == [desk, porch] and pa.ignored == ignored + 1, "another program's messages are passed by")
        wifi = FakeProvider("net", "wifi", [("Home", "Home")], ("radio.wifi",))
        a.register(wifi)
        a.select("net", "wifi:Home")
        check(a.conflicts("espnow.peer", [desk, porch]) == ([], []), "choosing peers stops neither each other nor Wi-Fi")
        b.select("espnow.peer", kitchen)
        check(mac_a in rb.peers, "choosing a board adds it as a peer")
        b.poll()
        check(b.find(kitchen).state == endpointkit.CONNECTED, "a chosen board shows as connected")
        check(pb.send(b"too early") == 1, "send goes to each chosen board")
        check(pa.recv() is None, "a board that isn't chosen is not heard")
        a.select("espnow.peer", [desk, porch])
        check(mac_b in ra.peers and mac_c in ra.peers, "every chosen board is added")
        check(pb.send(b"ping") == 1 and pa.recv() == (desk, b"ping") and pa.recv() is None, "a message from a chosen board arrives once")
        check(espnowpeers.send(b"pong") == 2, "the module sends through the registered provider")
        check(pb.recv() == (kitchen, b"pong") and pc.recv() is None, "a board that hasn't chosen back doesn't hear it")
        check(espnowpeers.send(b"just you", to=desk) == 1 and pb.recv() == (kitchen, b"just you"), "send to one chosen board")
        for bad in ((b"x" * (espnowpeers.MAX_DATA + 1), None), (b"x", "espnow:ffffffffffff")):
            try:
                pa.send(*bad)
                check(False, "send refuses %r" % (bad[1],))
            except ValueError:
                pass
        for i in range(espnowpeers.INBOX + 4):
            pb.send(b"%d" % i)
        a.poll()
        check(len(ra.queue) == 4, "a poll reads at most MAX_READS messages: %d left" % len(ra.queue))
        a.poll()
        check(pa.dropped == 4 and pa.recv() == (desk, b"4"), "a full inbox drops the oldest and counts them")
        while pa.recv():
            pass
        a.select("espnow.peer", porch)
        check(mac_b not in ra.peers and mac_c in ra.peers, "letting a board go removes the peer")
        a.poll()
        check(a.find(desk).state == endpointkit.AVAILABLE, "a board let go shows as available")
        pb.send(b"after")
        check(pa.recv() is None, "a board let go is not heard")
        a.select("espnow.peer", [desk, porch])
        step = espnowpeers.BEACON_MS
        quiet = 0
        while quiet <= espnowpeers.FORGET_MS:
            clock[0] += step
            quiet += step
            c.poll()
            a.poll()
            if quiet < espnowpeers.FORGET_MS:
                check(desk in ids(a.endpoints("espnow.peer")), "a board stays listed for forget_ms")
        check(ids(a.endpoints("espnow.peer")) == [porch], "a board that goes quiet drops out after forget_ms")
        check(mac_b not in ra.peers and desk in a.chosen("espnow.peer"), "its peer is removed and it stays chosen")
        sent = len(ra.sent)
        b.poll()
        a.poll()
        check(a.find(desk) is not None and mac_b in ra.peers, "a chosen board heard again is added again")
        check(len(ra.sent) == sent + 1, "a board that hears a new one answers at once, beacon due or not")
        a.poll()
        check(a.find(desk).state == endpointkit.CONNECTED, "and shows as connected on the next poll")
        a.unregister(pa)
        check(ra.peers == [], "unregistering removes every peer it added and the broadcast one")
        espnowpeers._provider[:] = []
        try:
            espnowpeers.register(Registry())
            check(False, "register without espnow raises")
        except ImportError:
            pass
    finally:
        espnowpeers._ticks_ms, espnowpeers._ticks_diff = saved
        espnowpeers._provider[:] = []


# -- Thread ----------------------------------------------------------------------


def _tlv(kind, value):
    return bytes((kind, len(value))) + bytes(value)


class FakeThreadAir:
    """802.15.4 radios in range of each other. Networks made anywhere are numbered
    in one sequence, so two airs never make the same one."""

    made = 0
    ups = 0

    def __init__(self):
        self.nodes = []


class FakeOpenThread:
    """The firmware's openthread module on one board: a node forms a network
    when nobody else is up on it, joins as a child when a node with the same
    network key is, and stays detached with the wrong key. A node is
    "detached" for one role() read after coming up, as a real one is while
    it attaches. A search reports on the second discovered() call."""

    def __init__(self, air):
        self.air = air
        self.tlvs = None
        self.on = False
        self.attaching = False
        self.searching = 0
        self.since = 0
        self.calls = []
        air.nodes.append(self)

    def _info(self):
        out = {}
        tlvs = self.tlvs or b""
        i = 0
        while i < len(tlvs):
            out[tlvs[i]] = bytes(tlvs[i + 2 : i + 2 + tlvs[i + 1]])
            i += 2 + tlvs[i + 1]
        return out

    def dataset_new(self, name=None, channel=None, panid=None):
        self.calls.append("dataset_new")
        FakeThreadAir.made += 1
        n = FakeThreadAir.made
        return b"".join((
            _tlv(14, b"\x00\x00\x00\x00\x00\x01\x00\x00"),  # active timestamp: passed by
            _tlv(0, bytes((0, 0, channel or 11 + n))),
            _tlv(1, bytes((0x12, n))),
            _tlv(2, bytes((0xDE, 0xAD, 0, 0, 0, 0, 0, n))),
            _tlv(3, (name or "net-%d" % n).encode()),
            _tlv(5, bytes((n,)) * 16),
            _tlv(7, b"\xfd\x00\x00\x00\x00\x00\x00\x01"),  # mesh-local prefix: passed by
        ))

    def dataset(self, tlvs=None):
        if tlvs is None:
            self.calls.append("dataset?")
            return self.tlvs
        self.calls.append("dataset!")
        info = self.tlvs, self.tlvs = self.tlvs, bytes(tlvs)
        got = self._info()
        if 5 not in got or 0 not in got or 1 not in got:
            self.tlvs = info[0]
            raise ValueError("a dataset needs at least a network key, a channel and a PAN ID")
        return None

    def up(self, on=None):
        if on is None:
            return self.on
        self.calls.append("up(%s)" % on)
        if on and self.tlvs is None:
            raise OSError("OpenThread: no dataset; set one with openthread.dataset()")
        self.on = bool(on)
        self.attaching = self.on
        FakeThreadAir.ups += 1
        self.since = FakeThreadAir.ups
        return None

    def _peers(self):
        mine = self._info()
        return [n for n in self.air.nodes if n is not self and n.on and n._info().get(2) == mine.get(2)]

    def role(self):
        self.calls.append("role")
        if not self.on:
            return "disabled"
        if self.attaching:
            self.attaching = False
            return "detached"
        key = self._info().get(5)
        mates = [p for p in self._peers() if p._info().get(5) == key]
        if self._peers() and not mates:
            return "detached"  # the network is there, but this key doesn't open it
        return "child" if any(p.since < self.since for p in mates) else "leader"

    def neighbors(self):
        key = self._info().get(5)
        return [("%016x" % i, 0x400 + i, -55, True) for i, p in enumerate(self._peers()) if p._info().get(5) == key]

    def discover(self):
        self.calls.append("discover")
        if self.searching:
            raise OSError("OpenThread: Busy")
        self.searching = 2

    def discovered(self):
        self.searching -= 1
        if self.searching:
            return None
        out, seen = [], []
        for n in self.air.nodes:
            info = n._info()
            if n is self or not n.on or info.get(2) in seen:
                continue
            seen.append(info[2])
            out.append((info[3].decode(), binascii.hexlify(info[2]).decode(), info[1][0] << 8 | info[1][1], info[0][2], -60 - len(out)))
        return out


def t_thread():
    import threadnet
    from endpointkit.fake import FakeProvider

    clock = [5000]
    saved = (threadnet._ticks_ms, threadnet._ticks_diff)
    threadnet._ticks_ms = lambda: clock[0]
    threadnet._ticks_diff = lambda a, b: a - b
    threadnet._provider[:] = []
    threadnet._registry[:] = []
    try:
        # The dataset helpers.
        ds = FakeOpenThread(FakeThreadAir()).dataset_new("garden", channel=20)
        info = threadnet.parse(ds)
        n = FakeThreadAir.made
        check(info == {"name": "garden", "extpanid": "dead0000000000%02x" % n, "panid": 0x1200 + n, "channel": 20, "key": "%02x" % n * 16}, "parse reads name, IDs, channel and key: %r" % (info,))
        check(threadnet.parse(binascii.hexlify(ds).decode()) == info, "parse takes hex too")
        built = threadnet.build("garden", "dead0000000000%02x" % n, 0x1200 + n, 20, "%02x" % n * 16)
        check(threadnet.parse(built) == info, "build makes what parse reads back")
        for bad in (ds[:-3], "zz", b"\x00"):
            try:
                threadnet.parse(bad)
                check(False, "parse refuses %r" % (bad,))
            except ValueError:
                pass
        for args in (("x", "dead", 1, 20, "01" * 16), ("x", "dead000000000001", 1, 27, "01" * 16), ("x", "dead000000000001", 1, 20, "01"), ("", "dead000000000001", 1, 20, "01" * 16)):
            try:
                threadnet.build(*args)
                check(False, "build refuses %r" % (args,))
            except ValueError:
                pass

        air = FakeThreadAir()
        oa, ob, oc, od = FakeOpenThread(air), FakeOpenThread(air), FakeOpenThread(air), FakeOpenThread(air)
        a, b, c, d = Registry(), Registry(), Registry(), Registry()
        pa = threadnet.register(a, oa)
        check(endpointkit.KINDS["thread.net"] == endpointkit.ONE and endpointkit.title("thread.net") == "Thread" and endpointkit.icon("thread.net") == "lan", "registering makes the kind known")
        check(threadnet.register(a) is pa and len(a.providers("thread.net")) == 1, "registering again returns the same provider")
        check(a.endpoints("thread.net") == [] and not oa.on, "a board with no dataset lists nothing and stays down")

        # The first board forms a network and leads it.
        check(oa.calls.count("discover") == 1, "registering starts a search")
        a.poll()
        a.poll()
        shared = threadnet.form("bench", channel=15)
        ext = threadnet.extpanid(shared)
        net = "thread:" + ext
        check(oa.on and threadnet.parse(oa.dataset())["name"] == "bench", "form sets the new dataset and comes up")
        check(a.chosen("thread.net") == [net], "form chooses the new network: %r" % a.chosen("thread.net"))
        check(oa.calls.count("discover") == 1, "no search while the new network attaches")
        check(a.find(net).label == "bench", "the network is listed by its name")
        clock[0] += threadnet.RESCAN_MS
        a.poll()
        ep = a.find(net)
        check(ep.state == endpointkit.CONNECTED and ep.caps["role"] == "leader" and ep.caps["channel"] == 15, "the board leads its network: %r %r" % (ep.state, ep.caps))
        reads = len(oa.calls)
        a.poll()
        check(len(oa.calls) == reads, "poll reads nothing before rescan_ms")

        # The radio is Thread's own: Wi-Fi isn't stopped, another 802.15.4 user is.
        wifi = FakeProvider("net", "wifi", [("Home", "Home")], ("radio.wifi",))
        a.register(wifi)
        a.select("net", "wifi:Home")
        check(a.conflicts("thread.net", [net]) == ([], []), "choosing Thread stops nothing on Wi-Fi")
        endpointkit.add_kind("zigbee.net", endpointkit.ONE, "Zigbee", "lan")
        zig = FakeProvider("zigbee.net", "zigbee", [("hub", "Zigbee hub")], ("radio.15_4",))
        a.register(zig)
        a.select("zigbee.net", "zigbee:hub", confirm=True)
        check(a.chosen("thread.net") == [] and not oa.on, "another 802.15.4 choice stops Thread when confirmed")
        a.select("thread.net", net, confirm=True)
        check(oa.on and a.chosen("zigbee.net") == [], "and choosing Thread again stops it")
        a.unregister(zig)
        clock[0] += threadnet.RESCAN_MS
        a.poll()
        a.poll()

        # A second board finds the network and joins it with the network key.
        pb = b.register(threadnet.ThreadNet(ob))
        b.refresh("thread.net")
        check(ob.calls.count("discover") == 1 and b.endpoints("thread.net") == [], "a scan starts a search and lists nothing yet")
        b.refresh("thread.net")
        check(ob.calls.count("discover") == 1, "a scan during a search doesn't start another")
        b.poll()
        check(b.endpoints("thread.net") == [], "nothing is listed while the search runs")
        b.poll()
        ep = b.find(net)
        check(ep is not None and ep.state == endpointkit.NEEDS_PAIRING and ep.asks == endpointkit.PASSWORD and ep.label == "bench", "the search finds the network, which needs its key: %r" % (ep,))
        check(ep.caps["channel"] == 15 and ep.caps["rssi"] == -60, "a found network carries its channel and signal: %r" % (ep.caps,))
        b.select("thread.net", net)
        check(b.find(net).error and "join it first" in b.find(net).error and not ob.on, "choosing it before pairing is refused: %r" % b.find(net).error)
        for bad in ("nonsense", "00" * 15, FakeOpenThread(FakeThreadAir()).dataset_new("other").hex()):
            try:
                b.pair(net, bad)
                check(False, "pair refuses %r" % bad)
            except ValueError:
                pass
        check(b.find(net).state == endpointkit.NEEDS_PAIRING, "a refused secret leaves it unpaired")
        key = threadnet.parse(shared)["key"]
        b.pair(net, key)
        check(b.find(net).state == endpointkit.AVAILABLE and not ob.on, "the network key pairs it without joining")
        b.select("thread.net", net)
        got = threadnet.parse(ob.dataset())
        check(ob.on and got["key"] == key and got["channel"] == 15 and got["extpanid"] == ext, "choosing it joins with a dataset made from the search and the key: %r" % (got,))
        clock[0] += threadnet.RESCAN_MS
        b.poll()
        clock[0] += threadnet.RESCAN_MS
        b.poll()
        ep = b.find(net)
        check(ep.state == endpointkit.CONNECTED and ep.caps["role"] == "child" and ep.caps["neighbors"] == 1, "the second board is a child on the network: %r %r" % (ep.state, ep.caps))
        clock[0] += threadnet.RESCAN_MS
        a.poll()
        check(a.find(net).caps["neighbors"] == 1, "the leader hears the child: %r" % (a.find(net).caps,))

        # A third board joins with the whole dataset, a fourth with the wrong key.
        c.register(threadnet.ThreadNet(oc))
        c.refresh("thread.net")
        c.poll()
        c.poll()
        c.pair(net, shared)
        c.select("thread.net", net)
        clock[0] += threadnet.RESCAN_MS
        c.poll()
        clock[0] += threadnet.RESCAN_MS
        c.poll()
        check(c.find(net).state == endpointkit.CONNECTED and oc.dataset() == bytes(binascii.unhexlify(shared)), "the whole dataset joins as given")
        d.register(threadnet.ThreadNet(od))
        d.refresh("thread.net")
        d.poll()
        d.poll()
        d.pair(net, "ff" * 16)
        d.select("thread.net", net)
        clock[0] += threadnet.RESCAN_MS * 3
        d.poll()
        check(od.on and d.find(net).state == endpointkit.AVAILABLE and d.find(net).caps["role"] == "detached", "the wrong key stays detached, not connected: %r" % (d.find(net).caps,))

        # Letting go takes the interface down; unregistering does too.
        b.select("thread.net", [])
        check(not ob.on, "letting the network go takes the interface down")
        clock[0] += threadnet.RESCAN_MS
        b.poll()
        check(b.find(net).state == endpointkit.AVAILABLE and b.find(net).caps["role"] == "disabled", "a network let go shows as available")
        c.unregister(c.providers("thread.net")[0])
        check(not oc.on, "unregistering takes the interface down")

        # A board already on a network adopts it when it registers.
        threadnet._provider[:] = []
        threadnet._registry[:] = []
        oc.up(True)
        oc.role()
        e = Registry()
        threadnet.register(e, oc)
        check(e.chosen("thread.net") == [net], "registering adopts the network the board is on: %r" % e.chosen("thread.net"))

        threadnet._provider[:] = []
        threadnet._registry[:] = []
        try:
            threadnet.register(Registry())
            check(False, "register without openthread raises")
        except ImportError:
            pass
        try:
            threadnet.form("x")
            check(False, "form before register raises")
        except RuntimeError:
            pass
        del pb
    finally:
        threadnet._ticks_ms, threadnet._ticks_diff = saved
        threadnet._provider[:] = []
        threadnet._registry[:] = []


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
