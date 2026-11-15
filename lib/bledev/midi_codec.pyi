# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""The BLE-MIDI packet codec: MIDI 1.0 messages in and out of GATT packets."""
from collections.abc import Iterable

TIMESTAMP_MASK: int

def data_length(status: int) -> int | None:
    """How many data bytes follow `status`; `None` for SysEx and stray bytes."""
def is_realtime(message: bytes | bytearray | memoryview) -> bool: ...

class Splitter:
    """A MIDI 1.0 byte stream in, complete messages out, SysEx included."""

    desync: int
    def __init__(self) -> None: ...
    def feed(self, data: Iterable[int]) -> list[bytes]: ...

class Decoder:
    """BLE-MIDI packets in, `(timestamp, message)` pairs out."""

    errors: int
    def __init__(self) -> None: ...
    def reset(self) -> None:
        """Forget running status and any SysEx in progress (a new link)."""
    def decode(self, packet: bytes | bytearray | memoryview) -> list[tuple[int, bytes]]: ...

class Encoder:
    """`(timestamp, message)` pairs in, BLE-MIDI packets out."""

    running_status: bool
    def __init__(self, running_status: bool = True) -> None: ...
    def put(self, timestamp: int, message: bytes | bytearray | memoryview) -> None: ...
    def pending(self) -> bool: ...
    def packet(self, size: int) -> bytes | None: ...

def encode(messages: Iterable[tuple[int, bytes | bytearray | memoryview]], size: int, running_status: bool = True) -> list[bytes]:
    """Every packet for `messages`, a list of `(timestamp, message)`."""
def decode(packets: Iterable[bytes | bytearray | memoryview]) -> list[tuple[int, bytes]]:
    """Every `(timestamp, message)` in `packets`, with a fresh decoder."""
