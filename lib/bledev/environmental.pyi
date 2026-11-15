# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Environmental Sensing Service (0x181A): temperature, humidity, pressure and UV index."""
from . import Characteristic as Characteristic, Service as Service, UUID as UUID

SERVICE: UUID
PRESSURE: UUID
TEMPERATURE: UUID
HUMIDITY: UUID
UV_INDEX: UUID

def encode_temperature(celsius: float) -> bytes:
    """Temperature as sint16 in 0.01 degrees Celsius."""
def encode_humidity(percent: float) -> bytes:
    """Relative humidity as uint16 in 0.01 percent."""
def encode_pressure(pascals: float) -> bytes:
    """Pressure as uint32 in 0.1 pascal."""
def encode_uv_index(index: float) -> bytes:
    """The UV index as uint8."""

class EnvironmentalSensing:
    """An Environmental Sensing Service."""

    SERVICE = SERVICE
    service: Service
    characteristics: dict[str, Characteristic]
    def __init__(self, temperature: bool = False, humidity: bool = False, pressure: bool = False, uv_index: bool = False) -> None: ...
    def update(self, temperature: float | None = None, humidity: float | None = None, pressure: float | None = None, uv_index: float | None = None) -> None:
        """Set readings and notify the centrals subscribed to them."""
