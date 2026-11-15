# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Nordic UART Service: a two-way byte stream over BLE."""
from . import BLE, Device, Connection, UUID as UUID
from collections.abc import Iterable
from typing import Any
from typing_extensions import Self

SERVICE: UUID
RX: UUID
TX: UUID
MTU: int

class Link:
    """One end of a NUS byte stream. Made by `serve` or `connect`."""

    connection: Connection
    bytes_in: int
    bytes_out: int
    def __init__(self, connection: Connection) -> None: ...
    @property
    def closed(self) -> bool: ...
    async def read(self, n: int = -1) -> bytes:
        """Up to `n` bytes (all that's buffered when `n` < 0), waiting for at least one."""
    async def readexactly(self, n: int) -> bytes:
        """Exactly `n` bytes. Raises `DisconnectedError` if the link closes first."""
    async def readline(self) -> bytes:
        """Bytes up to and including `b"\\n"`; at end of stream, whatever is left."""
    def __aiter__(self) -> Self: ...
    async def __anext__(self) -> bytes: ...
    async def write(self, data: bytes | bytearray | memoryview | Iterable[int]) -> None:
        """Send all of `data`, split to the link's MTU."""
    async def drain(self) -> None: ...
    async def close(self) -> None:
        """Disconnect. Anything already received stays readable."""

async def serve(ble: BLE | object, name: str = 'bledev', *, timeout_ms: int | None = None, interval_us: int = 100000, mtu: int = ...) -> Link:
    """Advertise the Nordic UART service as `name` and return a `Link` when a central connects."""
async def connect(ble: BLE | object, name: str | None = None, *, device: Device | None = None, timeout_ms: int = 10000, mtu: int = ..., **connect_options: Any) -> Link:
    """Find a NUS peripheral (by `name`, or the first one advertising the service), connect, and return a `Link`."""
