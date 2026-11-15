# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Navigator/tab content page."""

from typing import Any

from ..widget import Widget

class Page(Widget):
    """Full-bleed content page for `Navigator` or `TabView`."""

    title: str | None
    def __init__(self, parent: Widget, x: int = 0, y: int = 0, w: int | None = None, h: int | None = None, align: int | None = None, align_to: Widget | None = None, fg: int | None = None, bg: int | None = None, visible: bool = True, value: Any = None, padding: tuple[int, int, int, int] | None = None, title: str | None = None) -> None: ...
