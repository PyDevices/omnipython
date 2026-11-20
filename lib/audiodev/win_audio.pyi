# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""WASAPI queued PCM backend for Windows CPython (via `uwin32`)."""

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
WRITE_WAIT_MS: int

def list_audio_devices(capture: bool = False) -> tuple[str, ...]:
    """Return the friendly names of the active playback or capture endpoints."""
    ...

class WinPCMOutput(PCMOutput):
    """WASAPI shared-mode playback with a software coalescing queue."""

    device_name: str | None
    samples: int
    queue_ms: int
    poll_ms: int
    coalesce_ms: int
    recycles: int
    lost_bytes: int
    requeued_bytes: int
    def __init__(
        self,
        fmt: AudioFormat,
        *,
        device: str | None = None,
        samples: int = ...,
        queue_ms: int = ...,
        poll_ms: int = 2,
        coalesce_ms: int = ...,
        prebuffer_ms: int | None = None,
        session: AudioSession | None = None,
    ) -> None: ...
    @property
    def speaker_sink(self) -> str | None:
        """`"wasapi"` for the default device, which the pump can play to itself."""
    def queued_size(self) -> int: ...
    def is_active(self) -> bool: ...
    def clear(self) -> None: ...
    @property
    def buffer_frames(self) -> int:
        """Frames in the WASAPI buffer, or 0 while closed."""
    def device_frames(self) -> int:
        """Frames queued in the device now."""
    def write_now(self, buf: bytes | bytearray | memoryview, *, start: bool = True) -> int:
        """Write `buf` straight into the WASAPI buffer, now, and return the bytes written."""
    def start(self) -> bool:
        """Start playing what `write_now` has written; `True` once playing."""
    def service(self) -> int: ...

class WinPCMInput(PCMInput):
    """WASAPI shared-mode capture."""

    device_name: str | None
    samples: int
    queue_ms: int
    poll_ms: int
    def __init__(
        self,
        fmt: AudioFormat,
        *,
        device: str | None = None,
        samples: int = 512,
        queue_ms: int = 500,
        poll_ms: int = 2,
        session: AudioSession | None = None,
    ) -> None: ...
    def queued_size(self) -> int: ...

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
) -> WinPCMOutput:
    """Create a WASAPI-backed `PCMOutput`."""

def pcm_in(
    format: AudioFormat | None = None,
    *,
    device: str | None = None,
    latency: Literal["low", "buffered"] | None = None,
    samples: int | None = None,
    queue_ms: int | None = None,
    poll_ms: int = 2,
) -> WinPCMInput:
    """Create a WASAPI-backed `PCMInput`."""
