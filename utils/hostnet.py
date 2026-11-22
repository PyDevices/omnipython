# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""A computer's network as an endpointkit ``net`` endpoint, reported and never changed.

On a desktop the operating system owns networking: it brings links up and
picks the one that carries traffic. This provider only reports that link,
so a picker can show it, and refuses a choice it can't carry out::

    import endpointkit
    import hostnet

    hostnet.register()
    print(endpointkit.selected("net"))   # [<Endpoint host-net:default 'Network (192.168.1.20)' connected>]

The ``default`` endpoint is the link the operating system routes through,
labelled with the address it gives this computer, and is chosen when
nothing else is. On Linux the other interfaces are listed too, so a picker
shows what's there, but choosing one raises: change it in the operating
system's own settings.
"""

import socket
import sys
import time

import endpointkit

#: How often, in milliseconds, `endpointkit.poll` looks at the network again.
RESCAN_MS = 5000

# A documentation address (RFC 5737): connecting a UDP socket to it sends
# nothing, but makes the system pick the route and the source address.
_PROBE = ("192.0.2.1", 9)

_ticks_ms = getattr(time, "ticks_ms", None)
_ticks_diff = getattr(time, "ticks_diff", None)
if _ticks_ms is None:

    def _ticks_ms():
        return int(time.monotonic() * 1000)

    def _ticks_diff(a, b):
        return a - b


def _ip(addr):
    """The IPv4 address in *addr*: CPython's ``(host, port)``, or MicroPython's raw sockaddr bytes."""
    if isinstance(addr, tuple):
        return addr[0]
    if isinstance(addr, (bytes, bytearray)) and len(addr) >= 8 and addr[0] == socket.AF_INET:
        return "%d.%d.%d.%d" % (addr[4], addr[5], addr[6], addr[7])
    return None


def default_address():
    """The address the system would send from, or None when there's no route
    or this interpreter can't say."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(socket.getaddrinfo(_PROBE[0], _PROBE[1])[0][-1])
        name = getattr(s, "getsockname", None)
        if name is None:
            return None
        return _ip(name())
    except OSError:
        return None
    finally:
        s.close()


def interfaces():
    """The names of the network interfaces besides loopback, where the system lists them (Linux)."""
    if sys.platform != "linux" or not hasattr(socket, "if_nameindex"):
        return []
    try:
        return [name for _, name in socket.if_nameindex() if name != "lo"]
    except OSError:
        return []


class HostNet(endpointkit.Provider):
    """The operating system's network, report only.

    Args:
        address (callable): returns the default source address or None.
        names (callable): returns the other interfaces' names.
        rescan_ms (int): how often `poll` looks again.
    """

    kind = "net"
    name = "host-net"

    def __init__(self, address=None, names=None, rescan_ms=RESCAN_MS):
        endpointkit.Provider.__init__(self)
        self._address = address or default_address
        self._names = names or interfaces
        self.rescan_ms = rescan_ms
        self._last = _ticks_ms()
        self._seen = None

    def scan(self):
        self._last = _ticks_ms()
        addr = self._address()
        if addr:
            default = self.endpoint("default", "Network (%s)" % addr, endpointkit.CONNECTED, caps={"address": addr, "role": "uplink"})
        else:
            default = self.endpoint("default", "Network", endpointkit.UNAVAILABLE, caps={"address": None, "role": "uplink"})
        found = [default]
        for name in self._names():
            found.append(self.endpoint(name, name, caps={"role": "uplink"}))
        self._seen = [(ep.id, ep.label, ep.state) for ep in found]
        return found

    def poll(self):
        if _ticks_diff(_ticks_ms(), self._last) < self.rescan_ms:
            return None
        before = self._seen
        found = self.scan()
        return found if self._seen != before else None

    def apply(self, endpoint, chosen):
        if chosen and endpoint.local_id != "default":
            raise OSError("the operating system chooses the network here; change it in its own settings")


_provider = []


def register(registry=None):
    """Register the host's network and choose it when ``net`` has no choice yet.

    Registering again returns the provider already registered.
    """
    if not _provider:
        registry = registry or endpointkit.registry
        _provider.append(registry.register(HostNet()))
        if not registry.chosen("net"):
            registry.select("net", "host-net:default")
    return _provider[0]
