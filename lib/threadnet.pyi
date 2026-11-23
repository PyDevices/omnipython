# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""A board's Thread networks as endpointkit ``thread.net`` endpoints, formed or joined from a picker."""

from typing import Any

import endpointkit

KIND: str
RESCAN_MS: int
ON_NETWORK: tuple[str, ...]

def parse(dataset: bytes | str) -> dict[str, Any]:
    """The parts of a Thread dataset that the provider reads, as a dict."""

def build(name: str, extpanid: str, panid: int, channel: int, key: str) -> bytes:
    """A dataset as TLVs from a network's name, IDs, channel and key."""

def extpanid(dataset: bytes | str) -> str | None:
    """The extended PAN ID of *dataset* (TLVs or hex), as hex: the network's local endpoint id."""

class ThreadNet(endpointkit.Provider):
    """The board's Thread interface on its 802.15.4 radio."""

    ot: Any
    rescan_ms: int
    def __init__(self, ot: Any = None, rescan_ms: int | None = None) -> None: ...
    def scan(self) -> list[endpointkit.Endpoint]: ...
    def poll(self) -> list[endpointkit.Endpoint] | None: ...
    def apply(self, endpoint: endpointkit.Endpoint, chosen: bool) -> None: ...
    def pair(self, endpoint: endpointkit.Endpoint, secret: str | None = None) -> None: ...
    def stop(self) -> None: ...
    def form(self, name: str, channel: int | None = None) -> str:
        """Make a new network on this board, lead it, and return its dataset as hex."""

def register(registry: endpointkit.Registry | None = None, ot: Any = None) -> ThreadNet:
    """Make the ``thread.net`` kind known, register the board's Thread once, and choose the network it's on."""

def form(name: str, channel: int | None = None) -> str:
    """Make a new network through the registered provider, and choose it."""
