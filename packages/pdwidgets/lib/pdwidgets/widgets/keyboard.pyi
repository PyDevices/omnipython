# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""On-screen keyboard widget."""

from typing import Any

from ..widget import Widget

class Keyboard(Widget):
    """On-screen QWERTY keyboard for focused text fields."""

    target: Any
    row_height: int
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
        visible: bool = False,
        value: Any = None,
        padding: tuple[int, int, int, int] | None = None,
        target: Any = None,
        row_height: int | None = None,
    ) -> None: ...
    def show(self, target: Any = None) -> None:
        """Show the keyboard, optionally binding `target` TextInput."""
    def hide_keyboard(self) -> None:
        """Hide the keyboard."""
