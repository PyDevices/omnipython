# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Gauge widget (arc / dial)."""

from ..widget import Widget

class Gauge(Widget):
    """Arc gauge displaying a normalized value in `[0, 1]`."""

    start_angle: int
    sweep: int
    track_color: int
    label: str | None
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
        value: float = 0.0,
        padding: tuple[int, int, int, int] | None = None,
        start_angle: int = 135,
        sweep: int = 270,
        track_color: int | None = None,
        label: str | None = None,
    ) -> None: ...
    def draw(self, _: object = None) -> None:
        """Draw track + value arcs and optional center text."""
