# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""A board's Wi-Fi networks as endpointkit ``net`` endpoints, joined from a picker.

Register the provider, and the networks in range appear under ``net`` in
every picker. The one the board is on is connected; one it knows (from
``secrets.py``, CircuitPython's ``settings.toml``, or an earlier join) is
joined when chosen; a new secured one needs its password first::

    import endpointkit
    import wifinet

    wifinet.register()
    endpointkit.pair("wifi:Cafe", "espresso")   # joins and remembers it
    endpointkit.select("net", "wifi:Cafe")

The networks it joins are remembered the way `wifi_manager` remembers them,
so `wifi_manager.connect()` joins them again at the next boot.

A scan holds the interpreter for a second or two, so the provider doesn't
scan on its own: `scan` (a picker's Scan button, through
`endpointkit.refresh`) asks for one, and the next `endpointkit.poll` does
it. Between scans, `poll` looks every ``rescan_ms`` at which network the
board is on, which costs nothing. Joining waits for the network, up to
`wifi_manager.JOIN_TIMEOUT_S` seconds.

Choosing another uplink leaves Wi-Fi up: nothing takes down a link it
didn't bring up. Choosing a Wi-Fi network again (`ethnet` moves traffic to
Ethernet) makes the station carry the board's traffic once more.
"""

import endpointkit
import wifi_manager

#: How often, in milliseconds, `endpointkit.poll` checks which network the board is on.
RESCAN_MS = 3000

_ticks_ms = wifi_manager._ticks_ms
_ticks_diff = wifi_manager._ticks_diff


class WifiNet(endpointkit.Provider):
    """The board's Wi-Fi station.

    Args:
        radio: the station, as `wifi_manager` drives it. Default: the
            board's own, made when the provider is.
        rescan_ms (int): how often `poll` checks the network the board is on.
            Default: `RESCAN_MS`.
        timeout (int): seconds a join waits for the network.
        module (str): the module holding ``WIFI_SSID`` and ``WIFI_PASSWORD``,
            as in `wifi_manager.connect`.
    """

    kind = "net"
    name = "wifi"
    resources = ("radio.wifi",)

    def __init__(self, radio=None, rescan_ms=None, timeout=wifi_manager.JOIN_TIMEOUT_S, module="secrets"):
        endpointkit.Provider.__init__(self)
        self.radio = radio if radio is not None else wifi_manager._radio()
        self.rescan_ms = RESCAN_MS if rescan_ms is None else rescan_ms
        self.timeout = timeout
        self.module = module
        self._seen = {}  # ssid -> (rssi, secured), from the last scan
        self._wanted = True
        self._last = _ticks_ms()
        self._on = None  # (ssid, address) at the last look

    def scan(self):
        self._wanted = True
        return self._list()

    def poll(self):
        if self._wanted:
            self._wanted = False
            self._seen = self.radio.survey()
            return self._list()
        if _ticks_diff(_ticks_ms(), self._last) < self.rescan_ms:
            return None
        before = self._on
        found = self._list()
        return found if self._on != before else None

    def apply(self, endpoint, chosen):
        if not chosen:
            return
        ssid = endpoint.local_id
        if self.radio.ssid() != ssid:
            password = self._password(ssid)
            if password is None:
                raise OSError("%s needs its password: join it first" % ssid)
            self._join(ssid, password, OSError)
        # Another uplink (Ethernet) may carry traffic now; Wi-Fi takes it back.
        make_default = getattr(self.radio, "make_default", None)
        if make_default is not None:
            make_default()

    def pair(self, endpoint, secret=None):
        self._join(endpoint.local_id, secret or "", ValueError)

    def _join(self, ssid, password, error):
        reason = self.radio.join(ssid, password, self.timeout)
        if reason == "wrong password":
            raise error("Wrong password for %s" % ssid)
        if reason is not None:
            raise error("Couldn't join %s: %s" % (ssid, reason))
        wifi_manager._remember(ssid, password)
        self._last = _ticks_ms() - self.rescan_ms  # the next poll shows it joined

    def _password(self, ssid):
        """The password a known network was joined with; "" for an open one, None when unknown."""
        for n in wifi_manager._known(self.module):
            if n["ssid"] == ssid:
                return n.get("password") or ""
        seen = self._seen.get(ssid)
        if seen is not None and not seen[1]:
            return ""
        return None

    def _list(self):
        self._last = _ticks_ms()
        current = self.radio.ssid()
        address = self.radio.ip() if current else None
        self._on = (current, address)
        names = sorted(self._seen, key=lambda s: -self._seen[s][0])
        if current and current not in self._seen:
            names.insert(0, current)
        found = []
        for ssid in names:
            rssi, secured = self._seen.get(ssid, (None, True))
            caps = {"role": "uplink", "rssi": rssi, "secured": secured}
            if ssid == current:
                caps["address"] = address
                found.append(self.endpoint(ssid, ssid, endpointkit.CONNECTED, caps))
            elif self._password(ssid) is not None:
                found.append(self.endpoint(ssid, ssid, endpointkit.AVAILABLE, caps))
            else:
                found.append(self.endpoint(ssid, ssid, endpointkit.NEEDS_PAIRING, caps, asks=endpointkit.PASSWORD))
        return found


_provider = []


def register(registry=None, radio=None):
    """Register the board's Wi-Fi, and choose the network it's on when ``net`` has no choice yet.

    Registering again returns the provider already registered.

    Args:
        registry (endpointkit.Registry): where to register; endpointkit's own when None.
        radio: as in `WifiNet`.
    """
    if not _provider:
        registry = registry or endpointkit.registry
        provider = registry.register(WifiNet(radio))
        _provider.append(provider)
        current = provider.radio.ssid()
        if current and not registry.chosen("net"):
            registry.select("net", "wifi:" + current)
    return _provider[0]
