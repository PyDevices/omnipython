# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Color palette toolkit for PyDevices."""

from collections.abc import Iterator, Sequence
from typing import Any

__all__ = ["WIN16", "get_palette", "Palette", "MappedPalette"]

WIN16: tuple[tuple[int, str], ...]

def get_palette(name: str = "default", **kwargs: Any) -> Palette:
    """Construct a palette by name: `default`, `wheel`, `cube`, `material_design` or `ansi`."""

class Palette:
    """Indexed color palette with optional named color attributes."""

    def __init__(
        self, name: str = "", color_depth: int = 16, swapped: bool = False, cached: bool = False
    ) -> None: ...
    @property
    def name(self) -> str: ...
    def __iter__(self) -> Iterator[int]: ...
    def __len__(self) -> int: ...
    def __getitem__(self, index: int) -> int: ...
    def color565(
        self, r: int | Sequence[int], g: int | None = None, b: int | None = None
    ) -> int: ...
    def color332(
        self, r: int | Sequence[int], g: int | None = None, b: int | None = None
    ) -> int: ...
    def color_rgb(self, color: int | bytes | bytearray | Sequence[int]) -> tuple[int, int, int]: ...
    def color_name(self, index: int) -> str: ...
    def rgb_name(
        self, r: int | Sequence[int], g: int | None = None, b: int | None = None
    ) -> str: ...
    def luminance(self, index: int) -> float: ...
    def brightness(self, index: int) -> float: ...

class MappedPalette(Palette):
    """Palette backed by a flat RGB byte map."""

    def __init__(
        self,
        name: str,
        color_depth: int,
        swapped: bool,
        color_map: bytes | bytearray | memoryview,
    ) -> None: ...
