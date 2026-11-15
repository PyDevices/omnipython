# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
from _typeshed import Incomplete
from time import ticks_diff as ticks_diff, ticks_us as ticks_us

__all__ = ['ticks_diff', 'ticks_us', 'report_map', 'identity', 'Peripheral', 'Host', 'connect']

def report_map(keyboard: bool = True, mouse: bool = True, consumer: bool = True, gamepad: bool = False): ...
def identity(keyboard: bool = True, mouse: bool = True, consumer: bool = True, gamepad: bool = False): ...

class Device:
    report_id: Incomplete
    usage_page: Incomplete
    usage: Incomplete
    in_report_length: Incomplete
    out_report_length: Incomplete
    def __init__(self, owner, characteristic, report_id, usage_page, usage, in_report_length, out_report_length: int = 0) -> None: ...
    def send_report(self, report, report_id=None) -> None: ...
    def get_last_received_report(self, report_id=None): ...

class Peripheral:
    ble: Incomplete
    name: Incomplete
    report_map: Incomplete
    connection: Incomplete
    last_send_us: Incomplete
    service_uuid: Incomplete
    keyboard: Incomplete
    devices: Incomplete
    battery: Incomplete
    services: Incomplete
    def __init__(self, ble, *, keyboard: bool = True, mouse: bool = True, consumer: bool = True, gamepad: bool = False, name=None, encrypted: bool = False, battery: int = 100, manufacturer: str = 'PyDevices', service_uuid=...) -> None: ...
    async def serve(self, timeout_ms=None): ...
    async def leds(self, timeout_ms=None): ...
    def close(self) -> None: ...

class Host:
    connection: Incomplete
    service_uuid: Incomplete
    bond: Incomplete
    instance_id: Incomplete
    report_map: Incomplete
    decoder: Incomplete
    paired: bool
    last_report_us: Incomplete
    def __init__(self, connection, *, bond: bool = True, instance_id: int = 0, queue_limit: int = 256, service_uuid=...) -> None: ...
    async def start(self, timeout_ms: int = 5000): ...
    def poll(self): ...
    async def events(self, timeout_ms=None): ...
    async def set_leds(self, bits): ...
    async def close(self) -> None: ...

async def connect(ble, name=None, *, device=None, timeout_ms: int = 10000, bond: bool = True, instance_id: int = 0, service_uuid=..., **options): ...
