# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""PasswordField: TextInput that masks glyphs."""

from ..widget import Widget
from .text_input import TextInput

class PasswordField(TextInput):
    """Single-line password entry; drawn text is replaced with mask characters."""

    mask: str
    def __init__(self, parent: Widget, x: int = 0, y: int = 0, w: int | None = None, h: int | None = None, align: int | None = None, align_to: Widget | None = None, fg: int | None = None, bg: int | None = None, visible: bool = True, value: str | None = None, padding: tuple[int, int, int, int] | None = None, hint: str = '', text_height: int = 16, radius: int = 6, max_length: int | None = None, mask: str = '*') -> None: ...
