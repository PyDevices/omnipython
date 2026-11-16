# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Is anyone speaking? Voice activity for a hands-free floor."""

from typing import Literal, Protocol

class _VoiceGate(Protocol):
    """What an `Intercom` needs to decide when to send: `VoiceActivity` or `WakeWord`."""

    @property
    def level(self) -> int: ...
    @property
    def speaking(self) -> bool: ...
    def feed(self, pcm: bytes | bytearray | memoryview) -> bool: ...
    def reset(self) -> None: ...

class VoiceActivity:
    """Feed it 16-bit PCM, a frame at a time; `feed()` says whether to send."""

    rate: int
    channels: int
    hold_ms: int
    detector: Literal["audiofeatures", "level"]
    level: int
    def __init__(
        self,
        rate: int = 16000,
        channels: int = 1,
        *,
        hold_ms: int = 600,
        detector: Literal["audiofeatures", "level"] | None = None,
    ) -> None: ...
    @property
    def speaking(self) -> bool:
        """True while speech was heard within `hold_ms`."""
    def feed(self, pcm: bytes | bytearray | memoryview) -> bool:
        """Take a frame of signed 16-bit PCM. True while it is worth sending."""
    def reset(self) -> None:
        """Forget the room: for a new microphone, or a new place."""
