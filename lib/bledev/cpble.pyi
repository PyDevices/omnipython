# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""CircuitPython backend over `_bleio`: a board's radio, either role."""
from . import BLE, Connection, Scanner, Service, _Bytes, _UUIDLike
from collections.abc import Iterable
from typing import Any

POLL_MS: int
RETRY_MS: int
SCAN_SLICE_MS: int

def get(adapter: Any = None) -> CPBLE:
    """The shared `CPBLE` for this board's radio, made on first use."""

class CPBLE(BLE):
    """The board's radio, `_bleio.adapter` unless you pass another."""

    backend: str
    min_setup_ms: int
    raw: Any
    queue_limit: int
    stream_buffer: int
    def __init__(self, adapter: Any = None, *, queue_limit: int = 64, stream_buffer: int = 32768) -> None: ...
    def capabilities(self) -> dict[str, Any]: ...
    def config(self, *names: str, **settings: Any) -> int | str | None: ...
    def close(self) -> None: ...
    def enable_bonding(self, store: Any = None) -> None:
        """CircuitPython always bonds and keeps the keys itself, so this only accepts the call."""
    def forget_bonds(self) -> None:
        """Erase every bond this board holds (`_bleio.adapter.erase_bonding()`)."""
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
