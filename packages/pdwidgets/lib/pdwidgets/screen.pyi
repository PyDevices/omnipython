# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Full-screen widget container."""

from .display import Display
from .widget import Widget

class Screen(Widget):
    """Full-screen page container for grouping a coherent UI view."""

    partitioned: bool
    top: Widget
    main: Widget
    bottom: Widget
    def __init__(
        self, parent: Display | Widget, fg: int | None = None, bg: int | None = None, visible: bool = True
    ) -> None: ...
