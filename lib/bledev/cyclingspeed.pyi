# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Cycling Speed and Cadence Service (0x1816): a wheel and crank sensor for cycling apps."""
from . import Characteristic as Characteristic, Service as Service, UUID as UUID
from collections.abc import Callable

SERVICE: UUID
CSC_MEASUREMENT: UUID
CSC_FEATURE: UUID
SENSOR_LOCATION: UUID
SC_CONTROL_POINT: UUID
REQUEST_SUPPORTED_LOCATIONS: int
RESPONSE: int

def encode_measurement(
    wheel_revolutions: int | None = None,
    wheel_time_s: float | None = None,
    crank_revolutions: int | None = None,
    crank_time_s: float | None = None,
) -> bytes:
    """The CSC Measurement bytes for the data you pass (each count with its time)."""

class CyclingSpeedCadence:
    """A Cycling Speed and Cadence Service."""

    SERVICE = SERVICE
    service: Service
    characteristic: Characteristic
    def __init__(
        self,
        wheel: bool = True,
        crank: bool = True,
        location: int | None = None,
        locations: tuple[int, ...] | list[int] = (),
        on_set_cumulative: Callable[[int], bool | None] | None = None,
    ) -> None: ...
    def update(
        self,
        wheel_revolutions: int | None = None,
        wheel_time_s: float | None = None,
        crank_revolutions: int | None = None,
        crank_time_s: float | None = None,
    ) -> None:
        """Send a measurement to every central subscribed to it."""
    async def run(self) -> None:
        """Answer the SC Control Point, forever. Run it as a task."""
