# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""The audio pump, used without being asked."""

from collections.abc import Callable
from typing import Any, Literal, Protocol

from typing_extensions import Self

from audiodev import (
    AnalogWire,
    AudioFormat,
    DACWire,
    I2SWire,
    PCMInput as PCMInput,
    PCMOutput as PCMOutput,
    PDMWire,
)

GET_BUFFER_DONE: int
GET_BUFFER_MORE_DATA: int

class _AudioSample(Protocol):
    """A CircuitPython-shaped audiosample."""

    @property
    def sample_rate(self) -> int: ...
    @property
    def channel_count(self) -> int: ...
    @property
    def bits_per_sample(self) -> int: ...

class StartFailed(RuntimeError):
    """The pump did not take a graph this time."""

FILE_BACKED: tuple[str, ...]

def module() -> Any:
    """The `audiopump` C module, or `None`."""
def driver() -> Any:
    """The `_audioif` C module (the pump's platform driver), or `None`."""
def busio() -> Any:
    """The `audiobusio` C module, or `None`."""
def dac() -> Any:
    """The `audioio` C module, or `None`."""
def driver_name() -> str:
    """Which platform driver the engine bound: esp32, pthread, win32, none."""
def available() -> bool:
    """True when this firmware carries a usable pump."""
def on_board() -> bool:
    """True when the pump owns a peripheral, rather than a ring."""
def duplex() -> bool:
    """True when this firmware can record while it plays, on one I2S port."""
def clock_running() -> bool:
    """True while the pump's driver has an I2S channel open on this board."""
def threaded() -> bool:
    """True where `spawn()` puts the pull loop on a thread of its own."""
def backpressure() -> bool:
    """True where a full output ring makes the pump wait instead of dropping."""
def now() -> int:
    """Frames the pump has pulled since it started, or 0 without one."""
def events(capacity: int = 96) -> Any:
    """The pump's event queue, or `None` on a build with no pump."""
def ring_bytes(frame_size: int, chunk_bytes: int = 0, max_block: int = 0) -> int:
    """How deep the desktop output ring is, for `frame_size`-byte frames."""
def block_size(sample: _AudioSample) -> int:
    """Bytes in one pull of `sample`, or 0 if it cannot be asked."""
def rearranging() -> bool:
    """True while something is rearranging the pump. A tick must not pull."""
def reentered() -> int:
    """Ticks turned away because something was rearranging the pump."""
def health() -> dict[str, Any] | None:
    """The process pump's `Pump.health`, or `None` when there is no pump."""
def retarget(mod: Any, sample: _AudioSample, loop: bool = False) -> None:
    """Swap a live pump's tail, carrying the output's loop flag with it."""
def pumpable(sample: _AudioSample) -> bool:
    """True when the pump can pull `sample` itself."""

class Prefetch:
    """A file-backed sample, pulled on the interpreter thread into a ring."""

    sample: _AudioSample
    loop: bool
    done: bool
    wrote: int
    block: int
    ring: Any
    def __init__(
        self,
        sample: _AudioSample,
        *,
        frames: int = 256,
        capacity: int = 6,
        loop: bool = False,
        min_bytes: int = 0,
    ) -> None: ...
    def service(self, limit: int | None = None) -> int:
        """Top the ring up. Returns bytes written this call."""
    def fed(self) -> bool:
        """True when every byte of the file is in the ring."""
    def finished(self) -> bool:
        """True when the file has been read out and the ring has drained."""
    def deinit(self) -> None: ...

class _Driver:
    needs_service: bool
    def spawn(self, sample: _AudioSample, status: bytearray, loop: bool = False) -> None: ...
    def retarget(self, sample: _AudioSample, loop: bool = False) -> None: ...
    def halt(self) -> None: ...
    def status(self) -> Any: ...
    def produce(self, into: bytearray | memoryview) -> int: ...
    def opened(self) -> bool: ...
    def close(self) -> None: ...

class RingDriver(_Driver):
    """Desktop: the pump fills a RAM ring, the interpreter drains it."""

    def __init__(self, frame_size: int, *, chunk_bytes: int = 0, max_block: int = 0) -> None: ...
    def ahead_ms(self, rate: int = 48000) -> float:
        """How much audio the ring holds when full, in milliseconds."""
    def spawn(self, sample: _AudioSample, status: bytearray, loop: bool = False) -> None: ...
    def dropped(self) -> int:
        """Blocks the ring had no room for."""
    def waited(self) -> tuple[int, int]:
        """`(times, microseconds)` the pump waited for this driver to drain."""
    def produce(self, into: bytearray | memoryview) -> int: ...
    def rest(self) -> None:
        """Stop the pump running ahead until the next `produce()`."""
    def close(self) -> None: ...

class ServiceDriver(RingDriver):
    """WebAssembly and CPython: there is no thread, so this tick is the pump."""

    def __init__(
        self, frame_size: int, *, chunk_bytes: int = 0, max_block: int = 0, ahead_ms: int = 0
    ) -> None: ...
    def spawn(self, sample: _AudioSample, status: bytearray, loop: bool = False) -> None: ...
    def produce(self, into: bytearray | memoryview) -> int: ...
    def rest(self) -> None: ...

