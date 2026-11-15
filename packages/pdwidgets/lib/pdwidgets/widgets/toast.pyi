# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Transient toast notification."""

from typing import Any

from ..widget import Widget
from .label import Label

class Toast(Widget):
    """Transient bottom banner that auto-hides after a duration."""

    duration_ms: int
    message: Label
    def __init__(self, parent: Widget, x: int = 0, y: int = 0, w: int | None = None, h: int | None = None, align: int | None = None, align_to: Widget | None = None, fg: int | None = None, bg: int | None = None, visible: bool = False, value: str = '', padding: tuple[int, int, int, int] | None = None, duration_ms: int = 2000, radius: int = 8) -> None: ...
    def show(self, message: str | None = None, duration_ms: int | None = None) -> None:
        """Show the toast with `message` (keeps the current text if omitted)."""
    def draw(self, area: Any = None) -> None:
        """Draw a rounded toast pill."""
