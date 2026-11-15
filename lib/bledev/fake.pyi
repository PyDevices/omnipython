# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""In-process loopback backend: two adapters, one pretend radio, no hardware."""
from . import BLE, Connection, Scanner, Service, _Bytes, _UUIDLike
from collections.abc import Callable, Iterable
from typing import Any

SCAN_TICK_MS: int

class Air:
    """The medium the fake adapters share. Make one per test."""

    adverts: list[Any]
    def __init__(self) -> None: ...

def default_air() -> Air:
    """The `Air` used when an adapter isn't given one."""

class FakeBLE(BLE):
    """A pretend radio. `central` and `peripheral` pick the roles it may take."""

    backend: str
    address: str
    rssi: int
    notify_buffers: int
    queue_limit: int
    bonds: set[str]
    pairing: str
    show_passkey: Callable[[int], Any] | None
    def __init__(
        self,
        *,
        air: Air | None = None,
        central: bool = True,
        peripheral: bool = True,
        mtu: int = ...,
        address: str | None = None,
        rssi: int = -50,
        notify_buffers: int = 8,
        queue_limit: int = 128,
        gap_name: str = 'fake',
        long_reads: bool = True,
    ) -> None: ...
    def capabilities(self) -> dict[str, Any]: ...
    def forget(self, address: str | None = None) -> None:
        """Drop the bond with `address`, or every bond (a board's filesystem erased)."""
    def set_pairing(self, mode: str = 'justworks', show: Callable[[int], Any] | None = None) -> None:
        """As a peripheral, pair "just works" (`mode="justworks"`), or show a passkey (`mode="passkey"`)."""
    def config(self, *names: str, **settings: Any) -> int | str | None: ...
    def close(self) -> None: ...
    def register_services(self, *services: Service) -> None: ...
    async def advertise(
        self,
        interval_us: int = 100000,
        *,
        name: str | bytes | None = None,
        services: Iterable[_UUIDLike] | None = None,
        appearance: int = 0,
        manufacturer: tuple[int, _Bytes] | None = None,
        connectable: bool = True,
        timeout_ms: int | None = None,
        service_data: Iterable[tuple[_UUIDLike, _Bytes]] | None = None,
    ) -> Connection: ...
    def scan(self, duration_ms: int, *, active: bool = False, interval_us: int | None = None, window_us: int | None = None) -> Scanner: ...
