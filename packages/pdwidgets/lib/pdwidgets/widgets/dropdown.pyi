# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Dropdown selection widget."""

from typing import Any

from ..widget import Widget

class Dropdown(Widget):
    """Header button that opens a modal list of options."""

    options: list[str]
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
        options: list[str] | tuple[str, ...] | None = None,
        radius: int = 6,
    ) -> None: ...
    def changed(self) -> None:
        """Update the header label to the selected option."""
    def draw(self, area: object | None = None) -> None:
        """Draw the dropdown header (rounded surface); repaint sub-areas flat."""
