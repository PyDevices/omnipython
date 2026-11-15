# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""PinPad: numeric button grid emitting digits into a field / callback."""

from typing import Callable, Protocol

from ..widget import Widget
from .grid import Grid

class _HasValue(Protocol):
    """Any widget or object with a settable string `value`."""

    value: str

class PinPad(Widget):
    """3x4 numeric keypad for PIN or code entry."""

    target: _HasValue | None
    on_digit: Callable[[str, str], None] | None
    on_enter: Callable[[str], None] | None
    max_length: int | None
    grid: Grid
    def __init__(self, parent: Widget, x: int = 0, y: int = 0, w: int | None = None, h: int | None = None, align: int | None = None, align_to: Widget | None = None, fg: int | None = None, bg: int | None = None, visible: bool = True, value: str = '', padding: tuple[int, int, int, int] | None = None, target: _HasValue | None = None, on_digit: Callable[[str, str], None] | None = None, on_enter: Callable[[str], None] | None = None, max_length: int | None = 8) -> None: ...
