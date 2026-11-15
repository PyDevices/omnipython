# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Card container widget."""

from typing import Any, Literal

from ..widget import Widget
from .label import Label

class Card(Widget):
    """Rounded container with optional title and drop shadow."""

    shadow: int
    title_label: Label | None
    def __init__(self, parent: Widget, x: int = 0, y: int = 0, w: int | None = None, h: int | None = None, align: int | None = None, align_to: Widget | None = None, fg: int | None = None, bg: int | None = None, visible: bool = True, value: Any = None, padding: tuple[int, int, int, int] | None = None, radius: int = 8, shadow: int = 2, title: str | None = None, font: Any = None, style: Literal['flat', 'raised'] = 'flat', bg_hi: int | None = None, bg_lo: int | None = None, rim: int | None = None) -> None: ...
    @property
    def style(self) -> Literal['flat', 'raised']:
        """Face style: `"flat"` or `"raised"`."""
    def draw(self, area: Any = None) -> None:
        """Draw the card's shadow and rounded surface."""
