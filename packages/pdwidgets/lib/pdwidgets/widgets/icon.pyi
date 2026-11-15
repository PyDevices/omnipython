# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Icon display widget."""

from typing import Any

from ..widget import Widget

class Icon(Widget):
    """Monochrome or RGB565 icon display."""

    cache: dict[str, Any]
    chroma: int | None
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
        chroma: int | None = None,
    ) -> None: ...
    def load_icon(self, value: str) -> None:
        """Load icon asset, cache it, and record whether it is a color asset."""
    def changed(self) -> None:
        """Update the icon when the value changes."""
    def draw(self, _: object = None) -> None:
        """Draw the icon on the screen."""
