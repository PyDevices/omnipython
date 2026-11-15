# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
from typing import Any, Literal

from displaydev import DisplayDriver

__all__ = ['host_kind', 'AutoDisplay']

def host_kind() -> Literal['wasm', 'android', 'pyscript', 'jupyter', 'desktop']:
    """Return the kind of host the program runs on."""
def AutoDisplay(width: int = 320, height: int = 240, rotation: int = 0, scale: float = 1.0, title: str = 'displaydev', canvas_id: str | None = None, *, quiet: bool = False, maximized: bool = False, **kwargs: Any) -> DisplayDriver:
    """Construct a host-appropriate display driver."""
