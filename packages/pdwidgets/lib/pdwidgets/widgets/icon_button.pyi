# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Icon-only button."""

from typing import Any, Literal

from ..widget import Widget
from .button import Button

class IconButton(Button):
    """Button whose content is a centered icon."""

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
        icon_file: str | None = None,
        radius: int = 0,
        shadow: int = 0,
        style: Literal["flat", "raised"] = "flat",
        bg_hi: int | None = None,
        bg_lo: int | None = None,
        rim: int | None = None,
        backdrop: int | None = None,
    ) -> None: ...
