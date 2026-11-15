# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Accordion — header + expandable body."""

from typing import Any

from ..widget import Widget
from .button import Button

class Accordion(Widget):
    """Stack of titled expansion panels; `exclusive` keeps at most one open."""

    exclusive: bool
    def __init__(self, parent: Widget, x: int = 0, y: int = 0, w: int | None = None, h: int | None = None, align: int | None = None, align_to: Widget | None = None, fg: int | None = None, bg: int | None = None, visible: bool = True, value: Any = None, padding: tuple[int, int, int, int] | None = None, exclusive: bool = True) -> None: ...
    def add_panel(self, title: str, body: Widget, open_: bool = False) -> Button:
        """Add a titled panel wrapping `body`; returns the header button."""
