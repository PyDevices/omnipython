# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Portable PCM and tone device contracts for MicroPython and CPython."""

import types
from collections.abc import Callable
from typing import Any, Literal

from typing_extensions import Self

__all__ = (
    "LATENCIES",
    "LOW_LATENCY_QUEUE_MS",
    "AudioFormat",
    "AudioFactory",
    "AudioCapability",
    "AudioLocked",
    "I2SWire",
    "DACWire",
    "PDMWire",
    "AnalogWire",
    "negotiate",
    "AudioSession",
    "ChannelAdapter",
    "adapt_channels",
    "InputChannelAdapter",
    "adapt_input_channels",
    "PaceOutput",
    "pace_output",
    "PCMInput",
    "PCMOutput",
    "ToneOutput",
    "check_latency",
    "queue_bytes",
)

LATENCIES: tuple[str | None, ...]

class AudioLocked(RuntimeError):
    """The platform won't start audio until the user acts, as a browser doesn't until a click."""


def check_latency(latency: Literal["low", "buffered"] | None) -> Literal["low", "buffered"] | None:
    """Validate a latency profile name, returning it unchanged."""

LOW_LATENCY_QUEUE_MS: int

def queue_bytes(
    fmt: AudioFormat,
    latency: Literal["low", "buffered"] | None = None,
    queue_ms: int | float | None = None,
    default: int | None = None,
    minimum: int = 0,
) -> int | None:
    """Bytes of buffering for a latency profile, e.g. `machine.I2S(ibuf=...)`."""

class AudioFormat:
    """Description of raw, interleaved PCM frames."""

    rate: int
    channels: int
    bits: int
    signed: bool
    byteorder: Literal["little", "big"]
    frame_size: int
    def __init__(
        self,
        rate: int,
        channels: int,
        bits: Literal[8, 16, 32],
        signed: bool = True,
        byteorder: Literal["little", "big"] = "little",
    ) -> None: ...
    def __eq__(self, other: object) -> bool: ...

class I2SWire:
    """Physical facts about a board's I2S port, published without opening it."""

    port: int
    sck: int
    ws: int
    sd: int
    mck: int | None
    mck_fs: int
    sd_in: int | None
    def __init__(
        self,
        port: int,
        *,
        sck: int,
        ws: int,
        sd: int,
        mck: int | None = None,
        mck_fs: int = 256,
        sd_in: int | None = None,
    ) -> None: ...

class DACWire:
    """A board's DAC output pins, published without opening them."""

    left: Any
    right: Any
    def __init__(self, left: Any, right: Any = None) -> None: ...

class PDMWire:
    """A board's PDM microphone pins, published without opening them."""

    clock: Any
    data: Any
    def __init__(self, clock: Any, data: Any) -> None: ...

class AnalogWire:
    """An analog microphone input, published without opening it."""

    pin: Any
    def __init__(self, pin: Any) -> None: ...

class AudioCapability:
    """What a board's audio role can actually do. Boards declare; `negotiate` decides."""

    kind: Literal["pcm", "tone"]
    default: AudioFormat | None
    rates: tuple[int, ...] | None
    channels: tuple[int, ...]
    native_channels: int
    bits: tuple[int, ...]
    signed: bool
    byteorder: Literal["little", "big"]
    wire: I2SWire | DACWire | PDMWire | AnalogWire | None
    def __init__(
        self,
        default: AudioFormat | None,
        *,
        kind: Literal["pcm", "tone"] = "pcm",
        rates: tuple[int, ...] | list[int] | None = None,
        channels: tuple[int, ...] | list[int] | None = None,
        native_channels: int | None = None,
        bits: tuple[int, ...] | list[int] = (16,),
        signed: bool = True,
        byteorder: Literal["little", "big"] = "little",
        wire: I2SWire | DACWire | PDMWire | AnalogWire | None = None,
    ) -> None: ...

def negotiate(
    capability: AudioCapability, requested: AudioFormat | None = None
) -> tuple[AudioFormat, AudioFormat] | tuple[None, None]:
    """Resolve a requested format against a board capability.

    Returns `(wire_format, source_format)`.
    """

