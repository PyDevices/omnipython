# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
from . import Characteristic as Characteristic, Service as Service, UUID as UUID
from _typeshed import Incomplete

SERVICE: Incomplete
HEART_RATE_MEASUREMENT: Incomplete
BODY_SENSOR_LOCATION: Incomplete
HEART_RATE_CONTROL_POINT: Incomplete
OTHER: int
CHEST: int
WRIST: int
FINGER: int
HAND: int
EAR_LOBE: int
FOOT: int

def encode_measurement(bpm, rr_ms=(), energy_kj=None, contact=None): ...

class HeartRate:
    SERVICE = SERVICE
    service: Incomplete
    characteristic: Incomplete
    def __init__(self, location=None, energy_expended: bool = False) -> None: ...
    def update(self, bpm, rr_ms=(), energy_kj=None, contact=None) -> None: ...
    async def reset_requested(self) -> None: ...
