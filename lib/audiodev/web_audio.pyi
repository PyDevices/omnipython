# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Browser Web Audio backend for PyScript (`audiodev` PCM devices)."""

from typing import Literal

from audiodev import AudioFormat as AudioFormat, PCMInput as PCMInput, PCMOutput as PCMOutput, check_latency as check_latency
from audiodev.bytequeue import ByteQueue as ByteQueue

class WebPCMOutput(PCMOutput):
    """Playback scheduled onto a Web Audio `AudioContext` timeline."""

    poll_ms: int
    def __init__(self, fmt: AudioFormat, *, poll_ms: int = 4) -> None: ...
    def locked(self) -> bool:
        """True while the browser keeps the context suspended."""
        ...

class WebPCMInput(PCMInput):
    """Capture through `getUserMedia` and a `ScriptProcessorNode`."""

    poll_ms: int
    samples: int
    def __init__(
        self, fmt: AudioFormat, *, poll_ms: int = 4, queue_ms: int = 500, samples: int = 2048
    ) -> None: ...

def pcm_out(
    format: AudioFormat | None = None,
    *,
    latency: Literal["low", "buffered"] | None = None,
    poll_ms: int = 4,
) -> WebPCMOutput:
    """Create a Web Audio-backed `PCMOutput` (PyScript)."""

def pcm_in(
    format: AudioFormat | None = None,
    *,
    latency: Literal["low", "buffered"] | None = None,
    poll_ms: int = 4,
    queue_ms: int = 500,
    samples: int | None = None,
) -> WebPCMInput:
    """Create a Web Audio-backed `PCMInput` via `getUserMedia` (PyScript)."""
