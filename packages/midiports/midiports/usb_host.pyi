# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""MIDI ports over a board's USB host port."""

from typing import Any

from . import PortIn, PortOut

def is_midi(dev: Any) -> bool:
    """For ``usb.core.find(custom_match=...)``."""

def all_ports(
    size: int = 64, poll_ms: int = 0, timeout_ms: int = 1000, rescan_ms: int = 1000, stall_ms: int = 500
) -> tuple[PortIn, PortOut]:
    """``(midi_in, midi_out)`` for every MIDI device on the host port at once."""

def ports(
    dev: Any = None, size: int = 64, poll_ms: int = 0, timeout_ms: int = 1000, wait_ms: int = 5000
) -> tuple[PortIn, PortOut | None]:
    """``(midi_in, midi_out)`` for a MIDI device on the host port; no output if it has none."""
