# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Show an icon in LVGL."""

from typing import Any

def dsc(name: str, size: int = 24) -> Any:
    """The `lv.image_dsc_t` for icon `name`, built once and kept alive."""

def image(parent: Any, name: str, size: int = 24, color: Any = None) -> Any:
    """An `lv.image` showing icon `name` in `color` (an `lv.color_t`; white when omitted)."""
