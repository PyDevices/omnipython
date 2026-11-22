# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""A board's Wi-Fi networks as endpointkit ``net`` endpoints, joined from a picker."""

from typing import Any

import endpointkit

RESCAN_MS: int

class WifiNet(endpointkit.Provider):
    """The board's Wi-Fi station."""

    radio: Any
    rescan_ms: int
    timeout: int
    module: str
    def __init__(self, radio: Any = None, rescan_ms: int | None = None, timeout: int = ..., module: str = "secrets") -> None: ...
    def scan(self) -> list[endpointkit.Endpoint]: ...
    def poll(self) -> list[endpointkit.Endpoint] | None: ...
    def apply(self, endpoint: endpointkit.Endpoint, chosen: bool) -> None: ...
    def pair(self, endpoint: endpointkit.Endpoint, secret: str | None = None) -> None: ...

def register(registry: endpointkit.Registry | None = None, radio: Any = None) -> WifiNet:
    """Register the board's Wi-Fi, and choose the network it's on when ``net`` has no choice yet."""
