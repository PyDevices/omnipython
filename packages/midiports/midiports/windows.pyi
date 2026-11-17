# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""MIDI ports on Windows, over the winmm API."""

from . import PortIn, PortInfo, PortOut

HWND_MESSAGE: int
SYSEX_BUFFERS: int
SYSEX_BUFFER_SIZE: int

def available() -> tuple[PortInfo, ...]:
    """Every MIDI port Windows offers, both directions."""

def find(name: str, direction: str | None = None) -> tuple[PortInfo, ...]:
    """Ports whose name contains ``name``, case-insensitively."""

def ports(name: str = "") -> tuple[WindowsMidiIn | None, WindowsMidiOut | None]:
    """``(midi_in, midi_out)`` for the first ports matching ``name``; ``None`` for a direction with no port."""

def open_port(port: PortInfo | str) -> WindowsMidiIn | WindowsMidiOut:
    """Open one port, given a ``PortInfo`` or an id string."""

class WindowsMidiOut(PortOut):
    def __init__(self, info: PortInfo, index: int) -> None: ...

class WindowsMidiIn(PortIn):
    def __init__(self, info: PortInfo, index: int) -> None: ...
    def any(self) -> int: ...
