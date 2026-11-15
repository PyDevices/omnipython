# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Text label widget."""

from typing import Any, Protocol, Sequence

from ..widget import Widget

class _ProportionalFont(Protocol):
    """A proportional bitmap font module from the font converter."""

    HEIGHT: int
    MAX_WIDTH: int
    MAP: str
    OFFSET_WIDTH: int
    OFFSETS: Sequence[int]
    WIDTHS: Sequence[int]
    BITMAPS: Sequence[int]

class Label(Widget):
    """Text display using romfont or an optional proportional font."""

    text_height: int
    scale: int
    def __init__(self, parent: Widget, x: int = 0, y: int = 0, w: int | None = None, h: int | None = None, align: int | None = None, align_to: Widget | None = None, fg: int | None = None, bg: int | None = None, visible: bool = True, value: str | None = None, padding: tuple[int, int, int, int] | None = None, text_height: int = 16, scale: int = 1, inverted: bool = False, font_data: str | bytes | memoryview | None = None, font: _ProportionalFont | None = None) -> None: ...
    def draw(self, _: Any = None) -> None:
        """Draw the label's text, filling the background first when `bg` is set."""
    def text_width(self, text: str | None = None) -> int:
        """Return the pixel width of `text` (default `value`) without drawing."""
    @property
    def char_width(self) -> int:
        """Rendered character width in pixels."""
    @property
    def char_height(self) -> int:
        """Rendered character height in pixels."""
