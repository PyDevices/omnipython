# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Turn accelerometer readings into a screen rotation of 0, 90, 180 or 270."""

def sector(x: float, y: float, z: float, *, upright: float = 0.9) -> int | None:
    """The sector gravity points into, 0, 90, 180 or 270, or `None` for a flat board or a zero reading."""

class Orientation:
    """The screen rotation for a stream of readings, with hysteresis."""

    offset: int
    stable: int
    upright: float
    rotation: int
    def __init__(self, *, offset: int = 0, stable: int = 2, upright: float = 0.9, rotation: int = 0) -> None: ...
    def update(self, x: float, y: float, z: float) -> int | None:
        """Take one reading. Returns the new rotation when it changes, else `None`."""
