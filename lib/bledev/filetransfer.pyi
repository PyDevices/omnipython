# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
from . import BLEError as BLEError, BLETimeoutError as BLETimeoutError, DisconnectedError as DisconnectedError, GattError as GattError, NEEDS_PAIRING as NEEDS_PAIRING, UUID as UUID, UnsupportedError as UnsupportedError, connect_and_set_up as connect_and_set_up, wait_ms as wait_ms
from _typeshed import Incomplete

SERVICE: Incomplete
VERSION: Incomplete
TRANSFER: Incomplete
AUTH: Incomplete
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
    status: Incomplete
    def __init__(self, status, message) -> None: ...

class AuthError(BLEError): ...

class _Out:
    head: Incomplete
    f: Incomplete
    pos: Incomplete
    size: Incomplete
    close: Incomplete
    def __init__(self, head, f=None, pos: int = 0, size: int = 0, close: bool = False) -> None: ...

class FileServer:
    root: Incomplete
    window: Incomplete
    authed: bool
    changed: int
    def __init__(self, root: str = '', window=...) -> None: ...
    def reset(self) -> None: ...
    def feed(self, data) -> None: ...
    def has_output(self): ...
    def packet(self, size): ...
    def sent(self) -> None: ...

def start(password=None, name: str = 'mpy-files', *, console: bool = True, window=..., **options): ...
def stop() -> None: ...

class Client:
    connection: Incomplete
    version: Incomplete
    chunk: Incomplete
    timeout_ms: int
    bytes_in: int
    bytes_out: int
    def __init__(self, connection, transfer, version, *, chunk=...) -> None: ...
    async def read(self, path, offset: int = 0): ...
    async def write(self, path, data, offset: int = 0, modification_time=None): ...
    async def delete(self, path) -> None: ...
    async def mkdir(self, path, modification_time=None): ...
    async def listdir(self, path): ...
    async def move(self, old, new) -> None: ...
    async def close(self) -> None: ...

async def connect(ble, password=None, name=None, *, device=None, timeout_ms: int = 10000, mtu: int = 247, pair=None, passkey=None, **connect_options): ...
