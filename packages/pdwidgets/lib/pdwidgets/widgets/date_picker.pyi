# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""DatePicker — month calendar grid; value is (y, m, d) or ISO string."""

from typing import Any

from ..widget import Widget

class DatePicker(Widget):
    """Month calendar for selecting a date."""

    weekdays: list[str]
    def __init__(
        self,
        parent: Widget,
        x: int = 0,
        y: int = 0,
        w: int | None = None,
        h: int | None = None,
        align: int | None = None,
        align_to: Widget | None = None,
        fg: int | None = None,
        bg: int | None = None,
        visible: bool = True,
        value: Any = None,
        padding: tuple[int, int, int, int] | None = None,
        weekdays: list[str] | tuple[str, ...] | None = None,
    ) -> None: ...
    def draw(self, _: object = None) -> None:
        """Draw the month header and day grid."""
