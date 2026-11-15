# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""On/off switch widget."""

from typing import Any

from ..widget import Widget

class Switch(Widget):
    """Pill track with sliding knob for boolean on/off."""

    on_color: int
    off_color: int
    knob_color: int
    def __init__(self, parent: Widget, x: int = 0, y: int = 0, w: int | None = None, h: int | None = None, align: int | None = None, align_to: Widget | None = None, fg: int | None = None, bg: int | None = None, visible: bool = True, value: bool = False, padding: tuple[int, int, int, int] | None = None, on_color: int | None = None, off_color: int | None = None, knob_color: int | None = None) -> None: ...
    def toggle(self, data: object = None, event: object = None) -> None:
        """Flip the switch between on and off."""
    def draw(self, _: Any = None) -> None:
        """Draw the pill track and the knob."""
