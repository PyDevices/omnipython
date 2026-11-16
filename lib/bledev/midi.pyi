# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""MIDI over Bluetooth LE (BLE-MIDI 1.0), as a MIDI port."""
from . import BLE, Connection, Device, UUID
from types import TracebackType
from typing import Any, NamedTuple
from typing_extensions import Self

SERVICE: UUID
CHARACTERISTIC: UUID
MTU: int
QUEUE_LIMIT: int
IN: str
OUT: str
INOUT: str

class PortInfo(NamedTuple):
    id: str
    name: str
    direction: str

def now_ms() -> int:
    """This host's BLE-MIDI clock: milliseconds, 13 bits."""

class Port:
    """One BLE-MIDI link, as a MIDI port. Made by `serve` or `connect`."""

    info: PortInfo
    direction: str
    is_open: bool
    connection: Connection
    queue_limit: int
    dropped: int
    decode_errors: int
    messages_in: int
    messages_out: int
    def __init__(self, connection: Connection, name: str, *, queue_limit: int = ..., running_status: bool = True) -> None: ...
    @property
    def overflowed(self) -> bool: ...
    def readinto(self, buf: bytearray | memoryview, nbytes: int | None = None) -> int | None:
        """Waiting MIDI bytes into `buf` (at most `nbytes`); how many, or `None` when nothing has arrived."""
    def read(self, nbytes: int | None = None) -> bytes | None:
        """Up to `nbytes` waiting MIDI bytes (everything waiting when `None`), or `None`."""
    def any(self) -> int:
        """How many MIDI bytes are waiting to be read."""
    def take(self) -> tuple[int, bytes] | None:
        """The next `(timestamp, message)` if one has arrived, else `None`; never waits."""
    async def receive(self, timeout_ms: int | None = None) -> tuple[int, bytes]:
        """The next `(timestamp, message)`. Raises `DisconnectedError` once the link has closed and everything that arrived is read."""
    def __aiter__(self) -> Self: ...
    async def __anext__(self) -> tuple[int, bytes]: ...
    def write(self, buf: bytes | bytearray | memoryview, nbytes: int | None = None) -> int:
        """Send the first `nbytes` of `buf` (all of it when `None`); returns how many bytes it took."""
    def send(self, message: bytes | bytearray | memoryview, timestamp: int | None = None) -> None:
        """Queue one complete message, optionally with its own timestamp."""
    async def drain(self) -> None:
        """Wait until everything written has been handed to the radio."""
    def close(self) -> None:
        """Close the port and drop the link."""
    deinit = close
    def __enter__(self) -> Self: ...
    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None) -> None: ...
    async def aclose(self) -> None:
        """Close the port and wait for the disconnect."""

async def serve(
    ble: BLE | object,
    name: str | None = None,
    *,
    timeout_ms: int | None = None,
    interval_us: int = 100000,
    mtu: int = ...,
    **options: Any,
) -> Port:
    """Advertise BLE-MIDI as `name` and return a `Port` when a central connects."""
async def connect(
    ble: BLE | object,
    name: str | None = None,
    *,
    device: Device | None = None,
    timeout_ms: int = 10000,
    mtu: int = ...,
    queue_limit: int = ...,
    running_status: bool = True,
    **connect_options: Any,
) -> Port:
    """Find a BLE-MIDI device (by `name`, or the first one advertising the service), connect, subscribe, and return a `Port`."""
