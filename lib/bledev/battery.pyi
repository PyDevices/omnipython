# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
from . import Characteristic as Characteristic, Service as Service, UUID as UUID
from _typeshed import Incomplete

SERVICE: Incomplete
BATTERY_LEVEL: Incomplete

class Battery:
    SERVICE = SERVICE
    service: Incomplete
    characteristic: Incomplete
    def __init__(self, level: int = 100) -> None: ...
    @property
    def level(self): ...
    def set_level(self, level) -> None: ...
