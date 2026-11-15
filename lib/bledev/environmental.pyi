# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
from . import Characteristic as Characteristic, Service as Service, UUID as UUID
from _typeshed import Incomplete

SERVICE: Incomplete
PRESSURE: Incomplete
TEMPERATURE: Incomplete
HUMIDITY: Incomplete
UV_INDEX: Incomplete

def encode_temperature(celsius): ...
def encode_humidity(percent): ...
def encode_pressure(pascals): ...
def encode_uv_index(index): ...

class EnvironmentalSensing:
    SERVICE = SERVICE
    service: Incomplete
    characteristics: Incomplete
    def __init__(self, temperature: bool = False, humidity: bool = False, pressure: bool = False, uv_index: bool = False) -> None: ...
    def update(self, temperature=None, humidity=None, pressure=None, uv_index=None) -> None: ...
