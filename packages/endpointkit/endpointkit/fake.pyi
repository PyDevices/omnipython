# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Providers with no hardware behind them, for tests and for trying a picker."""

from collections.abc import Iterable, Sequence

import endpointkit

class FakeProvider(endpointkit.Provider):
    """A provider that finds what it's told to."""

    fail: list[str]
    secrets: dict[str, tuple[str, str]]
    started: list[str]
    log: list[tuple[str, str]]
    def __init__(
        self,
        kind: str,
        name: str,
        found: Iterable[Sequence[str]] = (),
        resources: Iterable[str] = (),
        delay: int = 0,
        fail: Iterable[str] = (),
        secrets: dict[str, tuple[str, str]] | None = None,
    ) -> None: ...
    def scan(self) -> list[endpointkit.Endpoint]: ...
    def poll(self) -> list[endpointkit.Endpoint] | None: ...
    def apply(self, endpoint: endpointkit.Endpoint, chosen: bool) -> None: ...
    def pair(self, endpoint: endpointkit.Endpoint, secret: str | None = None) -> None: ...
    def add(self, local_id: str, label: str, state: str = ...) -> None:
        """Find another endpoint."""
    def remove(self, local_id: str) -> None:
        """Lose an endpoint, as when a device is unplugged."""
    def set_state(self, local_id: str, state: str) -> None:
        """Change an endpoint's state, as when a speaker connects."""

def bench(registry: endpointkit.Registry | None = None, delay: int = 2) -> dict[str, FakeProvider]:
    """Register fakes for a board's transports; returns them by name."""
