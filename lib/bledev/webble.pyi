# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Web Bluetooth backend for browsers. Central only."""
from . import BLE, Device, UUID, _UUIDLike
from collections.abc import Callable, Iterable
from typing import Any, NoReturn

create_proxy: Callable[..., Any] | None

def available() -> bool:
    """True when this page can use Web Bluetooth."""

class WebBLE(BLE):
    """The browser's Bluetooth, through `navigator.bluetooth`. Central only."""

    backend: str
    CONNECT_ATTEMPTS: int
    bluetooth: Any
    optional_services: list[UUID]
    link_mtu: int
    queue_limit: int
    connect_retries: int
    def __init__(self, *, services: Iterable[_UUIDLike] = (), mtu: int = ..., queue_limit: int = 512) -> None: ...
    def capabilities(self) -> dict[str, Any]: ...
    def config(self, *names: str, **settings: Any) -> int | None: ...
    def close(self) -> None: ...
    def scan(self, duration_ms: int, *, active: bool = False, interval_us: int | None = None, window_us: int | None = None) -> NoReturn:
        """Always raises `UnsupportedError`: a browser has no scan, `find()` opens its device chooser instead."""
    async def find(self, name: str | None = None, service: _UUIDLike | None = None, *, timeout_ms: int = 10000, active: bool = True) -> Device:
        """Open the browser's device chooser and return the `Device` picked."""

DISCOVERY_FLOOR_MS: int
