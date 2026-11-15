# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Material Design icons as 8-bit alpha masks that stay in flash."""

from typing import Protocol

class _IconModule(Protocol):
    SIZE: int
    NAMES: tuple[str, ...] | list[str]
    DATA: bytes | memoryview

def mask(name: str, size: int = 24) -> tuple[memoryview, int, int]:
    """The alpha mask of icon `name`: `(data, w, h)`, `w * h` alpha bytes row by row."""

def names(size: int = 24) -> tuple[str, ...]:
    """Every icon name at `size`, in the order of its module(s)."""

def add(module: _IconModule) -> None:
    """Register an icon module built by `tools/make_icons.py` for the module's size."""
