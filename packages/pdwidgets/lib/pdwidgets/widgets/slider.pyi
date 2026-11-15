# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Slider widget."""

from typing import Any

from ..widget import Widget
from .progress_bar import ProgressBar

class Slider(ProgressBar):
    """Draggable 0 to 1 value control with a circular knob."""

    knob_color: int
    step: float
    dragging: bool
    knob_radius: int
    def __init__(self, parent: Widget, x: int = 0, y: int = 0, w: int | None = None, h: int | None = None, align: int | None = None, align_to: Widget | None = None, fg: int | None = None, bg: int | None = None, visible: bool = True, value: float = 0.0, padding: tuple[int, int, int, int] | None = None, vertical: bool = False, reverse: bool = False, knob_color: int | None = None, step: float = 0.1) -> None: ...
    def draw(self, _: Any = None) -> None:
        """Draw the progress bar and the circular knob."""
    def event_callback(self, data: Any, event: Any) -> None:
        """Handle clicks, dragging and mouse movement."""
    def adjust_value(self, value: float) -> None:
        """Add `value` to the slider value (negated when reversed), clamped to 0..1."""
