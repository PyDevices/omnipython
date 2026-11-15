# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Cycling Power Service (0x1818): a power meter for cycling apps."""
from . import Characteristic as Characteristic, Service as Service, UUID as UUID
from collections.abc import Callable

SERVICE: UUID
CYCLING_POWER_MEASUREMENT: UUID
CYCLING_POWER_FEATURE: UUID
SENSOR_LOCATION: UUID
CYCLING_POWER_CONTROL_POINT: UUID
UPDATE_SENSOR_LOCATION: int
REQUEST_SUPPORTED_LOCATIONS: int
RESPONSE: int

def encode_measurement(
    power: float,
    pedal_balance: float | None = None,
    accumulated_torque: float | None = None,
    crank_torque: bool = False,
    wheel_revolutions: int | None = None,
    wheel_time_s: float | None = None,
    crank_revolutions: int | None = None,
    crank_time_s: float | None = None,
    energy_kj: int | None = None,
) -> bytes:
    """The Cycling Power Measurement bytes for the data you pass."""

class CyclingPower:
    """A Cycling Power Service."""

    SERVICE = SERVICE
    service: Service
    characteristic: Characteristic
    def __init__(
        self,
        pedal_balance: bool = False,
        torque: bool = False,
        crank_torque: bool = False,
        wheel: bool = False,
        crank: bool = False,
        energy: bool = False,
        location: int = 0,
        locations: tuple[int, ...] | list[int] = (),
        on_set_cumulative: Callable[[int], bool | None] | None = None,
    ) -> None: ...
    def update(
        self,
        power: float,
        pedal_balance: float | None = None,
        accumulated_torque: float | None = None,
        wheel_revolutions: int | None = None,
        wheel_time_s: float | None = None,
        crank_revolutions: int | None = None,
        crank_time_s: float | None = None,
        energy_kj: int | None = None,
    ) -> None:
        """Send a measurement to every central subscribed to it."""
    async def run(self) -> None:
        """Answer the Cycling Power Control Point, forever. Run it as a task."""
