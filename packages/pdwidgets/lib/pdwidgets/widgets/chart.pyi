# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Chart — tiny line / bar chart (MCU-light)."""

from collections.abc import Iterable
from typing import Any, Literal

from ..widget import Widget

class Chart(Widget):
    """Lightweight line or bar chart for numeric sequences."""

    mode: Literal['line', 'bar']
    auto_scale: bool
    def __init__(self, parent: Widget, x: int = 0, y: int = 0, w: int | None = None, h: int | None = None, align: int | None = None, align_to: Widget | None = None, fg: int | None = None, bg: int | None = None, visible: bool = True, value: Iterable[float] | None = None, padding: tuple[int, int, int, int] | None = None, mode: Literal['line', 'bar'] = 'line', auto_scale: bool = True) -> None: ...
    def draw(self, _: Any = None) -> None:
        """Draw the chart axes and data series."""
