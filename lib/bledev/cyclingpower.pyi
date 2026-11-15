# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
from . import Characteristic as Characteristic, Service as Service, UUID as UUID
from ._sig import INVALID_PARAMETER as INVALID_PARAMETER, OP_CODE_NOT_SUPPORTED as OP_CODE_NOT_SUPPORTED, SET_CUMULATIVE_VALUE as SET_CUMULATIVE_VALUE, SUCCESS as SUCCESS, check_location as check_location, event_time as event_time, serve_control_point as serve_control_point
from _typeshed import Incomplete

SERVICE: Incomplete
CYCLING_POWER_MEASUREMENT: Incomplete
CYCLING_POWER_FEATURE: Incomplete
SENSOR_LOCATION: Incomplete
CYCLING_POWER_CONTROL_POINT: Incomplete
UPDATE_SENSOR_LOCATION: int
REQUEST_SUPPORTED_LOCATIONS: int
RESPONSE: int

def encode_measurement(power, pedal_balance=None, accumulated_torque=None, crank_torque: bool = False, wheel_revolutions=None, wheel_time_s=None, crank_revolutions=None, crank_time_s=None, energy_kj=None): ...

class CyclingPower:
    SERVICE = SERVICE
    service: Incomplete
    characteristic: Incomplete
    def __init__(self, pedal_balance: bool = False, torque: bool = False, crank_torque: bool = False, wheel: bool = False, crank: bool = False, energy: bool = False, location: int = 0, locations=(), on_set_cumulative=None) -> None: ...
    def update(self, power, pedal_balance=None, accumulated_torque=None, wheel_revolutions=None, wheel_time_s=None, crank_revolutions=None, crank_time_s=None, energy_kj=None) -> None: ...
    async def run(self) -> None: ...
