# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""A computer's sound devices as endpointkit endpoints, for ``audio.out`` and ``audio.in``."""

from collections.abc import Callable, Sequence

import endpointkit

RESCAN_MS: int

class HostAudio(endpointkit.Provider):
    """The host's playback or capture devices, through one audiodev backend."""

    backend: str
    capture: bool
    rescan_ms: int
    def __init__(
        self,
        capture: bool = False,
        backend: str | None = None,
        names: Callable[[str, bool], Sequence[str]] | None = None,
        rescan_ms: int = ...,
    ) -> None: ...
    def scan(self) -> list[endpointkit.Endpoint]: ...
    def poll(self) -> list[endpointkit.Endpoint] | None: ...

def register(registry: endpointkit.Registry | None = None, backend: str | None = None) -> tuple[HostAudio, HostAudio]:
    """Register the host's outputs and inputs; returns ``(outputs, inputs)``."""

def device(kind: str = "audio.out", registry: endpointkit.Registry | None = None) -> str | None:
    """The device name to open for *kind*'s first chosen endpoint; None for the system default."""

def devices(kind: str = "audio.out", registry: endpointkit.Registry | None = None) -> list[str | None]:
    """The device names of every chosen, found endpoint of *kind*."""
