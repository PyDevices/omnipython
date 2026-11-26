# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Bluetooth MIDI devices a browser page connects to, through Web Bluetooth."""

from typing import Any, Callable

from . import PortIn, PortInfo, PortOut
from .ble import BleIn

ASK: str
KEEP_ASKING: bool
RETRY_MS: int

class PageBleIn(BleIn):
    """The link to one device the person chose, with the browser as the central."""

    retry_ms: int
    def __init__(self, ble: Any = None, connect: Callable[..., Any] | None = None, **options: Any) -> None: ...

def state() -> str:
    """``"asking"`` while the chooser is open, ``"idle"`` otherwise, or ``"unavailable"``."""

def why() -> str | None:
    """Why no device can be chosen, or why the last choice failed (once); None otherwise."""

def request(link: Callable[[], PageBleIn] = ...) -> None:
    """Open the browser's chooser; the device picked is listed once it connects."""

def changes() -> int:
    """A count that moves whenever the devices or the chooser's state do."""

def available() -> tuple[PortInfo, ...]:
    """``PortInfo`` for each device chosen, both ways round."""

def open_port(info: PortInfo) -> PortIn | PortOut:
    """Open one of `available`'s ports."""

def forget() -> None:
    """Close every device's link and forget them, as a page's restart would."""
