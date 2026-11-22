# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Boards nearby as endpointkit ``espnow.peer`` endpoints, found and chosen over ESP-NOW."""

from typing import Any

import endpointkit

KIND: str
BEACON_MS: int
FORGET_MS: int
MAX_READS: int
INBOX: int
MAX_DATA: int

class EspNowPeers(endpointkit.Provider):
    """The boards in ESP-NOW range that run this provider too."""

    esp: Any
    board_name: str
    beacon_ms: int
    forget_ms: int
    dropped: int
    ignored: int
    def __init__(self, esp: Any = None, name: str | None = None, beacon_ms: int | None = None, forget_ms: int | None = None) -> None: ...
    def scan(self) -> list[endpointkit.Endpoint]: ...
    def poll(self) -> list[endpointkit.Endpoint] | None: ...
    def apply(self, endpoint: endpointkit.Endpoint, chosen: bool) -> None: ...
    def stop(self) -> None: ...
    def send(self, data: bytes, to: str | None = None) -> int:
        """Send *data* to every chosen board, or to the one with endpoint id *to*."""
    def recv(self) -> tuple[str, bytes] | None:
        """The oldest message from a chosen board, as ``(endpoint id, bytes)``, or None."""

def register(registry: endpointkit.Registry | None = None, esp: Any = None, name: str | None = None) -> EspNowPeers:
    """Make the ``espnow.peer`` kind known and register this board's ESP-NOW once."""

def send(data: bytes, to: str | None = None) -> int:
    """Send *data* to the chosen boards through the registered provider."""

def recv() -> tuple[str, bytes] | None:
    """The oldest message from a chosen board through the registered provider."""
