# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
from . import Characteristic as Characteristic, Service as Service, UUID as UUID
from ._sig import INVALID_PARAMETER as INVALID_PARAMETER, OP_CODE_NOT_SUPPORTED as OP_CODE_NOT_SUPPORTED, SET_CUMULATIVE_VALUE as SET_CUMULATIVE_VALUE, SUCCESS as SUCCESS, check_location as check_location, serve_control_point as serve_control_point
from _typeshed import Incomplete

SERVICE: Incomplete
RSC_MEASUREMENT: Incomplete
RSC_FEATURE: Incomplete
SENSOR_LOCATION: Incomplete
SC_CONTROL_POINT: Incomplete
REQUEST_SUPPORTED_LOCATIONS: int
RESPONSE: int

def encode_measurement(speed_mps, cadence, stride_m=None, distance_m=None, running=None): ...

class RunningSpeedCadence:
    SERVICE = SERVICE
    service: Incomplete
    characteristic: Incomplete
    def __init__(self, stride_length: bool = False, total_distance: bool = False, running_status: bool = False, location=None, locations=(), on_set_cumulative=None) -> None: ...
    def update(self, speed_mps, cadence, stride_m=None, distance_m=None, running=None) -> None: ...
    async def run(self) -> None: ...