class BusioDriver(_Driver):
    """esp32: the graph goes to `audiobusio.I2SOut`, and it owns the bus."""

    needs_service: bool
    wire: I2SWire | DACWire
    fmt: AudioFormat
    transport: Any
    volume: int
    out: Any
    def __init__(
        self,
        wire: I2SWire | DACWire,
        fmt: AudioFormat,
        *,
        power: Callable[[bool], Any] | None = None,
        volume: int | None = None,
        transport: Any = None,
    ) -> None: ...
    def open(self) -> None: ...
    def opened(self) -> bool: ...
    def spawn(self, sample: _AudioSample, status: bytearray, loop: bool = False) -> None: ...
    def retarget(self, sample: _AudioSample, loop: bool = False) -> None: ...
    def halt(self) -> None: ...
    def playing(self) -> bool: ...
    def starved(self) -> int:
        """Blocks the DMA could not be given in time."""
    def status(self) -> Any: ...
    def close(self) -> None: ...

class PumpPCMInput(PCMInput):
    """Capture from the RX half of the pump's own I2S channel."""

    wire: I2SWire | PDMWire | AnalogWire
    ring_bytes: int
    timeout_ms: int
    def __init__(
        self,
        format: AudioFormat,
        *,
        wire: I2SWire | PDMWire | AnalogWire,
        ring_bytes: int = 20000,
        take: Literal["left", "right", "mix"] = "mix",
        timeout_ms: int = 1000,
        before_open: Callable[[], Any] | None = None,
        **kwargs: Any,
    ) -> None: ...
    def open(self) -> Self: ...
    def stats(self) -> dict[str, int]:
        """`captured` and `dropped` frames, and `waiting` bytes."""

def pcm_input(format: AudioFormat, **kwargs: Any) -> PumpPCMInput:
    """Build a `PumpPCMInput`."""

class PumpOutput:
    """A push stream on the pump, over a ring."""

    format: AudioFormat
    ring: Any
    def __init__(self, fmt: AudioFormat, *, frames: int = 256, capacity: int = 6) -> None: ...
    def write(self, buf: bytes | bytearray | memoryview) -> int: ...
    def space(self) -> int: ...
    def level(self) -> int: ...
    def drain(self) -> None: ...
    def deinit(self) -> None: ...

def attach_stream(
    fmt: AudioFormat, *, driver: _Driver | None = None, frames: int = 256, capacity: int = 6
) -> PumpOutput:
    """Put a push stream on the pump beside whatever else is sounding."""

class PumpPCMOutput(PCMOutput):
    """A `PCMOutput` that writes into the pump, for a board whose pump owns the output."""

    wire: I2SWire | DACWire
    buffer_ms: int | None
    audio_power: Callable[[bool], Any] | None
    def __init__(
        self,
        format: AudioFormat,
        *,
        wire: I2SWire | DACWire,
        audio_power: Callable[[bool], Any] | None = None,
        frames: int = 256,
        capacity: int = 6,
        buffer_ms: int | None = None,
    ) -> None: ...
    def space(self) -> int: ...
    def queued_size(self) -> int: ...
    def is_active(self) -> bool: ...

class _Client:
    owner: object
    sample: _AudioSample
    paused: bool
    loop: bool
    def __init__(self, owner: object, sample: _AudioSample, loop: bool = False) -> None: ...

class Pump:
    """The one pump, and who is sounding through it."""

    def __init__(self) -> None: ...
    def events(self, capacity: int = 96) -> Any:
        """The pump's event queue, or `None` on a build without a pump."""
    def clients(self) -> int: ...
    def play(
        self,
        owner: object,
        sample: _AudioSample,
        driver: _Driver | None = None,
        loop: bool = False,
        raises: bool = False,
    ) -> bool:
        """Put `owner`'s `sample` on the pump. Returns `True` when it sounds."""
    def stop(self, owner: object) -> None: ...
    def pause(self, owner: object) -> None: ...
    def resume(self, owner: object) -> None: ...
    def paused(self) -> bool: ...
    def produce(self, into: bytearray | memoryview) -> int: ...
    def rest(self) -> None: ...
    def status(self) -> bytearray:
        """The status block the loop writes."""
    def health(self) -> dict[str, Any]:
        """One dict an app can put on a screen. Nothing here raises."""
    def died(self) -> str | None:
        """The reason the pump stopped by itself, as a sentence, or `None`."""
    def fault(self) -> str | None:
        """The last reason the pump stopped or refused a graph, or `None`."""
    def refusal(self) -> BaseException | None:
        """The exception behind `fault`, or `None`."""
    def blocked(self) -> bool:
        """True while the pump will refuse every `play`."""
    def clear_fault(self) -> str | None:
        """Forget the last fault and let the next `play` try again."""
    def note_fault(self, why: str, blocking: bool = True) -> None:
        """Record a refusal somebody else caught."""
    def shutdown(self) -> None: ...

def owner() -> Pump:
    """The process's one `Pump`."""
def forget() -> None:
    """Drop the pump and everything on it."""
