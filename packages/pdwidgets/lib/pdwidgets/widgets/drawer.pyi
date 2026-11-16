# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Drawer — side panel + scrim."""

from typing import Callable, Literal

from ..widget import Widget
from .card import Card

class Drawer(Widget):
    """Modal side panel that slides in from the left or right."""

    scrim: int
    on_dismiss: Callable[[], None] | None
    side: Literal["left", "right"]
    panel: Card
    def __init__(
        self,
        parent: Widget,
        title: str | None = None,
        w: int | None = None,
        side: Literal["left", "right"] = "left",
        fg: int | None = None,
        bg: int | None = None,
        scrim: int | None = None,
        on_dismiss: Callable[[], None] | None = None,
    ) -> None: ...
    @property
    def content(self) -> Card:
        """The `Card` panel; add child widgets here."""
    def show(self) -> None:
        """Show the drawer, grab modal capture, and redraw."""
    def hide_drawer(self) -> None:
        """Hide the drawer, release modal capture, and call `on_dismiss`."""
    def draw(self, area: object | None = None) -> None:
        """Fill the scrim behind the side panel."""
