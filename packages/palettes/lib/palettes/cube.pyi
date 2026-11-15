# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""RGB color-cube palettes."""

from . import Palette as _Palette

class CubePalette(_Palette):
    """Evenly spaced RGB cube palette; `size` is 2, 3, 4 or 5."""

    def __init__(
        self,
        name: str = "",
        color_depth: int = 16,
        swapped: bool = False,
        cached: bool = True,
        size: int = 5,
    ) -> None: ...
