# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Numeric stepper widget."""

from ..widget import Widget
from .icon_button import IconButton
from .text_box import TextBox

class NumberStepper(Widget):
    """Bounded numeric stepper with `-` / `+` buttons."""

    step: int | float
    minimum: int | float | None
    maximum: int | float | None
    neg_button: IconButton
    pos_button: IconButton
    box: TextBox
    def __init__(self, parent: Widget, x: int = 0, y: int = 0, w: int | None = None, h: int | None = None, align: int | None = None, align_to: Widget | None = None, fg: int | None = None, bg: int | None = None, visible: bool = True, value: int | float = 0, padding: tuple[int, int, int, int] | None = None, step: int | float = 1, minimum: int | float | None = None, maximum: int | float | None = None, number_format: str = '{}') -> None: ...
    def changed(self) -> None:
        """Clamp the value to the configured bounds and refresh the display."""
