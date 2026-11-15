# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""SVG decode on CPython, the same API as MicroPython's built-in `svgio`."""

from typing import BinaryIO

_Buffer = bytes | bytearray | memoryview

class SvgDecoder:
    """Call `open`, then `decode`."""

    def __init__(self) -> None: ...
    @property
    def width(self) -> int: ...
    @property
    def height(self) -> int: ...
    def open(
        self,
        source: _Buffer | str | BinaryIO,
        *,
        width: int | None = None,
        height: int | None = None,
        scale: float | None = None,
    ) -> tuple[int, int]:
        """Read an SVG from bytes, a path or a stream, at one of `width`, `height` or `scale`; return `(width, height)`."""
    def decode(
        self,
        target: bytearray | memoryview | None,
        alpha: bytearray | memoryview | None = None,
        *,
        x: int = 0,
        y: int = 0,
        stride: int | None = None,
    ) -> None:
        """Write RGB565 into `target` and coverage into `alpha`; `target` alone blends over what it holds."""
