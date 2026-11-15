# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Chip — compact selectable filter chip (Badge stays status-only)."""

from typing import Any, Literal

from ..widget import Widget

class Chip(Widget):
    """Compact selectable filter chip."""

    label: str
    text_height: int
    def __init__(self, parent: Widget, x: int = 0, y: int = 0, w: int | None = None, h: int | None = None, align: int | None = None, align_to: Widget | None = None, fg: int | None = None, bg: int | None = None, visible: bool = True, value: bool = False, padding: tuple[int, int, int, int] | None = None, label: str = '', text_height: int = ..., radius: int = 10, style: Literal['flat', 'raised'] = 'flat', bg_hi: int | None = None, bg_lo: int | None = None, rim: int | None = None) -> None: ...
    @property
    def style(self) -> Literal['flat', 'raised']:
        """Face style: `"flat"` or `"raised"`."""
    def draw(self, _: Any = None) -> None:
        """Draw the chip background and label."""
