# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""A board's Ethernet port as an endpointkit ``net`` endpoint, so a picker can move traffic onto it.

Register the provider, and the port appears under ``net`` as ``eth:0``.
Choosing it makes Ethernet the interface that carries the board's traffic,
and Wi-Fi stays up beside it; choosing a Wi-Fi network moves traffic back::

    import endpointkit
    import ethnet

    ethnet.register()                      # the board config's ethernet()
    endpointkit.select("net", "eth:0")     # traffic leaves by Ethernet
    endpointkit.select("net", "wifi:Home") # and back by Wi-Fi (wifinet)

The port is the one ``board_peripherals.ethernet()`` makes, unless you pass
your own ``network.LAN``. Choosing it turns the port on if it was off, and
nothing turns it off again: nothing takes down a link it didn't bring up,
and a link it did bring up may be carrying something else by then.

Moving traffic needs firmware whose interfaces take
``ipconfig(default=True)`` (OmniPython's ESP32 builds); on other firmware
choosing Ethernet is refused with a message saying so. The DNS servers don't
move with it: a server out on the internet is reached through whichever link
carries traffic, and `network.ipconfig` sets another.

`endpointkit.poll` looks at the port every ``rescan_ms``, which costs
nothing, and reports a cable pulled or an address gained.
"""

import endpointkit

try:
    from time import ticks_diff as _ticks_diff
    from time import ticks_ms as _ticks_ms
except ImportError:  # CPython, for the desktop checks
    import time

    def _ticks_ms():
        return int(time.monotonic() * 1000)

    def _ticks_diff(a, b):
        return a - b


#: How often, in milliseconds, `endpointkit.poll` looks at the port.
RESCAN_MS = 3000


def _board_ethernet():
    try:
        import board_peripherals
    except ImportError:
        raise OSError("No board_peripherals here: pass the network.LAN to use")
    make = getattr(board_peripherals, "ethernet", None)
    if make is None:
        raise OSError("This board config has no ethernet()")
    return make()


class EthNet(endpointkit.Provider):
    """The board's Ethernet port.

    Args:
        nic: the port, a ``network.LAN``. Default: ``board_peripherals.ethernet()``,
            made when the provider is.
        rescan_ms (int): how often `poll` looks at the port. Default: `RESCAN_MS`.
    """

    kind = "net"
    name = "eth"
    resources = ("eth.0",)

    def __init__(self, nic=None, rescan_ms=None):
        endpointkit.Provider.__init__(self)
        self.nic = nic if nic is not None else _board_ethernet()
        self.rescan_ms = RESCAN_MS if rescan_ms is None else rescan_ms
        self.brought_up = False  # True once choosing it turned the port on
        self._last = _ticks_ms()
        self._seen = None

    def scan(self):
        return self._list()

    def poll(self):
        if _ticks_diff(_ticks_ms(), self._last) < self.rescan_ms:
            return None
        before = self._seen
        found = self._list()
        return found if self._seen != before else None

    def apply(self, endpoint, chosen):
        # Letting go does nothing here: whatever is chosen next makes itself
        # the default, and the port stays up for anything else using it.
        if not chosen:
            return
        if not self.nic.active():
            self.nic.active(True)
            self.brought_up = True
        try:
            self.nic.ipconfig(default=True)
        except (AttributeError, TypeError, ValueError):
            raise OSError("This firmware can't move traffic to Ethernet")
        self._last = _ticks_ms() - self.rescan_ms  # the next poll shows it

    def is_default(self):
        """True when Ethernet carries the board's traffic; None when the firmware can't say."""
        try:
            return bool(self.nic.ipconfig("default"))
        except (AttributeError, TypeError, ValueError):
            return None

    def address(self):
        """The port's IPv4 address, or None without a link and a lease."""
        try:
            if not self.nic.isconnected():
                return None
            ip = self.nic.ipconfig("addr4")[0]
        except (OSError, ValueError):
            return None
        return ip if ip and ip != "0.0.0.0" else None

    def _list(self):
        self._last = _ticks_ms()
        address = self.address()
        default = self.is_default()
        self._seen = (address, default)
        caps = {"role": "uplink", "address": address, "default": default}
        label = "Ethernet (%s)" % address if address else "Ethernet"
        state = endpointkit.CONNECTED if address else endpointkit.AVAILABLE
        return [self.endpoint("0", label, state, caps)]


_provider = []


def register(registry=None, nic=None):
    """Register the board's Ethernet, and choose it when it already carries traffic and ``net`` has no choice yet.

    Registering again returns the provider already registered.

    Args:
        registry (endpointkit.Registry): where to register; endpointkit's own when None.
        nic: as in `EthNet`.
    """
    if not _provider:
        registry = registry or endpointkit.registry
        provider = registry.register(EthNet(nic))
        _provider.append(provider)
        if provider.is_default() and provider.address() and not registry.chosen("net"):
            registry.select("net", "eth:0")
    return _provider[0]
