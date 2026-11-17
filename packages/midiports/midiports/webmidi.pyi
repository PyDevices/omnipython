# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""MIDI ports in a browser, over Web MIDI."""

from typing import Any

from . import PortIn, PortOut

PENDING_LIMIT: int
PAGE_LIMIT: int

def ports(access: Any, name: str = "", ring: int = 1024) -> tuple[PortIn, PortOut]:
    """``(midi_in, midi_out)`` over a ``MIDIAccess`` you already hold."""

async def open(name: str = "", sysex: bool = False, ring: int = 1024) -> tuple[PortIn, PortOut]:
    """Ask the browser for MIDI, then ``ports()`` on it."""

def page_in(name: str = "") -> PortIn:
    """An input over every matching port, for MicroPython's WebAssembly port."""

def page_out(name: str = "") -> PortOut:
    """An output to the first matching port, for MicroPython's WebAssembly port."""

def relay_ports(port: Any, ring: int = 1024) -> tuple[PortIn, PortOut]:
    """``(midi_in, midi_out)`` over a ``MessagePort`` the page relays MIDI on."""
