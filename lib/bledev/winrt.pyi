# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""CPython backend for Windows: a GATT server through WinRT, and bleak's central."""
from collections.abc import Iterable

from . import Connection, Service, _Bytes, _UUIDLike
from .bleak import BleakBLE
from typing import Any

def radio_name() -> str:
    """The name Windows advertises for this PC's Bluetooth radio."""

class WinRTBLE(BleakBLE):
    """The PC's Bluetooth radio: Windows' GATT server, and bleak's central."""

    backend: str
    notify_buffers: int
    def __init__(
        self,
        *,
        notify_buffers: int = 16,
        queue_limit: int = 1024,
        mtu: int = ...,
        scanner_args: dict[str, Any] | None = None,
        client_args: dict[str, Any] | None = None,
    ) -> None: ...
    def capabilities(self) -> dict[str, Any]: ...
    def config(self, *names: str, **settings: Any) -> Any: ...
    def close(self) -> None:
        """Stop the GATT server, forget its centrals, and drop bleak's connections."""
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
