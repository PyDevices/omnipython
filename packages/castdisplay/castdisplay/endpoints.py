# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""Rokus on the network as endpointkit ``cast.target`` endpoints.

Register the provider and keep calling `endpointkit.poll`; each Roku that
answers appears with its own name::

    import endpointkit
    from castdisplay import endpoints

    endpoints.register()
    ...                                   # endpointkit.poll() from a timer
    tv = endpointkit.selected("cast.target")
    if tv:
        RokuScreen(tv[0].caps["host"]).cast(fb)

The provider asks with SSDP (``roku:ecp``) every ``rescan_ms`` and reads the
answers without blocking, from a socket bound to the address the computer
routes through, so the question doesn't leave by a virtual adapter (WSL's,
a VPN's) that no TV is on. It asks each new Roku for its name once, with a
short HTTP request, and keeps an endpoint until it misses ``MISSES`` rounds
in a row. An endpoint's id holds the Roku's serial number, from the SSDP
answer itself, so a saved choice finds the TV again when its address
changes. Pass ``ask`` to choose which Rokus are asked for their names; the
rest are listed as "Roku at <address>". ``caps`` hold ``host``,
``model`` and ``type`` (``"roku"``). Choosing a target starts nothing: the
program that casts reads the choice.
"""

import socket
import time

import endpointkit

#: How often, in milliseconds, the provider asks the network again.
RESCAN_MS = 10000
#: How many rounds a Roku may miss before its endpoint goes.
MISSES = 3

SSDP = ("239.255.255.250", 1900)
SEARCH = (
    b"M-SEARCH * HTTP/1.1\r\nHost: 239.255.255.250:1900\r\nMan: \"ssdp:discover\"\r\n"
    b"ST: roku:ecp\r\nMX: 2\r\n\r\n"
)

_ticks_ms = getattr(time, "ticks_ms", None)
_ticks_diff = getattr(time, "ticks_diff", None)
if _ticks_ms is None:

    def _ticks_ms():
        return int(time.monotonic() * 1000)

    def _ticks_diff(a, b):
        return a - b


def _tag(xml, tag):
    a = xml.find(b"<" + tag + b">")
    if a < 0:
        return None
    a += len(tag) + 2
    b = xml.find(b"</" + tag + b">", a)
    return xml[a:b].decode() if b > a else None


def device_info(host, timeout=1.5):
    """``{serial, name, model}`` from the Roku at *host*; raises OSError when it doesn't answer."""
    addr = socket.getaddrinfo(host, 8060)[0][-1]
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(timeout)
        s.connect(addr)
        s.send(b"GET /query/device-info HTTP/1.0\r\nHost: %s:8060\r\n\r\n" % host.encode())
        body = b""
        while True:
            chunk = s.recv(1024)
            if not chunk:
                break
            body += chunk
    finally:
        s.close()
    return {
        "serial": _tag(body, b"serial-number") or host,
        "name": _tag(body, b"user-device-name") or _tag(body, b"friendly-device-name") or host,
        "model": _tag(body, b"friendly-model-name") or _tag(body, b"model-name") or "",
    }


def _parse(answer):
    """``(host, serial)`` from an SSDP answer; either may be None."""
    host = serial = None
    for line in answer.split(b"\r\n"):
        low = line[:9].lower()
        if low == b"location:":
            url = line[9:].strip().decode()
            host = url.split("//", 1)[-1].split("/", 1)[0].split(":")[0]
        elif low[:4] == b"usn:":
            usn = line[4:].strip().decode()
            if usn.startswith("uuid:roku:ecp:"):
                serial = usn[14:]
    return host, serial


def _ip(addr):
    """The IPv4 address in *addr*: CPython's ``(host, port)``, or MicroPython's raw sockaddr bytes."""
    if isinstance(addr, tuple):
        return addr[0]
    if isinstance(addr, (bytes, bytearray)) and len(addr) >= 8 and addr[0] == socket.AF_INET:
        return "%d.%d.%d.%d" % (addr[4], addr[5], addr[6], addr[7])
    return None


def source_address():
    """The address this computer sends from by default, or None when it can't tell."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # A documentation address (RFC 5737): connecting sends nothing.
        s.connect(socket.getaddrinfo("192.0.2.1", 9)[0][-1])
        return _ip(s.getsockname())
    except (OSError, AttributeError):
        return None
    finally:
        s.close()


class Rokus(endpointkit.Provider):
    """Rokus that answer SSDP on the local network.

    Args:
        rescan_ms (int): how often to ask the network again.
        info (callable): ``info(host)`` returning ``{serial, name, model}``,
            to stand in for the network in a test.
        ask (callable): ``ask(host)`` says whether to ask that Roku for its
            name; every Roku is asked when None.
        sock (object): a UDP socket to use instead of making one, for a test.
    """

    kind = "cast.target"
    name = "roku"

    def __init__(self, rescan_ms=RESCAN_MS, info=None, sock=None, ask=None):
        endpointkit.Provider.__init__(self)
        self.rescan_ms = rescan_ms
        self._info = info or device_info
        self._sock = sock
        self._ask = ask
        self._known = {}  # host -> {serial, name, model, misses, heard}
        self._order = []  # hosts in the order they answered first; MicroPython's dicts keep none
        self._last = None

    def _socket(self):
        if self._sock is None:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            src = source_address()
            if src:
                try:
                    s.bind(socket.getaddrinfo(src, 0)[0][-1])
                except OSError:
                    pass
            s.setblocking(False)
            self._sock = s
        return self._sock

    def _search(self):
        self._last = _ticks_ms()
        for d in self._known.values():
            d["misses"] = 0 if d["heard"] else d["misses"] + 1
            d["heard"] = False
        try:
            s = self._socket()
            dest = socket.getaddrinfo(SSDP[0], SSDP[1])[0][-1]
            s.sendto(SEARCH, dest)
        except OSError as exc:
            print("castdisplay.endpoints: can't search the network: %s" % exc)

    def _list(self):
        return [
            self.endpoint(d["serial"], ("Roku %s" if d["name"].startswith("at ") else "Roku: %s") % d["name"], caps={"host": h, "model": d["model"], "type": "roku"})
            for h, d in [(h, self._known[h]) for h in self._order]
            if d["misses"] < MISSES
        ]

    def scan(self):
        self._search()
        return self._list()

    def poll(self):
        before = [ep.id for ep in self._list()]
        if self._last is None or _ticks_diff(_ticks_ms(), self._last) >= self.rescan_ms:
            self._search()
        s = self._socket()
        while True:
            try:
                answer = s.recv(1024)
            except OSError:
                break
            if not answer:
                break
            host, serial = _parse(answer)
            if host is None:
                continue
            d = self._known.get(host)
            if d is None:
                d = {"serial": serial or host, "name": "at %s" % host, "model": ""}
                if self._ask is None or self._ask(host):
                    try:
                        d.update(self._info(host))
                    except OSError:
                        pass
                if serial:
                    d["serial"] = serial
                self._known[host] = d
                self._order.append(host)
            d["heard"] = True
            d["misses"] = 0
        found = self._list()
        return found if [ep.id for ep in found] != before else None

    def stop(self):
        if self._sock is not None:
            self._sock.close()
            self._sock = None


_provider = []


def register(registry=None):
    """Register the Roku finder; registering again returns the one already registered."""
    if not _provider:
        _provider.append((registry or endpointkit.registry).register(Rokus()))
    return _provider[0]
