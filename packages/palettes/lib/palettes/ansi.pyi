# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Use the colors a terminal names with ANSI escape codes."""

from collections.abc import Sequence

from . import Palette as _Palette

ANSI16: tuple[tuple[int, str], ...]

class AnsiPalette(_Palette):
    """The 16 or 256 colors of an ANSI terminal."""

    def __init__(
        self,
        name: str = "ansi",
        color_depth: int = 16,
        swapped: bool = False,
        cached: bool = True,
        length: int = 256,
    ) -> None: ...
    def nearest(
        self, r: int | Sequence[int], g: int | None = None, b: int | None = None
    ) -> int:
        """Return the index of the palette color closest to an RGB color."""
