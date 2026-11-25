# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""A computer's sound devices, and a board's outputs, as endpointkit endpoints, for ``audio.out`` and ``audio.in``."""

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

class BoardAudio(endpointkit.Provider):
    """A board's own audio output, the one its ``audio_out`` role opens."""

    factory: Callable[..., object]
    label: str
    chosen: bool
    def __init__(self, factory: Callable[..., object], label: str = "Built-in audio") -> None: ...
    def scan(self) -> list[endpointkit.Endpoint]: ...
    def apply(self, endpoint: endpointkit.Endpoint, chosen: bool) -> None: ...
    def open_out(self, endpoint: endpointkit.Endpoint, *args: object, **kwargs: object) -> object:
        """Open the board's own output, with the arguments ``audio_out`` was given."""

class BoardAudioIn(endpointkit.Provider):
    """A board's own microphones, the ones its ``pcm_in`` role opens."""

    factory: Callable[..., object]
    label: str
    chosen: bool
    def __init__(self, factory: Callable[..., object], label: str = "Built-in microphones") -> None: ...
    def scan(self) -> list[endpointkit.Endpoint]: ...
    def apply(self, endpoint: endpointkit.Endpoint, chosen: bool) -> None: ...
    def open_in(self, endpoint: endpointkit.Endpoint, *args: object, **kwargs: object) -> object:
        """Open the board's own microphones, with the arguments ``pcm_in`` was given."""

class RoutedAudioOut:
    """A board's ``audio_out`` that opens whichever ``audio.out`` endpoint is chosen."""

    board: BoardAudio
    registry: endpointkit.Registry
    capability: object
    def __init__(self, board: BoardAudio, registry: endpointkit.Registry, capability: object = None) -> None: ...
    def __call__(self, *args: object, **kwargs: object) -> object: ...

def playing_on(registry: endpointkit.Registry | None = None) -> endpointkit.Endpoint | None:
    """The ``audio.out`` endpoint a routed ``audio_out`` opens now, or None for the board's own output."""

class RoutedPCMIn:
    """A board's ``pcm_in`` that records from whichever ``audio.in`` endpoint is chosen."""

    board: BoardAudioIn
    registry: endpointkit.Registry
    capability: object
    def __init__(self, board: BoardAudioIn, registry: endpointkit.Registry, capability: object = None) -> None: ...
    def __call__(self, *args: object, **kwargs: object) -> object: ...

def listening_on(registry: endpointkit.Registry | None = None) -> endpointkit.Endpoint | None:
    """The ``audio.in`` endpoint a routed ``pcm_in`` opens now, or None for the board's own microphones."""

def route(
    peripherals: object,
    registry: endpointkit.Registry | None = None,
    label: str = "Built-in audio",
    in_label: str = "Built-in microphones",
) -> BoardAudio:
    """List the board's own output under ``audio.out``, and make its ``audio_out`` play wherever ``audio.out`` is chosen; its ``pcm_in`` the same under ``audio.in``."""
