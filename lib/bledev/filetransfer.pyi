# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Files over Bluetooth: CircuitPython's BLE file-transfer protocol, both sides."""
from . import BLE, BLEError, ClientCharacteristic, Connection, Device, UUID, _Passkey
from .repl import _ReplServer
from typing import Any

SERVICE: UUID
VERSION: UUID
TRANSFER: UUID
AUTH: UUID
PROTOCOL_VERSION: int
READ: int
READ_DATA: int
READ_PACING: int
WRITE: int
WRITE_PACING: int
WRITE_DATA: int
DELETE: int
DELETE_STATUS: int
MKDIR: int
MKDIR_STATUS: int
LISTDIR: int
LISTDIR_ENTRY: int
MOVE: int
MOVE_STATUS: int
STATUS_OK: int
STATUS_ERROR: int
STATUS_ERROR_NO_FILE: int
STATUS_ERROR_PROTOCOL: int
STATUS_ERROR_READONLY: int
STATUS_LOCKED: int
FLAG_DIRECTORY: int
WINDOW: int
MAX_PATH: int

class FileTransferError(BLEError):
    """The board answered with an error status (`.status`)."""

    status: int
    def __init__(self, status: int, message: str) -> None: ...

class AuthError(BLEError):
    """The board refused the password, or wants one and none was given."""

class FileServer:
    """The protocol, without a radio, so it runs and is tested anywhere."""

    root: str
    window: int
    authed: bool
    changed: int
    def __init__(self, root: str = '', window: int = ...) -> None: ...
    def reset(self) -> None:
        """Forget the transfer in progress and everything queued (the connection closed)."""
    def feed(self, data: bytes | bytearray | memoryview) -> None:
        """Take what the client wrote to the transfer characteristic, in any split."""
    def has_output(self) -> bool: ...
    def packet(self, size: int) -> bytes | None:
        """The next notification's payload (`None` when nothing is waiting)."""
    def sent(self) -> None: ...

def start(
    password: str | bool | None = None,
    name: str = 'mpy-files',
    *,
    console: bool = True,
    window: int = ...,
    **options: Any,
) -> _ReplServer:
    """Serve files (and, unless `console=False`, the REPL) over BLE. MicroPython only."""
def stop() -> None: ...

class Client:
    """A connection to a board's file service. Made by `connect`."""

    connection: Connection | None
    version: int | None
    chunk: int
    timeout_ms: int
    bytes_in: int
    bytes_out: int
    def __init__(self, connection: Connection | None, transfer: ClientCharacteristic | None, version: int | None, *, chunk: int = ...) -> None: ...
    async def read(self, path: str, offset: int = 0) -> bytes:
        """The file's contents from `offset` on."""
    async def write(self, path: str, data: bytes | bytearray | memoryview, offset: int = 0, modification_time: int | None = None) -> int:
        """Write `data` at `offset` (the file ends after it). Returns the stored time in ns."""
    async def delete(self, path: str) -> None:
        """Delete a file, or a directory and everything in it."""
    async def mkdir(self, path: str, modification_time: int | None = None) -> int:
        """Make a directory and any missing parents. Returns the stored time in ns."""
    async def listdir(self, path: str) -> list[tuple[str, int, bool, int]]:
        """`[(name, size, is_directory, modification_time_ns), ...]`."""
    async def move(self, old: str, new: str) -> None:
        """Rename or move a file or directory (protocol version 4)."""
    async def close(self) -> None: ...

async def connect(
    ble: BLE | object,
    password: str | bytes | bytearray | memoryview | None = None,
    name: str | None = None,
    *,
    device: Device | None = None,
    timeout_ms: int = 10000,
    mtu: int = 247,
    pair: bool | None = None,
    passkey: _Passkey | None = None,
    **connect_options: Any,
) -> Client:
    """Find a board serving files (by `name`, or the first advertising the service), connect, log in, and return a `Client`."""
