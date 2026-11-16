# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""PNG encode and decode on CPython, the same API as MicroPython's built-in `pngio`."""

from typing import BinaryIO

RGB565: int
GS8: int
RGB888: int

_Buffer = bytes | bytearray | memoryview

class PngEncoder:
    """Encode RGB565, 8-bit grey or RGB888 pixels as PNG."""

    level: int
    def __init__(self, level: int = 1) -> None: ...
    def encode(
        self,
        buffer: _Buffer,
        width: int,
        height: int,
        *,
        format: int = 0,
        stride: int | None = None,
        swap: bool = False,
    ) -> bytes: ...

class PngDecoder:
    """Call `open`, then `decode`."""

    def __init__(self) -> None: ...
    @property
    def width(self) -> int: ...
    @property
    def height(self) -> int: ...
    def open(self, source: _Buffer | str | BinaryIO) -> tuple[int, int]:
        """Read a PNG from bytes, a path or a stream; return `(width, height)`."""
    def decode(
        self, target: bytearray | memoryview, x: int = 0, y: int = 0, *, stride: int | None = None
    ) -> None:
        """Write native-order RGB565 into `target`."""
