# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Pairing and bonding on a MicroPython board: the bond store, passkeys, link state."""
from collections.abc import Callable
from typing import Any, Literal, Protocol, TypeVar

_F = TypeVar("_F", bound=Callable[..., Any])
_Secrets = dict[tuple[int, bytes], bytes]

class _Store(Protocol):
    kind: str
    def load(self) -> _Secrets: ...
    def save(self, secrets: _Secrets) -> None: ...
    def erase(self) -> None: ...

class _Display(Protocol):
    width: int
    height: int
    def fill_rect(self, x: int, y: int, w: int, h: int, color: int) -> Any: ...

IO_DISPLAY_ONLY: int
IO_DISPLAY_YESNO: int
IO_KEYBOARD_ONLY: int
IO_NO_INPUT_OUTPUT: int
IO_KEYBOARD_DISPLAY: int
MODES: tuple[str, ...]

class FileStore:
    """aioble's `ble_secrets.json`."""

    kind: str
    path: str
    def __init__(self, path: str = 'ble_secrets.json') -> None: ...
    def load(self) -> _Secrets: ...
    def save(self, secrets: _Secrets) -> None: ...
    def erase(self) -> None: ...

class NVSStore:
    """The keys in ESP32 NVS, outside the filesystem."""

    kind: str
    def __init__(self, namespace: str = 'bledev') -> None: ...
    def load(self) -> _Secrets: ...
    def save(self, secrets: _Secrets) -> None: ...
    def erase(self) -> None: ...

def pack_secrets(secrets: _Secrets) -> bytearray:
    """The NVS blob for `{(type, key): value}`."""
def unpack_secrets(buf: bytes | bytearray | memoryview) -> _Secrets:
    """`{(type, key): value}` from an NVS blob; a torn tail is dropped."""
def default_store() -> _Store:
    """NVS on an ESP32, the file anywhere else."""
def use_store(store: _Store | str | None = None) -> _Store:
    """Keep the keys in `store` (a store, `"nvs"`, `"file"` or a file path) and turn bonding on."""
def store() -> _Store | None:
    """The store in use, or `None` before `use_store`."""
def bonds() -> int:
    """How many peers this board holds keys for."""
def forget(address: bytes | bytearray | memoryview | str | None = None) -> None:
    """Forget every bond, or the ones with `address` (6 bytes, or `"aa:bb:cc:dd:ee:ff"`)."""
def state(conn_handle: int) -> tuple[bool, bool, bool, int]:
    """`(encrypted, authenticated, bonded, key_size)` for a connection."""
def passkey_asked(conn_handle: int) -> int | None:
    """`time.ticks_ms()` when the stack last asked about a passkey on this connection, or `None`."""
def on_change(callback: _F) -> _F:
    """Call `callback(conn_handle, encrypted, authenticated, bonded, key_size)` whenever a link's security changes."""
def remove_listener(callback: Callable[..., Any]) -> None: ...
def expect_passkey(conn_handle: int, passkey: int | str | Callable[[], int | str | None] | None) -> None:
    """As central: the passkey to type in when this connection's peer shows one."""
def configure(
    mode: Literal["justworks", "passkey", "numeric", "auto"],
    *,
    show: Callable[[int], Any] | None = None,
    hide: Callable[[], Any] | None = None,
    confirm: Callable[[int], bool | None] | None = None,
    display: _Display | None = None,
) -> Literal["justworks", "passkey", "numeric"]:
    """Set this board's pairing as a peripheral. Returns the mode actually used."""
def answer(conn_handle: int, accept: bool) -> None:
    """Answer a numeric comparison that `confirm` deferred."""
def random_passkey() -> int:
    """Six random digits, as an int (000000-999999)."""
def poll() -> None:
    """Run work the IRQ couldn't schedule. Cheap when there's none."""
def find_display() -> Any:
    """`board_config.display_drv`, or `None` on a board without a display."""
def display_passkey(display: _Display | None = None) -> tuple[Callable[[int], None], Callable[[], None]]:
    """`(show, hide)`: draw a passkey big in the middle of `display`, and clear it again."""
