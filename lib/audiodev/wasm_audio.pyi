# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Web Audio PCM backend for the direct MicroPython WebAssembly runtime."""

from typing import Any, Literal

from audiodev import AudioFormat as AudioFormat, PCMInput as PCMInput, PCMOutput as PCMOutput, check_latency as check_latency

DEFAULT_FORMAT: AudioFormat

class WasmPCMOutput(PCMOutput):
    latency: Literal["low", "buffered"] | None
    def __init__(
        self,
        format: AudioFormat = ...,
        *,
        latency: Literal["low", "buffered"] | None = None,
        **kwargs: Any,
    ) -> None: ...
    def queued_size(self) -> int: ...
    def is_active(self) -> bool: ...
    def clear(self) -> None: ...

class WasmPCMInput(PCMInput):
    latency: Literal["low", "buffered"] | None
    def __init__(
        self,
        format: AudioFormat = ...,
        *,
        latency: Literal["low", "buffered"] | None = None,
        **kwargs: Any,
    ) -> None: ...
    def queued_size(self) -> int: ...
    def is_active(self) -> bool: ...
    def clear(self) -> None: ...

def pcm_out(format: AudioFormat | None = None, **kwargs: Any) -> WasmPCMOutput: ...
def pcm_in(format: AudioFormat | None = None, **kwargs: Any) -> WasmPCMInput: ...
