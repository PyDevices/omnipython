# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Menu: popup action list (labels to callbacks)."""

from typing import Any, Callable, Iterable

from ..widget import Widget
from .card import Card

class Menu(Widget):
    """Modal popup action menu of labeled callbacks."""

    scrim: int
    card: Card
    def __init__(self, parent: Widget, items: Iterable[tuple[str, Callable[[], None] | None]] | None = None, x: int = 0, y: int = 0, w: int | None = None, h: int | None = None, fg: int | None = None, bg: int | None = None, scrim: int | None = None) -> None: ...
    def show(self) -> None:
        """Show the menu, grab modal capture, and redraw."""
    def hide_menu(self) -> None:
        """Hide the menu and release modal capture."""
    def draw(self, area: Any = None) -> None:
        """Fill the scrim behind the popup menu."""
