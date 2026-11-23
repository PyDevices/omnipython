# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Play to Bluetooth headphones or a speaker, as a board's audio output."""

from typing import Any

import endpointkit
from audiodev import AudioFormat, PCMOutput
from audiodev.sample_out import AudioOut

INQUIRY_MS: int

class SourceOutput(PCMOutput):
    """A Bluetooth A2DP source as an audiodev ``PCMOutput``."""

    source: Any
    dropped: int
    def __init__(self, source: Any, format: AudioFormat, **kwargs: Any) -> None: ...
    def stats(self) -> dict[str, int]:
        """The source's counters and ``dropped``, in bytes."""

class BluetoothOut(endpointkit.Provider):
    """Bluetooth headphones and speakers, under ``audio.out``."""

    bc: Any
    inquiry_ms: int
    bt: Any
    source: Any
    known: list[list[Any]]
    def __init__(self, module: Any = None, inquiry_ms: int = ...) -> None: ...
    def scan(self) -> list[endpointkit.Endpoint]: ...
    def poll(self) -> list[endpointkit.Endpoint] | None: ...
    def apply(self, endpoint: endpointkit.Endpoint, chosen: bool) -> None: ...
    def open_out(self, endpoint: endpointkit.Endpoint, format: AudioFormat | None = None, *,
                 latency: str | None = None, **kwargs: Any) -> AudioOut:
        """The chosen speaker as an ``audiodev.AudioOut``."""
    def stop(self) -> None: ...

def register(registry: endpointkit.Registry | None = None) -> BluetoothOut:
    """Register the Bluetooth speaker provider, once; returns it."""
