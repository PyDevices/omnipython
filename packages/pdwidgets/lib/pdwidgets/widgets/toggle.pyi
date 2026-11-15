# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Icon toggle base class."""

from ..widget import Widget
from .icon_button import IconButton

class Toggle(IconButton):
    """Icon button that toggles between on and off states."""

    on_file: str
    off_file: str | None
    def __init__(self, parent: Widget, x: int = 0, y: int = 0, w: int | None = None, h: int | None = None, align: int | None = None, align_to: Widget | None = None, fg: int | None = None, bg: int | None = None, visible: bool = True, value: bool = False, padding: tuple[int, int, int, int] | None = None, on_file: str | None = None, off_file: str | None = None) -> None: ...
    def toggle(self, data: object = None, event: object = None) -> None:
        """Toggle the on/off state of the button."""
    def changed(self) -> None:
        """Update the icon based on the current on/off state."""
