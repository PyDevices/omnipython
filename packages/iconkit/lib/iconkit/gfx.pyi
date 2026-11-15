# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Draw an iconkit icon with pygraphics, or into an RGB565 buffer."""

from typing import Protocol

class _AlphaBlitter(Protocol):
    def blit_alpha(self, data: memoryview, x: int, y: int, w: int, h: int, color: int) -> None: ...

def draw(fb: _AlphaBlitter, name: str, x: int, y: int, color: int, size: int = 24) -> None:
    """Blend icon `name` in `color` over what `fb` already shows at (`x`, `y`)."""

def rgb565(
    name: str, color: int, bg: int, size: int = 24, buf: bytearray | None = None
) -> bytearray:
    """Icon `name` in `color` blended onto a flat `bg`, as RGB565, low byte first."""
