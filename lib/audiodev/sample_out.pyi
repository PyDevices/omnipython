# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""CircuitPython-shaped sample playback, off the interpreter thread where it can."""

import types
from typing import Any, Literal, Protocol

from typing_extensions import Self

from audiodev import AudioFormat, PCMOutput

__all__ = ("AudioOut", "sample_out")

class _AudioSample(Protocol):
    """A CircuitPython-shaped audiosample."""

    @property
    def sample_rate(self) -> int: ...
    @property
    def channel_count(self) -> int: ...
    @property
    def bits_per_sample(self) -> int: ...

class _TransportFactory(Protocol):
    """A backend module (or any object) exposing `pcm_out`."""

    def pcm_out(self, format: AudioFormat | None = None, **kwargs: Any) -> PCMOutput: ...

class _Rearranging:
    def __enter__(self) -> None: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: types.TracebackType | None,
    ) -> Literal[False]: ...

class AudioOut:
    """Pull-based sample player over a push transport."""

    transport: PCMOutput
    chunk_ms: int
    stalls: int
    def __init__(
        self,
        transport: PCMOutput,
        *,
        chunk_ms: int = 40,
        lookahead_chunks: int = 2,
        max_catchup_chunks: int = 5,
        pump: bool = True,
    ) -> None: ...
    @property
    def format(self) -> AudioFormat: ...
    def open(self) -> Self: ...
    def close(self) -> None: ...
    def deinit(self) -> None: ...
    def __enter__(self) -> Self: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: types.TracebackType | None,
    ) -> None: ...
    @property
    def pumped(self) -> bool:
        """True while this player's audio is being pulled by the pump."""
    @property
    def pump_refused(self) -> str | None:
        """Why the pump would not take this graph, or `None`."""
    @property
    def volume(self) -> int: ...
    def set_volume(self, percent: int | float) -> int: ...
    @property
    def muted(self) -> bool: ...
    def mute(self, value: bool = True) -> bool: ...
    @property
    def codec(self) -> Any: ...
    def play(self, sample: _AudioSample, *, loop: bool = False) -> None:
        """Start playing `sample`. Replaces whatever was already playing."""
    def stop(self) -> None: ...
    def pause(self) -> None: ...
    def resume(self) -> None: ...
    @property
    def playing(self) -> bool: ...
    @property
    def paused(self) -> bool: ...
    def service(self) -> None:
        """Call from the app tick. Required for continuous playback."""
    def attach(self, app: Any, period_ms: int | None = None) -> Self:
        """Subscribe `service` to `app`'s shared timer; returns `self`."""
    def detach(self) -> None: ...

def sample_out(
    transport_factory: _TransportFactory, format: AudioFormat | None = None, **kwargs: Any
) -> AudioOut:
    """Wrap a backend's `pcm_out(format, **kwargs)` transport in `AudioOut`."""
