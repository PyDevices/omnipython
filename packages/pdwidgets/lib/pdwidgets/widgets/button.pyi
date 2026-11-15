# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Button widget with optional icon and label."""

from typing import Any, Literal

from ..widget import Widget
from .icon import Icon
from .label import Label

class Button(Widget):
    """Clickable control with optional icon and text label."""

    pressed_offset: int
    shadow: int
    icon: Icon
    label: Label | None
    def __init__(self, parent: Widget, x: int = 0, y: int = 0, w: int | None = None, h: int | None = None, align: int | None = None, align_to: Widget | None = None, fg: int | None = None, bg: int | None = None, visible: bool = True, value: Any = None, padding: tuple[int, int, int, int] | None = None, radius: int = 0, pressed_offset: int = 2, pressed: bool = False, label: str | None = None, text_color: int | None = None, text_height: int = ..., scale: int = 1, icon_file: str | None = None, icon_color: int | None = None, shadow: int = 0, style: Literal['flat', 'raised'] = 'flat', bg_hi: int | None = None, bg_lo: int | None = None, rim: int | None = None, backdrop: int | None = None) -> None: ...
    @property
    def style(self) -> Literal['flat', 'raised']:
        """Face style: `"flat"` or `"raised"`."""
    @property
    def backdrop(self) -> int | None:
        """Clear color under the face, or `None` to erase via the parent."""
    @backdrop.setter
    def backdrop(self, value: int | None) -> None: ...
    def draw(self, _: Any = None) -> None:
        """Draw the button background and shape (with an optional drop shadow)."""
    def press(self, data: Any = None, event: Any = None) -> None:
        """Mark pressed and dirty; flush via the display tick."""
    def release(self, data: Any = None, event: Any = None) -> None:
        """Clear pressed and dirty; flush via the display tick."""
