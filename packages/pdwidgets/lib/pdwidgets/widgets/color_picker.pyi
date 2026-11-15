# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""ColorPicker — compact RGB565 hue + SV picker."""

from typing import Any

from ..widget import Widget

class ColorPicker(Widget):
    """RGB565 color picker with hue strip and saturation/value region."""

    def __init__(self, parent: Widget, x: int = 0, y: int = 0, w: int | None = None, h: int | None = None, align: int | None = None, align_to: Widget | None = None, fg: int | None = None, bg: int | None = None, visible: bool = True, value: int | None = None, padding: tuple[int, int, int, int] | None = None) -> None: ...
    def draw(self, _: Any = None) -> None:
        """Draw the hue strip and saturation/value region."""
