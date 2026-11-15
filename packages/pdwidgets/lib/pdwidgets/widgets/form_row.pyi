# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Label plus control form row."""

from typing import Any

from ..widget import Widget
from .label import Label

class FormRow(Widget):
    """Horizontal row with a left label and trailing control."""

    label_widget: Label | None
    trailing: Widget | None
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
        label: str = "",
        scale: int = 1,
        font: object | None = None,
    ) -> None: ...
    def add_child(self, child: Widget) -> None:
        """Add a child; non-label children are treated as the trailing control."""
