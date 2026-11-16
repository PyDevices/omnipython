# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""SegmentedControl: exclusive pill buttons."""

from typing import Any, Literal, Sequence

from ..widget import Widget

class SegmentedControl(Widget):
    """Exclusive pill-style segment selector; `value` is the selected index."""

    labels: list[str]
    text_height: int
    def __init__(self, parent: Widget, x: int = 0, y: int = 0, w: int | None = None, h: int | None = None, align: int | None = None, align_to: Widget | None = None, fg: int | None = None, bg: int | None = None, visible: bool = True, value: int = 0, padding: tuple[int, int, int, int] | None = None, labels: Sequence[str] | None = None, text_height: int = 14, radius: int = 8, style: Literal['flat', 'raised'] | None = 'flat', bg_hi: int | None = None, bg_lo: int | None = None, rim: int | None = None) -> None: ...
    @property
    def style(self) -> Literal['flat', 'raised']:
        """Face style: `"flat"` or `"raised"` (raised applies to the selected segment)."""
    def draw(self, _: Any = None) -> None:
        """Draw segment backgrounds and labels."""
