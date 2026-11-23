# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
from typing import Any

from displaydev import DisplayDriver
from displaydev.fbdisplay import FBDisplay

class RemoteServer:
    """Serves a display's frame to one browser or video player, and takes its input."""
    display: DisplayDriver
    port: int
    url: str
    sent: int
    frames: int
    quality: int
    def __init__(self, display: DisplayDriver, port: int = 80, period_ms: int = 40, sweep_ms: int = 2000, bind: str = "0.0.0.0") -> None: ...
    def note(self, x: int, y: int, w: int, h: int) -> None: ...
    def poll(self, _timer: Any = None) -> None: ...
    def read(self) -> list[Any]: ...
    @property
    def connected(self) -> bool: ...
    def close(self) -> None: ...

def mirror(display: FBDisplay, port: int = 80, period_ms: int = 40, sweep_ms: int = 2000) -> RemoteServer: ...

class RemoteDisplay(FBDisplay):
    """A display with no panel, shown and used in a web browser."""
    server: RemoteServer
    def __init__(self, width: int = 480, height: int = 320, port: int = 80, period_ms: int = 40, sweep_ms: int = 2000, *, quiet: bool = False) -> None: ...
    def get_events(self) -> list[Any]: ...
    @property
    def needs_refresh(self) -> bool: ...  # type: ignore[override]
