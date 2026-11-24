# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""CPython backend over bleak: Windows, Linux and macOS. Central only."""
from . import BLE, Connection, Device, Scanner
from typing import Any

class BleakBLE(BLE):
    """The host's Bluetooth adapter, through bleak. Central only."""

    backend: str
    pairs_on_connect: bool
    queue_limit: int
    def __init__(
        self,
        *,
        queue_limit: int = 1024,
        mtu: int = ...,
        scanner_args: dict[str, Any] | None = None,
        client_args: dict[str, Any] | None = None,
    ) -> None: ...
    def capabilities(self) -> dict[str, Any]: ...
    def config(self, *names: str, **settings: Any) -> int | None: ...
    def close(self) -> None:
        """Drop every connection. The OS disconnects in the background; `aclose()` waits for it."""
    async def aclose(self) -> None:
        """`close()`, waiting until the OS has let go of every connection."""
    def scan(self, duration_ms: int, *, active: bool = False, interval_us: int | None = None, window_us: int | None = None) -> Scanner: ...

class _BleakConnection(Connection):
    reused_bond: bool
    def __init__(self, ble: BLE, device: Device, client: Any) -> None: ...
    async def disconnect(self, timeout_ms: int = 5000) -> None:
        """Drop the link and wait for it to be gone. BlueZ waits two seconds before it drops one."""
    def request_throughput(self) -> bool:
        """Ask the OS for a short connection interval. Windows 11 only; returns whether it asked."""

async def unpair(address: str) -> None:
    """Remove the OS's pairing with `address` without connecting."""
