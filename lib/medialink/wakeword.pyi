# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""A wake word, such as "Hey Jarvis", to open the hands-free floor."""

from typing import Any, Protocol

from medialink.voice import VoiceActivity as VoiceActivity, _VoiceGate

class _Spotter(Protocol):
    """A wake word detector: `MicroWakeWord` or anything shaped like it."""

    name: str
    def feed(self, pcm: bytes | bytearray | memoryview, rate: int, channels: int) -> bool: ...
    def reset(self) -> None: ...

class MicroWakeWord:
    """A microWakeWord model, loaded from its JSON manifest."""

    name: str
    model: Any
    frontend: Any
    cutoff: int
    window: int
    stride: int
    warm_up: int
    def __init__(self, manifest: str, *, warm_up: int = 100, model: Any = None, frontend: Any = None) -> None: ...
    def reset(self) -> None:
        """Start again, warming up as at the start."""
    @property
    def probability(self) -> float:
        """The model's latest output, 0.0 to 1.0, for a score meter."""
    def feed(self, pcm: bytes | bytearray | memoryview, rate: int, channels: int) -> bool:
        """Take signed 16-bit PCM. True if the wake word ended in it."""

class WakeWord:
    """Opens the floor on a wake word; a stand-in for `VoiceActivity`."""

    spotter: _Spotter
    voice: _VoiceGate
    rate: int
    channels: int
    listen_ms: int
    detector: str
    heard: int
    def __init__(
        self,
        manifest: str | None = None,
        rate: int = 16000,
        channels: int = 1,
        *,
        voice: _VoiceGate | None = None,
        listen_ms: int = 2000,
        spotter: _Spotter | None = None,
    ) -> None: ...
    @property
    def level(self) -> int:
        """The last frame's level, for a meter."""
    @property
    def speaking(self) -> bool:
        """True while the floor is open: after the word, until speech stops."""
    def feed(self, pcm: bytes | bytearray | memoryview) -> bool:
        """Take a frame of signed 16-bit PCM. True while it is worth sending."""
    def reset(self) -> None:
        """Close the floor and forget the room."""
