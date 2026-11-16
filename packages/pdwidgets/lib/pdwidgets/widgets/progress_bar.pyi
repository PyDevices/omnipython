# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Progress bar widget."""

from typing import Any

from ..widget import Widget

class ProgressBar(Widget):
    """Horizontal or vertical progress indicator (0 to 1)."""

    vertical: bool
    reverse: bool
    end_radius: int
    def __init__(self, parent: Widget, x: int = 0, y: int = 0, w: int | None = None, h: int | None = None, align: int | None = None, align_to: Widget | None = None, fg: int | None = None, bg: int | None = None, visible: bool = True, value: float = 0.0, padding: tuple[int, int, int, int] | None = None, vertical: bool = False, reverse: bool = False) -> None: ...
    def draw_ends(self) -> None:
        """Draw the circular ends of the progress bar."""
    def draw(self, _: Any = None) -> None:
        """Draw the progress bar."""
    def changed(self) -> None:
        """Clamp the value to 0..1 and invalidate."""
