# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""JPEG decode and encode on CPython, the same API as MicroPython's built-in `jpegio`."""

from collections.abc import Callable
from typing import BinaryIO

RGB565: int
GRAY: int

_Buffer = bytes | bytearray | memoryview

class JpegDecoder:
    """Call `open`, then `decode`."""

    def __init__(self, *, hardware: bool = False) -> None: ...
    @property
    def width(self) -> int: ...
    @property
    def height(self) -> int: ...
    def open(self, source: _Buffer | str | BinaryIO) -> tuple[int, int]:
        """Read a JPEG from bytes, a path or a stream; return `(width, height)`."""
    def decode(
        self,
        target: bytearray | memoryview | Callable[[int, int, int, int, memoryview], None],
        scale: int = 0,
        x: int = 0,
        y: int = 0,
        *,
        stride: int | None = None,
    ) -> None:
        """Write native-order RGB565 into `target`, a buffer or a callable taking `(x, y, w, h, block)`."""

class JpegEncoder:
    """Encode RGB565 or grey pixels as JPEG."""

    quality: int
    subsampling: int
    hardware: bool
    def __init__(
        self, quality: int = 80, subsampling: int = 420, *, hardware: bool | None = None, exact: bool = True
    ) -> None: ...
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
