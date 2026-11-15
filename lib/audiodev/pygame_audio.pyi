# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""pygame-ce playback and capture backend for the portable `audiodev` contract."""

from typing import Literal

from audiodev import AudioFormat as AudioFormat, PCMInput as PCMInput, PCMOutput as PCMOutput, check_latency as check_latency

DEFAULT_PLAY_SAMPLES: int
DEFAULT_PLAY_QUEUE_MS: int
DEFAULT_COALESCE_MS: int
PREBUFFER_MS: int
STALL_WINDOW_MS: int
STALL_RATIO: float
STALL_SAMPLE_MS: int
RECOVER_GRACE_MS: int
RECOVER_SETTLE_MS: int

class PygamePCMOutput(PCMOutput):
    """PCM playback via pygame's SDL `QueueAudio` (no mixer, no Python callback)."""

    samples: int
    poll_ms: int
    coalesce_ms: int
    device: int
    channel: None
    mode: str
    recycles: int
    lost_bytes: int
    requeued_bytes: int
    def __init__(
        self,
        fmt: AudioFormat,
        *,
        samples: int = ...,
        poll_ms: int = 2,
        queue_ms: int = ...,
        coalesce_ms: int = ...,
    ) -> None: ...
    def queued_size(self) -> int: ...
    def is_active(self) -> bool: ...
    def service(self) -> None: ...
    def drain(self, timeout_ms: int | None = None) -> bool:
        """Block until queued PCM has played out. `False` if it timed out."""
    async def adrain(self, timeout_ms: int | None = None) -> bool:
        """Async `drain`."""
    def clear(self) -> None: ...

class PygamePCMInput(PCMInput):
    """Capture through pygame's `_sdl2.AudioDevice`."""

    device_name: str | None
    samples: int
    poll_ms: int
    def __init__(
        self,
        fmt: AudioFormat,
        *,
        device: str | None = None,
        samples: int = 512,
        poll_ms: int = 2,
        queue_ms: int = 500,
    ) -> None: ...

def pcm_out(
    format: AudioFormat | None = None,
    *,
    latency: Literal["low", "buffered"] | None = None,
    samples: int | None = None,
    poll_ms: int = 2,
    queue_ms: int | None = None,
    coalesce_ms: int | None = None,
) -> PygamePCMOutput:
    """Create a pygame-ce-backed PCM playback device."""

def pcm_in(
    format: AudioFormat | None = None,
    *,
    device: str | None = None,
    latency: Literal["low", "buffered"] | None = None,
    samples: int | None = None,
    poll_ms: int = 2,
    queue_ms: int | None = None,
) -> PygamePCMInput:
    """Create a pygame-ce-backed PCM capture device."""
