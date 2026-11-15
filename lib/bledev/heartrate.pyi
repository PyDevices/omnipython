# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Heart Rate Service (0x180D): a heart rate monitor that fitness apps can read."""
from . import Characteristic as Characteristic, Service as Service, UUID as UUID
from collections.abc import Iterable

SERVICE: UUID
HEART_RATE_MEASUREMENT: UUID
BODY_SENSOR_LOCATION: UUID
HEART_RATE_CONTROL_POINT: UUID
OTHER: int
CHEST: int
WRIST: int
FINGER: int
HAND: int
EAR_LOBE: int
FOOT: int

def encode_measurement(bpm: int, rr_ms: Iterable[float] = (), energy_kj: int | None = None, contact: bool | None = None) -> bytes:
    """The Heart Rate Measurement bytes: flags, rate, energy, RR-intervals."""

class HeartRate:
    """A Heart Rate Service."""

    SERVICE = SERVICE
    service: Service
    characteristic: Characteristic
    def __init__(self, location: int | None = None, energy_expended: bool = False) -> None: ...
    def update(self, bpm: int, rr_ms: Iterable[float] = (), energy_kj: int | None = None, contact: bool | None = None) -> None:
        """Send a measurement to every central subscribed to it."""
    async def reset_requested(self) -> None:
        """Wait until a central asks to reset the energy count, then return."""
