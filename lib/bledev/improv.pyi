# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
from . import BLEError as BLEError, BLETimeoutError as BLETimeoutError, BusyError as BusyError, Characteristic as Characteristic, DisconnectedError as DisconnectedError, MAX_MTU as MAX_MTU, Service as Service, UUID as UUID, sleep_ms as sleep_ms, wait_ms as wait_ms
from _typeshed import Incomplete

SERVICE: Incomplete
STATE: Incomplete
ERROR: Incomplete
RPC: Incomplete
RESULT: Incomplete
CAPABILITIES: Incomplete
SERVICE_DATA: Incomplete
STATE_AUTHORIZATION_REQUIRED: int
STATE_AUTHORIZED: int
STATE_PROVISIONING: int
STATE_PROVISIONED: int
ERROR_NONE: int
ERROR_INVALID_RPC: int
ERROR_UNKNOWN_RPC: int
ERROR_UNABLE_TO_CONNECT: int
ERROR_NOT_AUTHORIZED: int
ERROR_BAD_HOSTNAME: int
ERROR_UNKNOWN: int
CMD_WIFI_SETTINGS: int
CMD_IDENTIFY: int
CMD_DEVICE_INFO: int
CMD_WIFI_SCAN: int
CMD_HOSTNAME: int
CMD_DEVICE_NAME: int
CAP_IDENTIFY: int
CAP_DEVICE_INFO: int
CAP_WIFI_SCAN: int
CAP_HOSTNAME: int
AUTHORIZATION_MS: int

class ImprovError(BLEError):
    code: Incomplete
    def __init__(self, code, message=None) -> None: ...

def checksum(data): ...
def pack(command, *strings): ...
def packet_length(buffer): ...
def unpack(packet): ...
def service_data(state, capabilities): ...
async def wifi_connect(ssid, password, timeout_ms: int = 20000): ...
def wifi_scan(): ...

class Server:
    ble: Incomplete
    name: Incomplete
    redirect: Incomplete
    capabilities: Incomplete
    state: Incomplete
    error: Incomplete
    url: Incomplete
    ip: Incomplete
    service: Incomplete
    def __init__(self, ble, name: str = 'improv', *, join=None, redirect: str = 'http://{ip}/', on_join=None, require_authorization: bool = False, identify=None, scan=None, device_info=None) -> None: ...
    def authorize(self) -> None: ...
    async def serve(self, timeout_ms=None): ...
    async def session(self, connection): ...

async def serve(ble, name: str = 'improv', *, timeout_ms=None, **options): ...

class Client:
    connection: Incomplete
    capabilities: int
    def __init__(self, connection, chars) -> None: ...
    @classmethod
    async def connect(cls, ble, name=None, *, device=None, timeout_ms: int = 10000): ...
    async def state(self): ...
    async def error(self): ...
    async def close(self) -> None: ...
    async def send_wifi(self, ssid, password, timeout_ms: int = 60000): ...
    async def device_info(self, timeout_ms: int = 5000): ...
    async def identify(self) -> None: ...
    async def scan(self, timeout_ms: int = 20000): ...

async def provision(ble, ssid, password, name=None, *, device=None, timeout_ms: int = 60000): ...
