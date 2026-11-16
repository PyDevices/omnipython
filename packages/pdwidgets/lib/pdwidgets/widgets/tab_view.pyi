# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Tab bar with per-tab content pages."""

from typing import Sequence

from ..widget import Widget
from .page import Page

class TabView(Widget):
    """Tab bar plus content area with one `Page` per tab."""

    bar_height: int
    tab_bar: Widget
    content: Widget
    def __init__(self, parent: Widget, x: int = 0, y: int = 0, w: int | None = None, h: int | None = None, align: int | None = None, align_to: Widget | None = None, fg: int | None = None, bg: int | None = None, visible: bool = True, value: int = 0, padding: tuple[int, int, int, int] | None = None, tabs: Sequence[str | tuple[str, Page | None] | list[str | Page | None]] | None = None, bar_height: int | None = None) -> None: ...
    def set_index(self, index: int) -> None:
        """Select the tab at `index` and show its page."""
    @property
    def index(self) -> int:
        """Index of the currently selected tab."""
    @index.setter
    def index(self, value: int) -> None: ...
    @property
    def pages(self) -> list[Page]:
        """List of `Page` widgets, one per tab."""
