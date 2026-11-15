# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Horizontal divider widget."""

from typing import Any

from ..widget import Widget

class Divider(Widget):
    """Thin horizontal rule for separating sections."""

    thickness: int
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
        thickness: int = 1,
    ) -> None: ...
    def draw(self, _: object = None) -> None:
        """Paint the parent background, then the centered hairline."""
