# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""AudioWorklet output for Python running in a Pyodide Web Worker."""

from collections.abc import Callable
from typing import Any, Literal

from audiodev import AudioFormat as AudioFormat, PCMOutput as PCMOutput, check_latency as check_latency, queue_bytes as queue_bytes
from audiodev.bytequeue import ByteQueue as ByteQueue

BLOCK_FRAMES: int
DEFAULT_FORMAT: AudioFormat

class WorkletOutput:
    """The worker's end of an AudioWorklet port."""

    port: Any
    channels: int
    sample_rate: int
    source: Callable[[int], bytes | bytearray | memoryview | None] | None
    offset: int | None
    underruns: int
    starved: int
    frames: int
    asked: Any
    def __init__(
        self,
        port: Any,
        channels: Literal[1, 2] = 1,
        sample_rate: int = 48000,
        *,
        listen: bool = True,
    ) -> None: ...
    def block_bytes(self, blocks: int = 1) -> int:
        """Bytes in `blocks` blocks at this channel count."""
    def listen(self) -> None:
        """Take `port.onmessage`. Called for you unless `listen=False`."""
    def close(self) -> None:
        """Stop answering: release `port.onmessage` and its proxy."""
    def handle(self, data: Any) -> bool:
        """Act on one message from the worklet. Returns `True` if it was ours."""

class WorkletPCMOutput(PCMOutput):
    """`audiodev.PCMOutput` over an AudioWorklet port."""

    latency: Literal["low", "buffered"] | None
    poll_ms: int
    dropped: int
    worklet: WorkletOutput
    def __init__(
        self,
        fmt: AudioFormat,
        *,
        port: Any,
        latency: Literal["low", "buffered"] | None = None,
        queue_ms: int | float | None = None,
        poll_ms: int = 4,
        listen: bool = True,
        **kwargs: Any,
    ) -> None: ...
    @property
    def offset(self) -> int | None: ...
    @property
    def underruns(self) -> int: ...
    @property
    def starved(self) -> int: ...
    @property
    def frames(self) -> int: ...
    def handle(self, data: Any) -> bool:
        """Pass one worklet message in, when you created this with `listen=False`."""
    def space(self) -> int:
        """Bytes the queue can take now, in whole frames."""
    def queued_size(self) -> int: ...
    def is_active(self) -> bool: ...
    def clear(self) -> None: ...
    def try_write(self, buf: bytes | bytearray | memoryview) -> int: ...
    def deinit(self) -> None:
        """Close and stop answering the worklet."""

def pcm_out(
    format: AudioFormat | None = None,
    *,
    port: Any,
    latency: Literal["low", "buffered"] | None = None,
    queue_ms: int | float | None = None,
    poll_ms: int = 4,
    listen: bool = True,
) -> WorkletPCMOutput:
    """Create a `WorkletPCMOutput` on `port` (a Pyodide worker's MessagePort)."""
