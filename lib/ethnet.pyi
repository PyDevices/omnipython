# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""A board's Ethernet port as an endpointkit ``net`` endpoint, so a picker can move traffic onto it."""

from typing import Any

import endpointkit

RESCAN_MS: int

class EthNet(endpointkit.Provider):
    """The board's Ethernet port."""

    nic: Any
    rescan_ms: int
    brought_up: bool
    def __init__(self, nic: Any = None, rescan_ms: int | None = None) -> None: ...
    def scan(self) -> list[endpointkit.Endpoint]: ...
    def poll(self) -> list[endpointkit.Endpoint] | None: ...
    def apply(self, endpoint: endpointkit.Endpoint, chosen: bool) -> None: ...
    def is_default(self) -> bool | None:
        """True when Ethernet carries the board's traffic; None when the firmware can't say."""
    def address(self) -> str | None:
        """The port's IPv4 address, or None without a link and a lease."""

def register(registry: endpointkit.Registry | None = None, nic: Any = None) -> EthNet:
    """Register the board's Ethernet, and choose it when it already carries traffic and ``net`` has no choice yet."""
