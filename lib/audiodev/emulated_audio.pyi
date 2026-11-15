# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""CI / no-hardware PCM: WAV files, waveform generator, in-memory loopback."""

from typing import Literal

from audiodev import AudioFormat as AudioFormat, PCMInput as PCMInput, PCMOutput as PCMOutput, queue_bytes as queue_bytes
from audiodev.bytequeue import ByteQueue as ByteQueue

def wav_header(fmt: AudioFormat, data_length: int) -> bytes:
    """Build a 44-byte PCM RIFF/WAVE header for `fmt` and `data_length` bytes."""

def parse_pcm_wav(data: bytes | bytearray | memoryview) -> tuple[AudioFormat, bytes]:
    """Return `(AudioFormat, pcm_bytes)` from a PCM WAV buffer."""

class WavPCMOutput(PCMOutput):
    """Write interleaved PCM into a WAV file; finalize sizes on close."""

    path: str
    def __init__(self, path: str, format: AudioFormat) -> None: ...

class WavPCMInput(PCMInput):
    """Read interleaved PCM from a WAV file; `readinto` returns 0 at EOF."""

    path: str
    def __init__(self, path: str) -> None: ...

class NullPCMOutput(PCMOutput):
    """Discard PCM (write-path tests that must not touch a host sink)."""

    written: int
    def __init__(self, format: AudioFormat) -> None: ...

class LoopbackBuffer:
    """Shared in-memory PCM queue for a loopback pair."""

    format: AudioFormat
    limit: int
    def __init__(self, format: AudioFormat, *, queue_ms: int | float | None = None) -> None: ...
    def write(self, buf: bytes | bytearray | memoryview) -> int: ...
    def readinto(self, buf: bytearray | memoryview) -> int: ...
    def queued_size(self) -> int: ...
    def clear(self) -> None: ...

class LoopbackPCMOutput(PCMOutput):
    """Enqueue PCM into a `LoopbackBuffer`."""

    def __init__(self, buffer: LoopbackBuffer) -> None: ...
    def queued_size(self) -> int: ...
    def is_active(self) -> bool: ...
    def clear(self) -> None: ...

class LoopbackPCMInput(PCMInput):
    """Dequeue PCM from a `LoopbackBuffer` (0 when empty)."""

    def __init__(self, buffer: LoopbackBuffer) -> None: ...
    def queued_size(self) -> int: ...
    def is_active(self) -> bool: ...
    def clear(self) -> None: ...

def loopback_pair(
    format: AudioFormat, *, queue_ms: int | float | None = None
) -> tuple[LoopbackPCMOutput, LoopbackPCMInput]:
    """Return `(LoopbackPCMOutput, LoopbackPCMInput)` sharing one buffer."""

class GeneratorPCMInput(PCMInput):
    """Endless or timed waveform as a `PCMInput` (no microphone)."""

    wave: Literal["sine", "square", "noise", "silence"]
    frequency: float
    amplitude: int
    duration_ms: int | None
    def __init__(
        self,
        format: AudioFormat,
        *,
        wave: Literal["sine", "square", "noise", "silence"] = "sine",
        frequency: int | float = 440,
        duration_ms: int | None = None,
        amplitude: int = 100,
    ) -> None: ...

def pcm_out(
    format: AudioFormat | None = None,
    *,
    path: str | None = None,
    loopback: LoopbackBuffer | None = None,
    discard: bool = False,
    queue_ms: int | float | None = None,
) -> PCMOutput:
    """Standalone emulated playback: WAV path, loopback buffer, or discard."""

def pcm_in(
    format: AudioFormat | None = None,
    *,
    path: str | None = None,
    loopback: LoopbackBuffer | None = None,
    wave: Literal["sine", "square", "noise", "silence"] | None = None,
    frequency: int | float = 440,
    duration_ms: int | None = None,
    amplitude: int = 100,
) -> PCMInput:
    """Standalone emulated capture: WAV path, loopback buffer, or generator."""
