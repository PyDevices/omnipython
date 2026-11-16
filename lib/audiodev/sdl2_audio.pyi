# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""SDL2 audio backend for `audiodev` (pure Python, queued audio only)."""

from typing import Literal

from audiodev import AudioFormat as AudioFormat, AudioSession, PCMInput as PCMInput, PCMOutput as PCMOutput, check_latency as check_latency
from audiodev.bytequeue import ByteQueue as ByteQueue

DEFAULT_PLAY_SAMPLES: int
DEFAULT_PLAY_QUEUE_MS: int
DEFAULT_COALESCE_MS: int
PREBUFFER_MS: int
STALL_WINDOW_MS: int
STALL_RATIO: float
STALL_SAMPLE_MS: int
RECOVER_GRACE_MS: int
RECOVER_SETTLE_MS: int

def list_audio_devices(capture: bool = False) -> tuple[str, ...]:
    """Return SDL playback or capture device names."""

class SDLPCMOutput(PCMOutput):
    """SDL playback via `SDL_QueueAudio` (no audio callback, no mixer)."""

    device_name: str | None
    samples: int
    queue_ms: int
    poll_ms: int
    device: int
    coalesce_ms: int
    recycles: int
    lost_bytes: int
    requeued_bytes: int
    channel: None
    mode: str
    def __init__(
        self,
        fmt: AudioFormat,
        *,
        device: str | None = None,
        samples: int = 512,
        queue_ms: int = 250,
        poll_ms: int = 2,
        coalesce_ms: int = ...,
        prebuffer_ms: int | None = None,
        session: AudioSession | None = None,
    ) -> None: ...
    def queued_size(self) -> int: ...
    def is_active(self) -> bool: ...
    def clear(self) -> None: ...
    def service(self) -> None: ...
    def drain(self, timeout_ms: int | None = None) -> bool:
        """Block until queued PCM has played out. `False` if it timed out."""
    async def adrain(self, timeout_ms: int | None = None) -> bool:
        """Async `drain`."""

class SDLPCMInput(PCMInput):
    """SDL capture through a real host input device."""

    device_name: str | None
    samples: int
    queue_ms: int
    poll_ms: int
    timeout_ms: int | None
    device: int
    def __init__(
        self,
        fmt: AudioFormat,
        *,
        device: str | None = None,
        samples: int = 512,
        queue_ms: int = 250,
        poll_ms: int = 2,
        timeout_ms: int | None = 100,
    ) -> None: ...

def pcm_out(
    format: AudioFormat | None = None,
    *,
    device: str | None = None,
    latency: Literal["low", "buffered"] | None = None,
    samples: int | None = None,
    queue_ms: int | None = None,
    coalesce_ms: int | None = None,
    prebuffer_ms: int | None = None,
    poll_ms: int = 2,
) -> SDLPCMOutput:
    """Create an SDL-backed `PCMOutput`."""

def pcm_in(
    format: AudioFormat | None = None,
    *,
    device: str | None = None,
    latency: Literal["low", "buffered"] | None = None,
    samples: int | None = None,
    queue_ms: int | None = None,
    poll_ms: int = 2,
    timeout_ms: int | None = 100,
) -> SDLPCMInput:
    """Create an SDL-backed `PCMInput` using real host capture."""
