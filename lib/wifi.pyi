# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""`wifi` for MicroPython: CircuitPython's `wifi.radio` API on `network.WLAN`."""

class ConnectionError(OSError):
    """Joining a network failed; a subclass of `OSError`, so `except OSError` runs on both."""

class PowerManagement:
    """Power-saving options, as in CircuitPython's `wifi.PowerManagement`."""

    MIN: str
    MAX: str
    NONE: str
    UNKNOWN: str

class Network:
    """One network seen by a scan, or the one joined (`radio.ap_info`)."""

    ssid: str
    rssi: int
    channel: int
    bssid: bytes | None
    authmode: int | None
    def __init__(self, ssid: str, rssi: int, channel: int, bssid: bytes | None = None, authmode: int | None = None) -> None: ...

class Radio:
    def __init__(self) -> None: ...
    @property
    def enabled(self) -> bool: ...
    @enabled.setter
    def enabled(self, value: bool) -> None: ...
    @property
    def hostname(self) -> str: ...
    @hostname.setter
    def hostname(self, value: str) -> None: ...
    @property
    def mac_address(self) -> bytes: ...
    @property
    def power_management(self) -> str: ...
    @power_management.setter
    def power_management(self, value: str) -> None: ...
    @property
    def tx_power(self) -> float: ...
    @tx_power.setter
    def tx_power(self, value: float) -> None: ...
    @property
    def connected(self) -> bool: ...
    @property
    def ipv4_address(self) -> str | None:
        """The station's address, or `None` until it is associated and has one."""
    @property
    def ipv4_subnet(self) -> str | None: ...
    @property
    def ipv4_gateway(self) -> str | None: ...
    @property
    def ipv4_dns(self) -> str | None: ...
    @property
    def ap_info(self) -> Network | None:
        """The network joined, with its live `rssi`; `None` when not connected."""
    def set_ipv4_address(self, *, ipv4: str, netmask: str, gateway: str, ipv4_dns: str | None = None) -> None:
        """Use a static address instead of DHCP. Call before `connect`."""
    def start_dhcp(self) -> None:
        """Take the station's address from DHCP again, after `set_ipv4_address`."""
    @property
    def ipv4_static(self) -> tuple[str, str, str, str] | None:
        """`(address, netmask, gateway, dns)` while on a fixed address, else `None`."""
    def start_scanning_networks(self, *, start_channel: int = 1, stop_channel: int = 11) -> list[Network]:
        """Every network in range, strongest first. The channel range is ignored."""
    def stop_scanning_networks(self) -> None: ...
    def start_station(self) -> None: ...
    def stop_station(self) -> None: ...
    def connect(self, ssid: str, password: str | bytes = b'', *, channel: int = 0, bssid: bytes | None = None, timeout: float | None = None) -> None:
        """Join `ssid` and wait for an address; raises `ConnectionError` on failure. `timeout=0` returns at once."""
    def start_ap(self, ssid: str, password: str | bytes = b'', *, channel: int = 1, authmode: int | None = None, max_connections: int = 4) -> None:
        """Run an access point. A password selects WPA2; none leaves it open."""
    def stop_ap(self) -> None: ...
    @property
    def ap_active(self) -> bool: ...
    @property
    def ipv4_address_ap(self) -> str | None: ...
    @property
    def mac_address_ap(self) -> bytes: ...

radio: Radio

def sync_time() -> bool:
    """Set the clock from NTP. Returns `True` when it worked."""

def connect_from_secrets(module: str = 'secrets', *, wait: bool = True, ntp: bool = True, timeout: float | None = None) -> bool:
    """Deprecated: call `wifi_manager.connect()`, which this now does."""
