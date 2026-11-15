# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Finding peers: by mDNS on a shared network, or over a hotspot."""

from typing import Any

SERVICE_TYPE: str
PROTOCOL: str

class MDNS:
    """Advertise this peer and find others on the local network."""

    def __init__(self, interface: Any = None) -> None: ...
    @property
    def hostname(self) -> str: ...
    def advertise(self, name: str, port: int) -> None:
        """Answer for `name` on UDP `port` until `deinit`."""
    def find(self, name: str | None = None, timeout: int | float = 2) -> list[tuple[str, tuple[str, int]]]:
        """`[(name, (ip, port)), ...]` of the peers that answer."""
    def deinit(self) -> None: ...

class Hotspot:
    """Two boards on a Wi-Fi network of their own: one hosts, one joins."""

    password: str
    ssid: str | None
    host: bool | None
    timeout: int | float
    name: str | None
    port: int | None
    def __init__(
        self, password: str, *, ssid: str | None = None, host: bool | None = None, timeout: int | float = 20
    ) -> None: ...
    def advertise(self, name: str, port: int) -> None:
        """Remember this side's name and port; the hotspot starts at `find()`."""
    def find(self, name: str | None = None, timeout: int | float | None = None) -> list[tuple[str, tuple[str, int | None]]]:
        """`[(name, (ip, port))]` of the host, or `[]` on the host itself."""
    def start(self, ssid: str) -> str:
        """Start an access point named `ssid`. Returns this board's address on it."""
    def join(self, ssid: str, timeout: int | float | None = None) -> str:
        """Join the access point `ssid`. Returns the host's address on it."""
    def deinit(self) -> None: ...

COMPANY: int

def pack_beacon(address: str, port: int) -> bytes:
    """The manufacturer data a medialink advertisement carries."""

def unpack_beacon(data: bytes | bytearray | memoryview) -> tuple[str, int] | None:
    """`(ip, port)` from a medialink advertisement's data, or `None`."""

class BLE:
    """Find a peer nearby by Bluetooth LE, then talk to it over IP."""

    def __init__(self, ble: Any = None) -> None: ...
    def advertise(self, name: str, port: int, address: str | None = None) -> None: ...
    def find(self, name: str | None = None, timeout: int | float = 2) -> list[tuple[str, tuple[str, int]]]:
        """`[(name, (ip, port)), ...]` of the peers heard."""
    def deinit(self) -> None: ...
