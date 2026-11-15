# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Running Speed and Cadence Service (0x1814): a foot pod for running apps."""
from . import Characteristic as Characteristic, Service as Service, UUID as UUID
from collections.abc import Callable

SERVICE: UUID
RSC_MEASUREMENT: UUID
RSC_FEATURE: UUID
SENSOR_LOCATION: UUID
SC_CONTROL_POINT: UUID
REQUEST_SUPPORTED_LOCATIONS: int
RESPONSE: int

def encode_measurement(
    speed_mps: float,
    cadence: int,
    stride_m: float | None = None,
    distance_m: float | None = None,
    running: bool | None = None,
) -> bytes:
    """The RSC Measurement bytes: speed in 1/256 m/s, cadence, stride in cm, distance in 1/10 m."""

class RunningSpeedCadence:
    """A Running Speed and Cadence Service."""

    SERVICE = SERVICE
    service: Service
    characteristic: Characteristic
    def __init__(
        self,
        stride_length: bool = False,
        total_distance: bool = False,
        running_status: bool = False,
        location: int | None = None,
        locations: tuple[int, ...] | list[int] = (),
        on_set_cumulative: Callable[[float], bool | None] | None = None,
    ) -> None: ...
    def update(
        self,
        speed_mps: float,
        cadence: int,
        stride_m: float | None = None,
        distance_m: float | None = None,
        running: bool | None = None,
    ) -> None:
        """Send a measurement to every central subscribed to it."""
    async def run(self) -> None:
        """Answer the SC Control Point, forever. Run it as a task."""
