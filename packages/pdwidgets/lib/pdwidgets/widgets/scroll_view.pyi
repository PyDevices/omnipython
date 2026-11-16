# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""ScrollView: generic scroll container with clip, drag and wheel."""

from typing import Any

from ..widget import Widget
from .scroll_bar import ScrollBar

class ScrollView(Widget):
    """Clipped scrollable viewport with drag, wheel, and scrollbar."""

    clip_content: bool
    scrollbar: ScrollBar
    def __init__(self, parent: Widget, x: int = 0, y: int = 0, w: int | None = None, h: int | None = None, align: int | None = None, align_to: Widget | None = None, fg: int | None = None, bg: int | None = None, visible: bool = True, padding: tuple[int, int, int, int] | None = None, content_h: int | None = None) -> None: ...
    @property
    def scroll_y(self) -> int:
        """Current vertical scroll offset in pixels."""
    @scroll_y.setter
    def scroll_y(self, y: int | float) -> None: ...
    def set_content_height(self, h: int | float) -> None:
        """Update the total scrollable content height in pixels."""
    def add_child(self, child: Widget) -> None:
        """Add a child and expand the content height if needed."""
    def draw(self, area: Any = None) -> None:
        """Draw the viewport background."""
