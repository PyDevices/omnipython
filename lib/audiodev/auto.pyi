# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Optional host backend selection. Backends never import this module."""

from typing import Any, Literal

from audiodev import AudioFormat, PCMInput, PCMOutput
from audiodev.sample_out import AudioOut

def host_kind() -> Literal["wasm", "jupyter", "desktop"]: ...
def select_backend() -> str:
    """Return the name of the first usable output backend."""

def pcm_out(format: AudioFormat | None = None, **kwargs: Any) -> PCMOutput:
    """Construct a raw `PCMOutput` via `select_backend`."""

def pcm_in(format: AudioFormat | None = None, **kwargs: Any) -> PCMInput:
    """Construct a raw `PCMInput` via `select_backend`."""

def audio_out(format: AudioFormat | None = None, **kwargs: Any) -> AudioOut:
    """Construct an `AudioOut` sample player."""
