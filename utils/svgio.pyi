# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""SVG decode on CPython, the same API as MicroPython's built-in `svgio`."""

from typing import BinaryIO

_Buffer = bytes | bytearray | memoryview

def expand(drawing: _Buffer) -> bytes:
    """Give the SVG text a drawing in the firmware module's compact form stands for."""

class Buffer(bytearray):
    """Bytes to draw pictures into; on a board, from outside MicroPython's heap."""

    def __init__(self, size: int) -> None: ...
    def close(self) -> None:
        """Let the bytes go, unless a memoryview still shows them."""

class SvgDecoder:
    """Call `open`, then `decode`."""

    def __init__(self, *, memory: int | None = None) -> None:
        """Make a decoder. `memory` is checked and kept: resvg's working memory is its own."""
    @property
    def memory(self) -> int:
        """The bytes of working memory it was made with, or 0."""
    @property
    def memory_peak(self) -> int:
        """Always 0 here."""
    def close(self) -> None:
        """Let go of the SVG."""
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
        rows: tuple[int, int] | None = None,
        colors: dict[int, int] | None = None,
    ) -> None:
        """Write RGB565 into `target` and coverage into `alpha`; `target` alone blends over what it holds.

        `rows=(first, end)` draws only those rows of the image, where they sit in the whole picture.
        `colors={0xRRGGBB: 0xRRGGBB}` draws it with those colours swapped, where the SVG writes them as hex.
        """
