# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""BottomSheet — modal slide-up panel + scrim."""

from collections.abc import Callable
from typing import Any

from ..widget import Widget
from .card import Card

class BottomSheet(Widget):
    """Modal slide-up panel with scrim tap-to-dismiss."""

    scrim: int
    on_dismiss: Callable[[], None] | None
    panel: Card
    def __init__(self, parent: Widget, title: str | None = None, h: int | None = None, fg: int | None = None, bg: int | None = None, scrim: int | None = None, on_dismiss: Callable[[], None] | None = None) -> None: ...
    @property
    def content(self) -> Card:
        """Attach children to the panel card."""
    def show(self) -> None:
        """Show the sheet, grab modal capture, and redraw."""
    def hide_sheet(self) -> None:
        """Hide the sheet, release modal capture, and call `on_dismiss`."""
    def draw(self, area: Any = None) -> None:
        """Fill the scrim behind the slide-up panel."""