class AudioFactory:
    """A board's `audio_out`/`pcm_out` callable, with its capability attached."""

    capability: AudioCapability
    def __init__(self, call: Callable[..., Any], capability: AudioCapability) -> None: ...
    def __call__(self, format: AudioFormat | None = None, **kwargs: Any) -> Any: ...

class AudioSession:
    """Coordinate devices which share a codec or peripheral."""

    codec_factory: Callable[[], Any] | None
    duplex: bool
    codec: Any
    def __init__(
        self, codec_factory: Callable[[], Any] | None = None, duplex: bool = False
    ) -> None: ...
    def get_codec(self) -> Any:
        """Return the shared codec, constructing it on first access."""
    def acquire(self, owner: object, direction: Literal["in", "out"]) -> Any: ...
    def release(self, owner: object) -> None: ...

class _Device:
    direction: Literal["in", "out"] | None
    session: AudioSession | None
    is_open: bool
    def __init__(self, *, session: AudioSession | None = None) -> None: ...
    @property
    def codec(self) -> Any: ...
    @codec.setter
    def codec(self, value: Any) -> None: ...
    def open(self) -> Self: ...
    def close(self) -> None: ...
    def deinit(self) -> None: ...
    def service(self) -> int | None: ...
    def queued_size(self) -> int: ...
    @property
    def prebuffer_bytes(self) -> int: ...
    def is_active(self) -> bool: ...
    def clear(self) -> None: ...
    def __enter__(self) -> Self: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> None: ...

class PCMOutput(_Device):
    """Raw PCM playback with normalized volume and async support."""

    kind: str
    direction: Literal["out"]
    format: AudioFormat
    codec: Any
    amplifier: Any
    capabilities: frozenset[str]
    def __init__(
        self,
        format: AudioFormat,
        *,
        session: AudioSession | None = None,
        codec: Any = None,
        amplifier: Any = None,
        set_hardware_volume: Callable[[int], Any] | None = None,
        set_hardware_mute: Callable[[bool], Any] | None = None,
        power: Callable[[bool], Any] | None = None,
    ) -> None: ...
    @property
    def volume(self) -> int: ...
    @property
    def muted(self) -> bool: ...
    def open(self) -> Self: ...
    def hardware_live(self, value: bool = True) -> None:
        """Say whether this transport's codec is powered by someone else."""
    def set_volume(self, percent: int | float) -> int: ...
    def mute(self, value: bool = True) -> bool: ...
    def write(self, buf: bytes | bytearray | memoryview) -> int: ...
    def try_write(self, buf: bytes | bytearray | memoryview) -> int:
        """Push as many bytes as the backend will take without blocking."""
    def drain(self) -> Any: ...
    async def awrite(self, buf: bytes | bytearray | memoryview) -> int: ...
    async def adrain(self) -> Any: ...
    def close(self) -> None: ...

class PCMInput(_Device):
    """Raw PCM capture with normalized gain and async support."""

    kind: str
    direction: Literal["in"]
    format: AudioFormat
    codec: Any
    capabilities: frozenset[str]
    def __init__(
        self,
        format: AudioFormat,
        *,
        session: AudioSession | None = None,
        codec: Any = None,
        set_hardware_gain: Callable[[int], Any] | None = None,
        set_hardware_mute: Callable[[bool], Any] | None = None,
        power: Callable[[bool], Any] | None = None,
    ) -> None: ...
    @property
    def gain(self) -> int: ...
    @property
    def muted(self) -> bool: ...
    def open(self) -> Self: ...
    def set_gain(self, percent: int | float) -> int: ...
    def mute(self, value: bool = True) -> bool: ...
    def readinto(self, buf: bytearray | memoryview) -> int: ...
    async def areadinto(self, buf: bytearray | memoryview) -> int: ...
    def close(self) -> None: ...

