# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Framebuffer text console with optional vertical scrolling."""

import io

from . import Widget

class Console(io.IOBase, Widget):
    """Framebuffer text console with optional vertical scrolling."""

    margin: int
    text_height: int
    scale: int
    font_data: str | bytes | None
    dirty_areas: list[tuple[int, int, int, int]]
    by_char: bool
    columns: int
    rows: int
    cursor_col: int
    cursor_row: int
    cursor_max_row: int
    def __init__(
        self,
        parent: Widget,
        fg: int | None = None,
        bg: int | None = None,
        visible: bool = True,
        value: str | None = None,
        by_char: bool = False,
        margin: int = 1,
        text_height: int = ...,
        scale: int = 1,
        font_data: str | bytes | None = None,
    ) -> None: ...
    def clear(self) -> None: ...
    def readinto(self, buf: bytearray | memoryview, nbytes: int = 0) -> int | None: ...
    def write(self, buf: str | bytes | bytearray | memoryview, fg: int | None = None, bg: int | None = None) -> int: ...
    def draw(self) -> None: ...  # type: ignore[override]
