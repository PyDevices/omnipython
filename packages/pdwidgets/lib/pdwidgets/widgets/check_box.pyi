# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Checkbox toggle widget."""

from ..widget import Widget
from .toggle import Toggle

class CheckBox(Toggle):
    """Boolean toggle rendered as checked/unchecked icons."""

    def __init__(self, parent: Widget, x: int = 0, y: int = 0, w: int | None = None, h: int | None = None, align: int | None = None, align_to: Widget | None = None, fg: int | None = None, bg: int | None = None, visible: bool = True, value: bool = False, padding: tuple[int, int, int, int] | None = None, size: int = ...) -> None: ...
