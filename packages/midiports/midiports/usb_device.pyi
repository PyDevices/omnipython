# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""MIDI ports over a board's USB device interface."""

from typing import Any

from . import PortIn, PortOut

SEND_WAIT_MS: int

class MIDIPortsInterface:
    """The USB-MIDI interface behind ``ports``; it extends ``usb.device.midi.MIDIInterface``."""

    ports: tuple[PortIn, PortOut]
    def __init__(self, ring: int = 256, rxlen: int = 64, txlen: int = 128, stamps: int | None = None) -> None: ...
    def on_midi_event(self, cin: int, midi0: int, midi1: int, midi2: int) -> None: ...

def ports(ring: int = 256, stamps: int | None = None, name: str | None = None) -> tuple[PortIn, PortOut]:
    """Start the USB device with one MIDI interface; ``(midi_in, midi_out)``."""
