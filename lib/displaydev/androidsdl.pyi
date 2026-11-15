# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
from typing import Any

from displaydev.sdldisplay import SDLDisplay

__all__ = ['AndroidSDLDisplay']

class AndroidSDLDisplay(SDLDisplay):
    """`SDLDisplay` for Android: aspect locks the Activity, no rotated copy."""
    quit_chord: tuple[int, int]
    def __init__(self, width: int = 320, height: int = 240, rotation: int = 0, color_depth: int = 16, title: str = 'SDL2 Display', scale: float = 1.0, window_flags: int = ..., render_flags: int = ..., x: int = ..., y: int = ..., *, quiet: bool = False) -> None: ...
    def show(self, _timer: Any = None) -> None: ...
    def init(self) -> None: ...
