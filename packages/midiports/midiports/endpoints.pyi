# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""A computer's or a browser page's MIDI ports as endpointkit endpoints, chosen once for every program."""

from types import ModuleType

from _typeshed import ReadableBuffer, WriteableBuffer

import endpointkit

from . import PortIn, PortOut

RESCAN_MS: int
ALLOW: str

class HostMidi(endpointkit.Provider):
    """One direction of the host's MIDI ports."""

    backend: ModuleType
    direction: str
    rescan_ms: int
    open: dict[str, PortIn | PortOut]
    def __init__(self, direction: str, backend: ModuleType | None = None, rescan_ms: int = ...) -> None: ...
    def scan(self) -> list[endpointkit.Endpoint]: ...
    def poll(self) -> list[endpointkit.Endpoint] | None: ...
    def pair(self, endpoint: endpointkit.Endpoint, secret: str | None = None) -> None: ...
    def apply(self, endpoint: endpointkit.Endpoint, chosen: bool) -> None: ...
    def stop(self) -> None: ...

class Merged(PortIn):
    """Every chosen input as one port."""

    providers: list[HostMidi]
    provider: HostMidi
    def __init__(self, providers: HostMidi | list[HostMidi]) -> None: ...
    def any(self) -> int: ...
    def readinto(self, buf: WriteableBuffer, nbytes: int | None = None) -> int | None: ...
    def take_timestamp(self) -> int | None: ...

class FanOut(PortOut):
    """Every chosen output at once."""

    providers: list[HostMidi]
    provider: HostMidi
    def __init__(self, providers: HostMidi | list[HostMidi]) -> None: ...
    def write(self, buf: ReadableBuffer, nbytes: int | None = None) -> int: ...

def register(registry: endpointkit.Registry | None = None, backend: ModuleType | None = None) -> tuple[HostMidi, HostMidi]:
    """Register the host's MIDI inputs and outputs; returns ``(inputs, outputs)``."""

def merged_in() -> Merged:
    """One port reading every chosen MIDI input."""

def fan_out() -> FanOut:
    """One port writing to every chosen MIDI output."""
