# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Busy spinner widget."""

from typing import Any

from ..widget import Widget

class Spinner(Widget):
    """Animated circular busy indicator; `value` is the rotation angle in degrees."""

    period_ms: int
    def __init__(self, parent: Widget, x: int = 0, y: int = 0, w: int | None = None, h: int | None = None, align: int | None = None, align_to: Widget | None = None, fg: int | None = None, bg: int | None = None, visible: bool = True, value: int = 0, padding: tuple[int, int, int, int] | None = None, period_ms: int = 80) -> None: ...
    def start(self) -> None:
        """Begin spinning."""
    def stop(self) -> None:
        """Stop spinning and hide."""
    def draw(self, _: Any = None) -> None:
        """Draw a partial ring whose start angle tracks `value`."""