class ChannelAdapter(PCMOutput):
    """Accept `source_format` on `write()`; emit the inner device's format."""

    remix: Callable[..., Any]
    codec: Any
    def __init__(
        self,
        inner: PCMOutput,
        source_format: AudioFormat,
        remix: Callable[..., Any] | None = None,
    ) -> None: ...
    @property
    def i2s(self) -> Any: ...
    @property
    def volume(self) -> int: ...
    @property
    def muted(self) -> bool: ...
    def set_volume(self, percent: int | float) -> int: ...
    def mute(self, value: bool = True) -> bool: ...
    is_open: bool
    def open(self) -> Self: ...
    def close(self) -> None: ...
    def queued_size(self) -> int: ...
    @property
    def prebuffer_bytes(self) -> int: ...
    def is_active(self) -> bool: ...
    def clear(self) -> None: ...
    def service(self) -> None: ...
    def space(self) -> int: ...

def adapt_channels(
    pcm: PCMOutput,
    source_format: AudioFormat,
    remix: Callable[..., Any] | None = None,
) -> PCMOutput:
    """Return `pcm` unchanged, or a wrapper that converts `source_format` to it."""

class InputChannelAdapter(PCMInput):
    """Hand `readinto()` the channel count asked for; read the inner device's."""

    remix: Callable[..., Any]
    codec: Any
    is_open: bool
    def __init__(
        self,
        inner: PCMInput,
        target_format: AudioFormat,
        remix: Callable[..., Any] | None = None,
    ) -> None: ...
    @property
    def gain(self) -> int: ...
    @property
    def muted(self) -> bool: ...
    def set_gain(self, percent: int | float) -> int: ...
    def mute(self, value: bool = True) -> bool: ...
    def open(self) -> Self: ...
    def close(self) -> None: ...
    def readinto(self, buf: bytearray | memoryview) -> int: ...
    async def areadinto(self, buf: bytearray | memoryview) -> int: ...

def adapt_input_channels(
    pcm: PCMInput,
    target_format: AudioFormat,
    remix: Callable[..., Any] | None = None,
) -> PCMInput:
    """Return `pcm` unchanged, or a wrapper whose `readinto()` gives `target_format`'s channels."""

class PaceOutput(PCMOutput):
    """Take `write()` without blocking `machine.I2S` until DMA is full."""

    lost_bytes: int
    codec: Any
    def __init__(self, inner: PCMOutput, queue_ms: int = 80) -> None: ...
    @property
    def i2s(self) -> Any: ...
    @property
    def volume(self) -> int: ...
    @property
    def muted(self) -> bool: ...
    def set_volume(self, percent: int | float) -> int: ...
    def mute(self, value: bool = True) -> bool: ...
    is_open: bool
    def open(self) -> Self: ...
    def close(self) -> None: ...
    def queued_size(self) -> int: ...
    @property
    def prebuffer_bytes(self) -> int: ...
    def is_active(self) -> bool: ...
    def clear(self) -> None: ...
    def service(self) -> None: ...
    def space(self) -> int: ...
    def try_write(self, buf: bytes | bytearray | memoryview) -> int: ...

def pace_output(pcm: PCMOutput, queue_ms: int = 80) -> PCMOutput:
    """Return `pcm` wrapped so `write()` will not block a full I2S DMA."""

class ToneOutput(_Device):
    """Frequency/duty output for PWM speakers and buzzers."""

    kind: str
    direction: Literal["out"]
    capabilities: frozenset[str]
    def __init__(
        self,
        *,
        session: AudioSession | None = None,
        power: Callable[[bool], Any] | None = None,
    ) -> None: ...
    def open(self) -> Self: ...
    @property
    def volume(self) -> int: ...
    @property
    def muted(self) -> bool: ...
    def set_volume(self, percent: int | float) -> int: ...
    def mute(self, value: bool = True) -> bool: ...
    def play(self, frequency: int | float, *, volume: int | float | None = None) -> None: ...
    def stop(self) -> None: ...
    async def aplay(self, frequency: int | float, duration_ms: int) -> None: ...
    def close(self) -> None: ...
