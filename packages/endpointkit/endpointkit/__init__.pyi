# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Choose where audio goes, which MIDI ports are in, which network carries traffic."""

from collections.abc import Callable, Iterable
from typing import Any

__version__: str
ONE: int
MANY: int
KINDS: dict[str, int]
NAMES: dict[str, tuple[str, str]]
OTHER_ICON: str
AVAILABLE: str
CONNECTED: str
NEEDS_PAIRING: str
UNAVAILABLE: str
PASSWORD: str
PIN: str
ENDPOINTS: str
STATE: str
SELECTION: str
ERROR: str

_Ids = str | Iterable[str] | None
_Callback = Callable[[str, str], object]

def add_kind(name: str, count: int = ..., title: str | None = None, icon: str | None = None) -> None:
    """Make a new kind known, choosing `ONE` or `MANY` endpoints at a time, with what it's called and its icon."""
def kinds() -> list[str]:
    """Every kind known, in the order they became known."""
def title(kind: str) -> str:
    """What a person calls `kind`, or the kind's own name."""
def icon(kind: str) -> str:
    """`kind`'s icon, a Material Symbols name; `OTHER_ICON` when it has none."""

class Conflict(Exception):
    """A choice would stop endpoints that are using the same resources."""

    kind: str
    stops: list[Endpoint]
    resources: list[str]
    def __init__(self, kind: str, stops: list[Endpoint], resources: list[str]) -> None: ...

class Endpoint:
    """Something a provider found that the device can connect to."""

    provider: Provider
    local_id: str
    id: str
    kind: str
    label: str
    state: str
    caps: dict[str, Any]
    resources: tuple[str, ...]
    error: str | None
    asks: str | None
    def __init__(
        self,
        provider: Provider,
        local_id: str,
        label: str,
        state: str = ...,
        caps: dict[str, Any] | None = None,
        resources: Iterable[str] | None = None,
        asks: str | None = None,
    ) -> None: ...

class Provider:
    """One transport for one kind."""

    kind: str | None
    name: str | None
    resources: tuple[str, ...]
    remember: bool
    def __init__(self, kind: str | None = None, name: str | None = None, resources: Iterable[str] | None = None) -> None: ...
    def endpoint(
        self,
        local_id: str,
        label: str,
        state: str = ...,
        caps: dict[str, Any] | None = None,
        resources: Iterable[str] | None = None,
        asks: str | None = None,
    ) -> Endpoint:
        """An `Endpoint` of this provider, for `scan` and `poll` to return."""
    def scan(self) -> list[Endpoint]:
        """The endpoints known now."""
    def poll(self) -> list[Endpoint] | None:
        """A new list of endpoints when something changed, or None."""
    def apply(self, endpoint: Endpoint, chosen: bool) -> None:
        """Start using *endpoint* when *chosen* is True, stop when False."""
    def pair(self, endpoint: Endpoint, secret: str | None = None) -> None:
        """Pair with or join *endpoint*; raise to refuse."""
    def stop(self) -> None:
        """Release whatever the provider holds."""

class Registry:
    """Every provider's endpoints, the device's choices, the pins and the subscribers."""

    def __init__(self, store: str | None = None) -> None: ...
    def register(self, provider: Any) -> Any: ...
    def unregister(self, provider: Provider) -> None: ...
    def providers(self, kind: str | None = None) -> list[Provider]: ...
    def poll(self) -> bool: ...
    def refresh(self, kind: str | None = None) -> None: ...
    def pair(self, endpoint_id: str, secret: str | None = None) -> Endpoint: ...
    def endpoints(self, kind: str) -> list[Endpoint]: ...
    def find(self, endpoint_id: str) -> Endpoint | None: ...
    def chosen(self, kind: str) -> list[str]: ...
    def pinned(self, kind: str) -> tuple[str, list[str]] | None: ...
    def selection(self, kind: str) -> list[str]: ...
    def selected(self, kind: str) -> list[Endpoint]: ...
    def conflicts(self, kind: str, ids: _Ids) -> tuple[list[Endpoint], list[str]]: ...
    def select(self, kind: str, ids: _Ids, confirm: bool = False) -> None: ...
    def pin(self, kind: str, ids: _Ids, owner: str, confirm: bool = False) -> None: ...
    def unpin(self, owner: str, kind: str | None = None) -> None: ...
    def subscribe(self, kind: str | None, callback: _Callback) -> _Callback: ...
    def unsubscribe(self, callback: _Callback) -> None: ...
    def set_store(self, path: str) -> None: ...

registry: Registry

def register(provider: Any) -> Any: ...
def unregister(provider: Provider) -> None: ...
def providers(kind: str | None = None) -> list[Provider]: ...
def poll() -> bool: ...
def refresh(kind: str | None = None) -> None: ...
def pair(endpoint_id: str, secret: str | None = None) -> Endpoint: ...
def endpoints(kind: str) -> list[Endpoint]: ...
def find(endpoint_id: str) -> Endpoint | None: ...
def chosen(kind: str) -> list[str]: ...
def pinned(kind: str) -> tuple[str, list[str]] | None: ...
def selection(kind: str) -> list[str]: ...
def selected(kind: str) -> list[Endpoint]: ...
def conflicts(kind: str, ids: _Ids) -> tuple[list[Endpoint], list[str]]: ...
def select(kind: str, ids: _Ids, confirm: bool = False) -> None: ...
def pin(kind: str, ids: _Ids, owner: str, confirm: bool = False) -> None: ...
def unpin(owner: str, kind: str | None = None) -> None: ...
def subscribe(kind: str | None, callback: _Callback) -> _Callback: ...
def unsubscribe(callback: _Callback) -> None: ...
def set_store(path: str) -> None: ...
