# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""CPython backend for Linux: a GATT server through BlueZ, and bleak's central."""
from collections.abc import Iterable

from . import Connection, Service, _Bytes, _UUIDLike
from .bleak import BleakBLE
from typing import Any

BLUEZ: str

class BlueZBLE(BleakBLE):
    """The Linux host's Bluetooth adapter: BlueZ's GATT server, and bleak's central."""

    backend: str
    adapter_path: str
    def __init__(
        self,
        *,
        adapter: str = "hci0",
        queue_limit: int = 1024,
        mtu: int = ...,
        scanner_args: dict[str, Any] | None = None,
        client_args: dict[str, Any] | None = None,
    ) -> None: ...
    def capabilities(self) -> dict[str, Any]: ...
    def config(self, *names: str, **settings: Any) -> Any: ...
    def close(self) -> None:
        """Unregister the GATT application and advertisement, and drop bleak's connections."""
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
