# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""TrueType glyphs on CPython, the same API as MicroPython's built-in `ttfio`."""

_Char = str | int
_Buffer = bytes | bytearray | memoryview

class Font:
    """A TrueType font, drawn unhinted as the C module draws it."""

    def __init__(self, data: _Buffer, scratch: int = 8192) -> None: ...
    @property
    def units_per_em(self) -> int: ...
    def has(self, ch: _Char) -> bool: ...
    def metrics(self, px: float) -> tuple[int, int, int]:
        """Ascent, descent (negative) and line gap at an em of `px` pixels."""
    def glyph(self, ch: _Char, px: float) -> tuple[int, int, int, int, int] | None:
        """`(w, h, x, y, advance)`, or None if the font has no glyph for `ch`."""
    def render(
        self, ch: _Char, px: float, buf: bytearray | memoryview | None = None, *, stride: int = 0
    ) -> bytearray | memoryview:
        """Draw `ch` as 8-bit coverage into `buf`, or into a new bytearray."""
