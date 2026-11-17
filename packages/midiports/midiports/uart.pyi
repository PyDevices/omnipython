# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""MIDI ports over a UART."""

from typing import Any

from . import WholeMessages

BAUDRATE: int

def ports(id: Any, *, tx: Any = None, rx: Any = None, baudrate: int = 31250, **kwargs: Any) -> tuple[WholeMessages, Any]:
    """``(midi_in, midi_out)`` over UART ``id``; the second is the UART itself."""
