# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Battery Service (0x180F): report a battery level that a phone or laptop can read."""
from . import Characteristic as Characteristic, Service as Service, UUID as UUID

SERVICE: UUID
BATTERY_LEVEL: UUID

class Battery:
    """A Battery Service holding one Battery Level characteristic."""

    SERVICE = SERVICE
    service: Service
    characteristic: Characteristic
    def __init__(self, level: int = 100) -> None: ...
    @property
    def level(self) -> int: ...
    def set_level(self, level: int) -> None:
        """Set the charge in percent and notify every central subscribed to it."""
