# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""HSV and RGB color-wheel palettes."""

from . import Palette as _Palette

class WheelPalette(_Palette):
    """Color wheel or HSV ramp palette."""

    def __init__(
        self,
        name: str = "",
        color_depth: int = 16,
        swapped: bool = False,
        cached: bool = True,
        length: int = 256,
        saturation: float | None = 1.0,
        value: float | None = None,
    ) -> None: ...
