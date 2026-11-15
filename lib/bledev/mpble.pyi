# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""MicroPython backend over aioble and `bluetooth`: a board's radio, either role."""
from . import BLE, Connection, Scanner, Service, _Bytes, _UUIDLike
from .security import _Store
from collections.abc import Callable, Iterable
from typing import Any

def get(ble: Any = None) -> MPBLE:
    """The shared `MPBLE` for this board's radio, made on first use."""

class MPBLE(BLE):
    """The board's radio. `ble` may be a `bluetooth.BLE()`; there is only one."""

    backend: str
    raw: Any
    queue_limit: int
    def __init__(self, ble: Any = None, *, queue_limit: int = 128, mtu: int | None = None) -> None: ...
    def capabilities(self) -> dict[str, Any]: ...
    def enable_bonding(self, store: _Store | str | None = None) -> None:
        """Bond from now on, keeping the keys in `store` (see `bledev.security.use_store`)."""
    def config(self, *names: str, **settings: Any) -> Any: ...
    def close(self) -> None: ...
    def __getattr__(self, name: str) -> Any: ...
    def irq(self, handler: Callable[[int, Any], Any] | None) -> None:
        """Like `bluetooth.BLE.irq`, but beside aioble's handler rather than instead of it."""
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
