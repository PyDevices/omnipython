# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""A desktop window's keyboard, mouse and gamepads as endpointkit endpoints."""

from collections.abc import Callable, Sequence

import endpointkit

RESCAN_MS: int

class Fixed(endpointkit.Provider):
    """One input that is always there: the computer's keyboard or its mouse."""

    def __init__(self, kind: str, name: str, local_id: str, label: str) -> None: ...
    def scan(self) -> list[endpointkit.Endpoint]: ...

def joystick_names() -> list[str]:
    """The names of the joysticks the running display opened, in its order."""

class Gamepads(endpointkit.Provider):
    """The gamepads the display opened."""

    rescan_ms: int
    def __init__(self, names: Callable[[], Sequence[str]] | None = None, rescan_ms: int = ...) -> None: ...
    def scan(self) -> list[endpointkit.Endpoint]: ...
    def poll(self) -> list[endpointkit.Endpoint] | None: ...

def register(registry: endpointkit.Registry | None = None) -> list[endpointkit.Provider]:
    """Register the keyboard, the mouse and the gamepads, and a browser page's cameras."""
