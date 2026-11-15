# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Scrollable list container."""

from typing import Any

from ..widget import Widget
from .scroll_bar import ScrollBar

class ListView(Widget):
    """Vertically scrollable list container."""

    clip_content: bool
    scrollbar: ScrollBar
    def __init__(self, parent: Widget, x: int = 0, y: int = 0, w: int | None = None, h: int | None = None, align: int | None = None, align_to: Widget | None = None, fg: int | None = None, bg: int | None = None, visible: bool = True, padding: tuple[int, int, int, int] | None = None) -> None: ...
    def add_child(self, child: Widget) -> None:
        """Add a child widget as the last row."""
    def remove_child(self, child: Widget) -> None:
        """Remove a child widget."""
    def reassign_positions(self) -> None:
        """Stack all children one under another after one is added or removed."""
    def config_scrollbar(self) -> None:
        """Configure the scrollbar based on the number of children."""
    def scroll(self, sender: Any) -> None:
        """Scroll to the position of the scrollbar slider."""
    def scroll_up(self) -> None:
        """Scroll the list view up by one item."""
    def scroll_down(self) -> None:
        """Scroll the list view down by one item."""
    def changed(self) -> None:
        """Update the visible rows and scrollbar when the value changes."""
