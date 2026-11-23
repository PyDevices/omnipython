# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""BLE-MIDI ports: advertise as a MIDI device a computer or phone connects to, or connect to a controller."""

from typing import Any

from _typeshed import ReadableBuffer

from . import PortIn, PortOut

QUEUE_LIMIT: int
PUMP_MS: int
WATCH_MS: int
SCAN_MS: int
RETRY_MS: int

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

    def read(self, nbytes: int | None = None) -> bytes | None:
        """Waiting MIDI bytes; a SysEx comes out whole when ``nbytes`` allows."""

    def write(self, buf: ReadableBuffer, nbytes: int | None = None) -> int: ...

class BleCentralIn(BleIn):
    scan_ms: int
    retry_ms: int
    misses: int
    miss: BaseException | None
    def __init__(
        self,
        name: str | None,
        ble: Any,
        *,
        scan_ms: int = 5000,
        retry_ms: int = 1000,
        connect_options: dict[str, Any] | None = None,
        pump: Any = None,
        pump_ms: int = 4,
        queue_limit: int = 256,
        stamps: int = 64,
    ) -> None: ...

class BleOut(PortOut):
    def __init__(self, link: BleIn) -> None: ...

def ports(
    name: str | None = None, *, adapter: Any = None, pump: Any = None, pump_ms: int = 4, queue_limit: int = 256
) -> tuple[BleIn, BleOut]:
    """``(midi_in, midi_out)``: advertise BLE-MIDI as ``name`` and serve the connected central."""

def connect_ports(
    name: str | None = None,
    *,
    adapter: Any = None,
    pump: Any = None,
    pump_ms: int = 4,
    queue_limit: int = 256,
    scan_ms: int = 5000,
    retry_ms: int = 1000,
    **connect_options: Any,
) -> tuple[BleCentralIn, BleOut]:
    """``(midi_in, midi_out)``: find the BLE-MIDI device advertising as ``name``, connect, and reconnect after a drop."""
