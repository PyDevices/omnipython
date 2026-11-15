# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Horizontal layout container."""

from typing import Any

from ..widget import Widget

class Row(Widget):
    """A container that lays its children out left-to-right with fixed spacing."""

    spacing: int
    def __init__(self, parent: Widget, x: int = 0, y: int = 0, w: int | None = None, h: int | None = None, align: int | None = None, align_to: Widget | None = None, fg: int | None = None, bg: int | None = None, visible: bool = True, value: Any = None, padding: tuple[int, int, int, int] | None = None, spacing: int = 2) -> None: ...
    def add_child(self, child: Widget) -> None:
        """Add a child widget, then re-flow the layout."""
    def remove_child(self, child: Widget) -> None:
        """Remove a child widget, then re-flow the layout."""
