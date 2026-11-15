# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
from . import Characteristic as Characteristic, Service as Service, UUID as UUID
from _typeshed import Incomplete

SERVICE: Incomplete
SYSTEM_ID: Incomplete
MODEL_NUMBER: Incomplete
SERIAL_NUMBER: Incomplete
FIRMWARE_REVISION: Incomplete
HARDWARE_REVISION: Incomplete
SOFTWARE_REVISION: Incomplete
MANUFACTURER_NAME: Incomplete
PNP_ID: Incomplete
SOURCE_BLUETOOTH_SIG: int
SOURCE_USB: int

class DeviceInformation:
    SERVICE = SERVICE
    service: Incomplete
    characteristics: Incomplete
    def __init__(self, manufacturer=None, model=None, serial=None, hardware=None, firmware=None, software=None, system_id=None, pnp_id=None) -> None: ...
