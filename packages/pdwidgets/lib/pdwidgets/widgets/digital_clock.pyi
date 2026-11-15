# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Live digital clock label."""

from typing import Any

from ..widget import Widget
from .label import Label

class DigitalClock(Label):
    """Live-updating HH:MM:SS clock label."""

    task: Any
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
        text_height: int = 16,
        scale: int = 1,
    ) -> None: ...
    def update_time(self) -> None:
        """Refresh the displayed time from the system clock."""
