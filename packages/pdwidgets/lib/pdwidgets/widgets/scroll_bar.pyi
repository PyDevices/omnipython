# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Scrollbar widget."""

from ..widget import Widget
from .icon_button import IconButton
from .slider import Slider

class ScrollBar(Widget):
    """Scroll control with end arrows and a central slider."""

    pos_button: IconButton
    neg_button: IconButton
    slider: Slider
    def __init__(self, parent: Widget, x: int = 0, y: int = 0, w: int | None = None, h: int | None = None, align: int | None = None, align_to: Widget | None = None, fg: int | None = None, bg: int | None = None, visible: bool = True, value: float = 0.0, padding: tuple[int, int, int, int] | None = None, vertical: bool = False, reverse: bool = False, knob_color: int | None = None, step: float = 0.1) -> None: ...
