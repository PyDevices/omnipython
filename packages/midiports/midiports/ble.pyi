# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""BLE-MIDI ports: advertise as a MIDI device a computer or phone connects to."""

from typing import Any

from _typeshed import ReadableBuffer

from . import PortIn, PortOut

QUEUE_LIMIT: int
PUMP_MS: int
WATCH_MS: int

def available() -> bool:
    """True when this board's firmware has Bluetooth LE for ``ports``."""

class BleIn(PortIn):
    def __init__(
        self,
        name: str | None,
        ble: Any,
        *,
        pump: Any = None,
        pump_ms: int = 4,
        queue_limit: int = 256,
        stamps: int = 64,
    ) -> None: ...
    def any(self) -> int:
        """How many MIDI bytes are waiting, after running the link's tasks."""

    def write(self, buf: ReadableBuffer, nbytes: int | None = None) -> int: ...

class BleOut(PortOut):
    def __init__(self, link: BleIn) -> None: ...

def ports(
    name: str | None = None, *, adapter: Any = None, pump: Any = None, pump_ms: int = 4, queue_limit: int = 256
) -> tuple[BleIn, BleOut]:
    """``(midi_in, midi_out)``: advertise BLE-MIDI as ``name`` and serve the connected central."""
