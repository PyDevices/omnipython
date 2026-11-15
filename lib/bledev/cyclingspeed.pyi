# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
from . import Characteristic as Characteristic, Service as Service, UUID as UUID
from ._sig import INVALID_PARAMETER as INVALID_PARAMETER, OP_CODE_NOT_SUPPORTED as OP_CODE_NOT_SUPPORTED, SET_CUMULATIVE_VALUE as SET_CUMULATIVE_VALUE, SUCCESS as SUCCESS, check_location as check_location, event_time as event_time, serve_control_point as serve_control_point
from _typeshed import Incomplete

SERVICE: Incomplete
CSC_MEASUREMENT: Incomplete
CSC_FEATURE: Incomplete
SENSOR_LOCATION: Incomplete
SC_CONTROL_POINT: Incomplete
REQUEST_SUPPORTED_LOCATIONS: int
RESPONSE: int

def encode_measurement(wheel_revolutions=None, wheel_time_s=None, crank_revolutions=None, crank_time_s=None): ...

class CyclingSpeedCadence:
    SERVICE = SERVICE
    service: Incomplete
    characteristic: Incomplete
    def __init__(self, wheel: bool = True, crank: bool = True, location=None, locations=(), on_set_cumulative=None) -> None: ...
    def update(self, wheel_revolutions=None, wheel_time_s=None, crank_revolutions=None, crank_time_s=None) -> None: ...
    async def run(self) -> None: ...
