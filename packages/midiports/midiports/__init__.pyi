# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""MIDI ports for ``adafruit_midi``, over any transport."""

from _typeshed import ReadableBuffer, WriteableBuffer
from types import TracebackType
from typing import Any, NamedTuple

__version__: str

LOOPBACK: str
"""The name of the Windows MIDI loopback port."""

IN: str
OUT: str
INOUT: str
DIRECTIONS: tuple[str, ...]
PORT_FIELDS: tuple[str, ...]

class PortInfo(NamedTuple):
    """One port a desktop transport lists."""

    id: Any
    name: Any
    direction: Any

def ticks_us() -> int:
    """Microseconds now, on the clock every arrival time is stamped with."""

def ticks_diff(end: int, start: int) -> int:
    """``end - start`` in microseconds, across a wrap where the clock wraps."""

class Stamps:
    """Arrival times, one per message, oldest first, in a ring made once."""

    def __init__(self, size: int = 64) -> None: ...
    def push(self, t: int) -> None: ...
    def take(self) -> int | None: ...
    def __len__(self) -> int: ...

class PortIn:
    """An input port. Subclasses implement ``readinto``."""

    def __init__(self, size: int = 64) -> None: ...
    def readinto(self, buf: WriteableBuffer, nbytes: int | None = None) -> int | None:
        """Waiting bytes into ``buf``; how many, or ``None`` when nothing has arrived."""

    def take_timestamp(self) -> int | None:
        """When the next message arrived, or ``None`` when no stamp is waiting."""

    def read(self, nbytes: int | None = None) -> bytes | None:
        """Up to ``nbytes`` waiting bytes, or ``None``. Never blocks."""

    def close(self) -> None: ...
    def deinit(self) -> None: ...
    def __enter__(self) -> "PortIn": ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

class PortOut:
    """An output port. Subclasses implement ``write``."""

    def write(self, buf: ReadableBuffer, nbytes: int | None = None) -> int:
        """Send the first ``nbytes`` of ``buf`` (all of it when ``None``); how many bytes it took."""

    def close(self) -> None: ...
    def deinit(self) -> None: ...
    def __enter__(self) -> "PortOut": ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

def check_direction(name: str) -> str:
    """``name`` unchanged if it's a direction; ``ValueError`` if not."""

def message_length(status: int) -> int:
    """How many data bytes follow ``status``; 0 for realtime and unknowns."""

class WholeMessages(PortIn):
    """Wrap a port whose bytes can arrive split or interleaved so it hands out whole messages."""

    port: Any
    desync: int
    def __init__(self, port: Any, size: int = 32, stamps: int | None = None) -> None: ...
    def any(self) -> int:
        """How many bytes are waiting, without taking them."""
