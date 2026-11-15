# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""The MicroPython REPL over Bluetooth, behind a password."""
from . import BLE, BLEError, Device, PairingError, nus as nus, _Passkey
from .security import _Store
from collections.abc import Callable
from typing import Any, Literal, Protocol

PROMPT: bytes
PAIR_WITHIN_MS: int
BANNER: bytes
DENIED: bytes
BUSY: bytes
MAX_PASSWORD: int

class AuthError(BLEError):
    """The board refused the password."""

class Login:
    """The password exchange, without a radio, so it can be tested anywhere."""

    verdict: bool | None
    def __init__(self, password: str | bytes | bytearray | memoryview) -> None: ...
    def feed(self, data: bytes | bytearray | memoryview) -> tuple[bytes, bool | None, bytes]:
        """`(reply, verdict, rest)` for a chunk the client wrote."""

def take_slot(dupterm: Callable[..., Any], stream: object, want: int | None = None) -> int | None:
    """Put `stream` on a free `os.dupterm` slot and return its index, or `None` when none is free."""
def give_slot(dupterm: Callable[..., Any], stream: object, index: int) -> None:
    """Free slot `index` if `stream` still holds it."""

class _ReplServer(Protocol):
    password: bytes | str | None
    pairing: str | None
    console: bool
    files: bool
    name: str
    interval_us: int
    running: bool
    authed: bool
    mtu: int
    def start(self) -> None: ...
    def advertise(self) -> None: ...
    def stop(self) -> None: ...

def start(
    password: str | Literal[False] | None = None,
    name: str | None = None,
    *,
    interval_us: int = 100000,
    dupterm_index: int | None = None,
    files: bool = False,
    console: bool = True,
    window: int | None = None,
    pairing: Literal["justworks", "passkey", "numeric", "auto"] | None = None,
    show: Callable[[int], Any] | None = None,
    hide: Callable[[], Any] | None = None,
    confirm: Callable[[int], bool | None] | None = None,
    bond_store: _Store | str | None = None,
) -> _ReplServer:
    """Serve the REPL over BLE until `stop` or a reset. MicroPython only."""
def stop() -> None:
    """Stop serving: drop the client, give the REPL back, stop advertising."""
def is_running() -> bool: ...
def refused(pair: bool, passkey: object) -> PairingError:
    """The `bledev.PairingError` for a board that refused a link."""
async def connect(
    ble: BLE | object,
    password: str | bytes | bytearray | memoryview | None = None,
    name: str | None = None,
    *,
    device: Device | None = None,
    timeout_ms: int = 10000,
    pair: bool = False,
    passkey: _Passkey | None = None,
    **connect_options: Any,
) -> nus.Link:
    """Log in to a board's BLE REPL and return the `bledev.nus.Link`, at `>>>`."""
async def run(link: nus.Link, code: str | bytes | bytearray | memoryview, timeout_ms: int = 10000) -> str:
    """Type `code` at the prompt and return what it printed, up to the next `>>>`."""
