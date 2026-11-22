# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Material Symbols icons at any size, drawn from a font that stays in flash."""

from typing import Protocol

CACHE_SIZE: int
"""How many drawn masks `mask` keeps."""
SCRATCH: int
"""ttfio's starting working memory per font, in bytes."""
SCRATCH_MAX: int
"""The most a font's working memory grows to when a glyph needs more."""

class _FontModule(Protocol):
    FONT: bytes
    NAMES: bytes
    CODES: bytes

def has(name: str) -> bool:
    """Whether an icon named `name` is in the built-in font or one added with `add`."""

def mask(name: str, size: int = 24, buf: bytearray | None = None) -> tuple[memoryview | bytearray, int, int]:
    """The alpha mask of icon `name` in a `size` by `size` square: `(data, w, h)`."""

def names() -> list[str]:
    """Every icon name: the built-in font's, sorted, then each added font's."""

def add(module: _FontModule) -> None:
    """Register a font module built by `tools/make_icons.py`."""
