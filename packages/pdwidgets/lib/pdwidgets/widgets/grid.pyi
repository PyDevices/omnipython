# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Grid — fixed-column cell layout (row-major)."""

from typing import Any

from ..widget import Widget

class Grid(Widget):
    """Fixed-column grid layout container."""

    columns: int
    spacing: int
    cell_h: int | None
    def __init__(
        self,
        parent: Widget,
        x: int = 0,
        y: int = 0,
        w: int | None = None,
        h: int | None = None,
        align: int | None = None,
        align_to: Widget | None = None,
        fg: int | None = None,
        bg: int | None = None,
        visible: bool = True,
        value: Any = None,
        padding: tuple[int, int, int, int] | None = None,
        columns: int = 2,
        spacing: int = 2,
        cell_h: int | None = None,
    ) -> None: ...
    def add_child(self, child: Widget) -> None:
        """Add a child at the next grid cell."""
    def remove_child(self, child: Widget) -> None:
        """Remove a child and reflow remaining cells."""
