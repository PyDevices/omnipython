# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Application title bar."""

from collections.abc import Callable
from typing import Any

from ..widget import Widget
from .icon_button import IconButton
from .label import Label

class AppBar(Widget):
    """Top title bar with optional leading back button."""

    on_back: Callable[[AppBar], None] | None
    back_button: IconButton | None
    title_label: Label
    def __init__(self, parent: Widget, x: int = 0, y: int = 0, w: int | None = None, h: int | None = None, align: int | None = None, align_to: Widget | None = None, fg: int | None = None, bg: int | None = None, visible: bool = True, value: Any = None, padding: tuple[int, int, int, int] | None = None, title: str = '', on_back: Callable[[AppBar], None] | None = None, scale: int = 2, font: Any = None) -> None: ...
    def set_title(self, title: str) -> None:
        """Update the title text."""
