# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Page stack navigator."""

from typing import Any

from ..widget import Widget
from .page import Page

class Navigator(Widget):
    """Page stack with push, pop, and replace navigation."""

    def __init__(self, parent: Widget, x: int = 0, y: int = 0, w: int | None = None, h: int | None = None, align: int | None = None, align_to: Widget | None = None, fg: int | None = None, bg: int | None = None, visible: bool = True, value: Any = None, padding: tuple[int, int, int, int] | None = None) -> None: ...
    @property
    def top(self) -> Page | None:
        """The visible top page, or `None` if empty."""
    def push(self, page: Page) -> Page:
        """Show `page` and hide the previous top page."""
    def pop(self) -> Page | None:
        """Hide the top page and reveal the one under it; return the popped page."""
    def replace(self, page: Page) -> Page:
        """Replace the entire stack with a single page."""
