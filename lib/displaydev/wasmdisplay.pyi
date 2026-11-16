# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
from collections.abc import Callable
from typing import Any

from displaydev import DisplayDriver
from displaydev.fbdisplay import FBDisplay as FBDisplay

class _DesktopDisplay(DisplayDriver):
    def vscrdef(self, tfa: int, vsa: int, bfa: int) -> None: ...
    def vscsad(self, vssa: int | None = None) -> int: ...

class WasmDevices:
    """Translate neutral bridge records into the project-wide `events` contract."""
    def __init__(self, canvas_id: str) -> None: ...
    def read(self) -> list[tuple[Any, ...]] | None: ...
    def clear(self) -> None: ...

class WasmDisplay(_DesktopDisplay, FBDisplay):
    """A Python-owned RGB565 framebuffer scanned live by the browser."""
    needs_refresh: bool
    refresh_period_ms: int
    quit_chord: tuple[int, int]
    can_rotate: bool
    get_events: Callable[[], list[tuple[Any, ...]] | None]
    def __init__(self, width: int = 320, height: int = 240, canvas_id: str = 'display_canvas', *, quiet: bool = False) -> None: ...
    def init(self) -> None: ...
    def show(self, _timer: Any = None) -> None: ...
