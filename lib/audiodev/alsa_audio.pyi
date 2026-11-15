# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""ALSA PCM backend for Linux, straight to ``libasound`` with no SDL or pygame."""

from typing import Any

from audiodev import AudioFormat, AudioSession, PCMInput, PCMOutput

STREAM_PLAYBACK: int
STREAM_CAPTURE: int
NONBLOCK: int
ACCESS_RW_INTERLEAVED: int
STATE_PREPARED: int
STATE_RUNNING: int
STATE_XRUN: int
STATE_DRAINING: int
EINTR: int
EAGAIN: int
EPIPE: int
ESTRPIPE: int
WRITE_WAIT_MS: int
DRAIN_WAIT_MS: int

def has_cards() -> bool:
    """True when the kernel has at least one sound card."""
    ...

def devices() -> list[dict[str, Any]]:
    """The sound cards' PCM devices, from ``/proc/asound/pcm``.

    Each dict has ``name`` (what to pass as ``device``, such as ``"plughw:2,0"``),
    ``card`` and ``device`` as ints, ``description`` as a string, and ``playback``
    and ``capture`` as bools. The list is empty where there are no cards.
    """
    ...

class AlsaPCMOutput(PCMOutput):
    device_name: str | None
    latency_us: int
    poll_ms: int
    buffer_frames: int
    period_frames: int
    xruns: int
    """Underruns the card has had since this output opened."""
    def __init__(
        self,
        fmt: AudioFormat,
        *,
        device: str | None = None,
        latency_us: int = 200000,
        prebuffer_ms: int = 50,
        poll_ms: int = 2,
        session: AudioSession | None = None,
    ) -> None: ...

class AlsaPCMInput(PCMInput):
    device_name: str | None
    latency_us: int
    poll_ms: int
    buffer_frames: int
    period_frames: int
    xruns: int
    """Overruns since this input opened: audio the caller didn't read in time."""
    def __init__(
        self,
        fmt: AudioFormat,
        *,
        device: str | None = None,
        latency_us: int = 200000,
        poll_ms: int = 2,
        session: AudioSession | None = None,
    ) -> None: ...

def pcm_out(
    format: AudioFormat | None = None, *, device: str | None = None, latency: str | None = None, poll_ms: int = 2
) -> AlsaPCMOutput:
    """Create an ALSA `PCMOutput`. ``latency`` ``"low"`` is a 40 ms ring buffer, the others 200 ms."""
    ...

def pcm_in(
    format: AudioFormat | None = None, *, device: str | None = None, latency: str | None = None, poll_ms: int = 2
) -> AlsaPCMInput:
    """Create an ALSA `PCMInput`."""
    ...
