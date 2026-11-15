# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Single-line text input field."""

from typing import Any

from ..widget import Widget

class TextInput(Widget):
    """Single-line editable text field with focus management."""

    hint: str
    text_height: int
    max_length: int | None
    focused: bool
    def __init__(self, parent: Widget, x: int = 0, y: int = 0, w: int | None = None, h: int | None = None, align: int | None = None, align_to: Widget | None = None, fg: int | None = None, bg: int | None = None, visible: bool = True, value: str | None = None, padding: tuple[int, int, int, int] | None = None, hint: str = '', text_height: int = 16, radius: int = 6, max_length: int | None = None) -> None: ...
    def draw(self, _: Any = None) -> None:
        """Draw the field box, its text or hint, and the cursor when focused."""
