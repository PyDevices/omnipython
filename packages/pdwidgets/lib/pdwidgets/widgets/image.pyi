# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Raster image widget."""

from typing import Any

from ..widget import Widget

class Image(Widget):
    """Raster image widget (package icon module or `.pbm` / `.bmp` path)."""

    cache: dict[str, Any]
    chroma: int | None
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
        chroma: int | None = None,
    ) -> None: ...
    def changed(self) -> None:
        """Invalidate after the image path changes."""
    def draw(self, _: object = None) -> None:
        """Blit the image or a placeholder rectangle."""
