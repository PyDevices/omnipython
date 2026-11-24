# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""A fake ``network.WLAN`` on a fake clock, shared by the Wi-Fi tests.

It is esp32-shaped: a static address set with ``ifconfig()`` reads back at
once, before the station has associated, and stays after the link drops.
"""

clock = [0]


def ticks_ms():
    return clock[0]


def ticks_diff(a, b):
    return a - b


def sleep_ms(ms):
    clock[0] += ms
    FakeWLAN.current.tick()


class FakeWLAN:
    """An esp32-shaped station.

    ``ip`` is what ``ifconfig()`` reports and ``linked`` what
    ``isconnected()`` reports. ``connect()`` associates after
    ``assoc_ms``; with DHCP the address arrives then too, and ``lag_ms``
    later ``isconnected()`` catches up (ESP-IDF's "got ip" event trailing
    lwIP on a debug build).
    """

    STA_IF = 0
    current = None

    def __init__(self, ip="0.0.0.0", linked=False, has_isconnected=True):
        self.ip = ip
        self.linked = linked
        self.dhcp = True  # ifconfig((...)) turns it off, as on esp32
        self.connects = []
        self.assoc_ms = 1500
        self.lag_ms = 0
        self._assoc_at = None
        self._link_at = None
        if not has_isconnected:
            self.isconnected = self._no_isconnected
        FakeWLAN.current = self

    def active(self, on=None):
        return True

    def ifconfig(self, cfg=None):
        if cfg == "dhcp":
            self.dhcp = True
            return None
        if cfg is not None:
            self.ip = cfg[0]
            self.dhcp = False
            return None
        return (self.ip, "255.255.255.0", "10.0.0.1", "10.0.0.1")

    def ipconfig(self, key=None, **kwargs):
        if key == "dhcp4":
            return self.dhcp
        if "dhcp4" in kwargs:
            self.dhcp = bool(kwargs["dhcp4"])
            return None
        raise ValueError("unexpected key")

    def isconnected(self):
        return self.linked

    def _no_isconnected(self):
        raise OSError("not supported")

    def status(self, param=None):
        if param == "rssi":
            return -50
        return 1010 if self.linked else 1001

    pm = 1  # esp32's default, PM_PERFORMANCE: sleep between beacons
    pm_sets = 0

    def config(self, key=None, **kwargs):
        if "pm" in kwargs:
            self.pm = kwargs["pm"]
            self.pm_sets += 1
            return None
        return {"ssid": "bench", "channel": 6, "pm": self.pm, "mac": b"\x00\x11\x22\x33\x44\x55"}[key]

    def disconnect(self):
        """Leave the network: the link falls, a static address stays."""
        self._assoc_at = self._link_at = None
        self.drop()

    def connect(self, ssid, password):
        self.connects.append(ssid)
        self._assoc_at = clock[0] + self.assoc_ms
        self._link_at = self._assoc_at + self.lag_ms

    def tick(self):
        now = clock[0]
        if self._assoc_at is not None and now >= self._assoc_at:
            if self.dhcp:
                self.ip = "10.0.0.77"
            self._assoc_at = None
        if self._link_at is not None and now >= self._link_at:
            self.linked = True
            self._link_at = None

    def drop(self):
        """The AP goes away: the link falls, a static address stays."""
        self.linked = False
        if self.dhcp:
            self.ip = "0.0.0.0"
