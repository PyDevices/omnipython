# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Material Design color palette."""

from . import MappedPalette

COLORS: memoryview
FAMILIES: list[str]
LENGTHS: list[int]

class MDPalette(MappedPalette):
    """Material Design swatch palette."""

    def __init__(
        self,
        name: str = "",
        color_depth: int = 16,
        swapped: bool = False,
        color_map: bytes | bytearray | memoryview = ...,
    ) -> None: ...
