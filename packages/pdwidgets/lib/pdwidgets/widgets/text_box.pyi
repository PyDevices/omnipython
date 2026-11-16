# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Read-only formatted text display."""

from typing import Any

from ..widget import Widget

class TextBox(Widget):
    """Read-only formatted text display."""

    format: str
    text_height: int
    scale: int
    def __init__(self, parent: Widget, x: int = 0, y: int = 0, w: int | None = None, h: int | None = None, align: int | None = None, align_to: Widget | None = None, fg: int | None = None, bg: int | None = None, visible: bool = True, value: Any = None, padding: tuple[int, int, int, int] | None = None, format: str = '', text_height: int = 16, scale: int = 1, inverted: bool = False, font_data: str | bytes | memoryview | None = None) -> None: ...
    def draw(self, _: Any = None) -> None:
        """Draw the text, formatted with `format`."""
    @property
    def char_width(self) -> int:
        """Rendered character width in pixels."""
    @property
    def char_height(self) -> int:
        """Rendered character height in pixels."""
