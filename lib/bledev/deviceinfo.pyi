# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Device Information Service (0x180A): tell a phone or laptop what this device is."""
from . import Characteristic as Characteristic, Service as Service, UUID as UUID
from collections.abc import Iterable
from typing import Any

SERVICE: UUID
SYSTEM_ID: UUID
MODEL_NUMBER: UUID
SERIAL_NUMBER: UUID
FIRMWARE_REVISION: UUID
HARDWARE_REVISION: UUID
SOFTWARE_REVISION: UUID
MANUFACTURER_NAME: UUID
PNP_ID: UUID
SOURCE_BLUETOOTH_SIG: int
SOURCE_USB: int

class DeviceInformation:
    """A Device Information Service with the fields you give it."""

    SERVICE = SERVICE
    service: Service
    characteristics: dict[str, Characteristic]
    def __init__(
        self,
        manufacturer: Any = None,
        model: Any = None,
        serial: Any = None,
        hardware: Any = None,
        firmware: Any = None,
        software: Any = None,
        system_id: bytes | bytearray | memoryview | None = None,
        pnp_id: tuple[int, int, int, int] | None = None,
    ) -> None: ...
