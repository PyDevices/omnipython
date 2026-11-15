# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Modal dialog widget."""

from typing import Callable

from ..widget import Widget
from .card import Card

class Dialog(Widget):
    """Modal message box with title, body, and action buttons."""

    scrim: int
    on_result: Callable[[str], None] | None
    card: Card
    def __init__(
        self,
        parent: Widget,
        message: str = "",
        title: str | None = None,
        buttons: list[str] | tuple[str, ...] | None = None,
        on_result: Callable[[str], None] | None = None,
        fg: int | None = None,
        bg: int | None = None,
        w: int | None = None,
        h: int | None = None,
        font: object | None = None,
        scrim: int | None = None,
    ) -> None: ...
    def show(self) -> None:
        """Show the dialog and grab modal pointer capture."""
    def hide_dialog(self) -> None:
        """Hide the dialog and release modal pointer capture."""
    def draw(self, area: object | None = None) -> None:
        """Paint the opaque scrim behind the card."""
