# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""MCU I2S adapter: wrap `machine.I2S` as `audiodev.PCMOutput` / `PCMInput`."""

from typing import Any

from audiodev import AudioFormat, I2SWire, PCMInput as PCMInput, PCMOutput as PCMOutput

class I2SPCMOutput(PCMOutput):
    """Playback through `machine.I2S` (or any object with `write`)."""

    wire: I2SWire | None
    audio_power: Any
    def __init__(
        self,
        i2s: Any,
        format: AudioFormat,
        *,
        wire: I2SWire | None = None,
        audio_power: Any = None,
        **kwargs: Any,
    ) -> None: ...
    @property
    def i2s(self) -> Any: ...
    def queued_size(self) -> int:
        """Estimate the bytes still queued for the DAC."""
    def service(self) -> None: ...

class I2SPCMInput(PCMInput):
    """Capture through `machine.I2S` (or any object with `readinto`)."""

    def __init__(self, i2s: Any, format: AudioFormat, **kwargs: Any) -> None: ...
    @property
    def i2s(self) -> Any: ...

def pcm_out(i2s: Any, format: AudioFormat, **kwargs: Any) -> I2SPCMOutput:
    """Build an `I2SPCMOutput` around `i2s` (instance or factory)."""

def pcm_in(i2s: Any, format: AudioFormat, **kwargs: Any) -> I2SPCMInput:
    """Build an `I2SPCMInput` around `i2s` (instance or factory)."""
