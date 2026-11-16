# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""A byte FIFO for PCM waiting between a writer and a device, kept in small chunks."""

CHUNK: int

class ByteQueue:
    """FIFO of bytes held in fixed-size chunks. Not thread-safe."""

    limit: int | None
    def __init__(self, limit: int | None = None, chunk: int = ...) -> None: ...
    def __len__(self) -> int: ...
    def __bool__(self) -> bool: ...
    def free(self) -> int:
        """Bytes that can still be written (a large number when unlimited)."""
    def clear(self) -> None: ...
    def write(self, data: bytes | bytearray | memoryview) -> int:
        """Append as much of `data` as fits; return how many bytes were taken."""
    def unread(self, data: bytes | bytearray | memoryview) -> int:
        """Put `data` back at the front, ahead of what is queued."""
    def peek(self, count: int) -> memoryview:
        """A view of up to `count` of the oldest bytes, without consuming them."""
    def consume(self, count: int) -> int:
        """Drop up to `count` of the oldest bytes; return how many were dropped."""
    def copy_into(
        self, buf: bytearray | memoryview, count: int | None = None, skip: int = 0
    ) -> int:
        """Copy up to `count` queued bytes into `buf`, leaving them queued."""
    def head(self, count: int) -> bytes:
        """A copy of up to `count` of the oldest bytes; they stay queued."""
    def tail(self, count: int) -> bytes:
        """A copy of up to `count` of the newest bytes; they stay queued."""
    def push(self, data: bytes | bytearray | memoryview) -> int:
        """Append `data`, dropping the oldest bytes to make room. Needs a `limit`."""
    def readinto(self, buf: bytearray | memoryview, count: int | None = None) -> int:
        """Move up to `count` of the oldest bytes into `buf`."""
    def take(self, count: int) -> bytearray:
        """Remove and return up to `count` of the oldest bytes."""
