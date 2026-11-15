# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Optional C accelerators for audiodev, from audiodsp when it is present."""

from collections.abc import Callable

__all__ = ("best_remix", "have_accel")

def best_remix() -> Callable[..., bytearray] | None:
    """Return `audiomath.remix_s16`, or `None` when audiodsp is absent."""

def have_accel() -> bool:
    """True when a C remix is available."""
