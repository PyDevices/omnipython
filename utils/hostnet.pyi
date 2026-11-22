# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""A computer's network as an endpointkit ``net`` endpoint, reported and never changed."""

from collections.abc import Callable, Sequence

import endpointkit

RESCAN_MS: int

def default_address() -> str | None:
    """The address the system would send from, or None."""

def interfaces() -> list[str]:
    """The names of the network interfaces besides loopback, where the system lists them."""

class HostNet(endpointkit.Provider):
    """The operating system's network, report only."""

    rescan_ms: int
    def __init__(
        self,
        address: Callable[[], str | None] | None = None,
        names: Callable[[], Sequence[str]] | None = None,
        rescan_ms: int = ...,
    ) -> None: ...
    def scan(self) -> list[endpointkit.Endpoint]: ...
    def poll(self) -> list[endpointkit.Endpoint] | None: ...
    def apply(self, endpoint: endpointkit.Endpoint, chosen: bool) -> None: ...

def register(registry: endpointkit.Registry | None = None) -> HostNet:
    """Register the host's network and choose it when ``net`` has no choice yet."""
