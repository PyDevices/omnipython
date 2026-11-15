# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Wi-Fi setup over BLE with the Improv standard (https://www.improv-wifi.com/ble/)."""
from . import BLE, BLEError, ClientCharacteristic, Connection, Device, Service, UUID
from collections.abc import Awaitable, Callable, Iterable
from typing import Any
from typing_extensions import Self

SERVICE: UUID
STATE: UUID
ERROR: UUID
RPC: UUID
RESULT: UUID
CAPABILITIES: UUID
SERVICE_DATA: UUID
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
    """The device reported an Improv error. `code` is one of `ERROR_*`."""

    code: int
    def __init__(self, code: int, message: str | None = None) -> None: ...

def checksum(data: Iterable[int]) -> int:
    """The standard's checksum: the sum of every byte, keeping the low byte."""
def pack(command: int, *strings: str | bytes | bytearray | memoryview) -> bytes:
    """An RPC command or result: `command, length, (len, bytes)..., checksum`."""
def packet_length(buffer: bytes | bytearray | memoryview) -> int | None:
    """The full length of the packet that starts `buffer`, or `None` until two bytes are in."""
def unpack(packet: bytes | bytearray | memoryview) -> tuple[int, list[bytes]]:
    """`(command, [bytes, ...])` from one whole packet. Raises `ImprovError`."""
def service_data(state: int, capabilities: int) -> bytes:
    """The six bytes the advertisement carries under `SERVICE_DATA`."""
async def wifi_connect(ssid: str, password: str, timeout_ms: int = 20000) -> str | None:
    """Join `ssid` with MicroPython's `network.WLAN`; the IP address, or `None`."""
def wifi_scan() -> list[tuple[str, int, bool]]:
    """`[(ssid, rssi, secured), ...]` from `network.WLAN.scan()`, strongest first."""

class Server:
    """The Improv service on a peripheral adapter."""

    ble: BLE
    name: str
    redirect: str | None
    capabilities: int
    state: int
    error: int
    url: str | None
    ip: str | None
    service: Service
    def __init__(
        self,
        ble: BLE,
        name: str = 'improv',
        *,
        join: Callable[[str, str], Awaitable[str | None]] | None = None,
        redirect: str | None = 'http://{ip}/',
        on_join: Callable[[str, str, str], Any] | None = None,
        require_authorization: bool = False,
        identify: Callable[[], Any] | None = None,
        scan: Callable[[], Iterable[tuple[str, int, bool]]] | None = None,
        device_info: Iterable[str] | None = None,
    ) -> None: ...
    def authorize(self) -> None:
        """Mark the device authorized for `AUTHORIZATION_MS` (from a button press)."""
    async def serve(self, timeout_ms: int | None = None) -> str | None:
        """Advertise until a client provisions the device; return the redirect URL (or IP)."""
    async def session(self, connection: Connection) -> bool:
        """Serve one connected client. True once the device is provisioned."""

async def serve(
    ble: BLE,
    name: str = 'improv',
    *,
    timeout_ms: int | None = None,
    join: Callable[[str, str], Awaitable[str | None]] | None = None,
    redirect: str | None = 'http://{ip}/',
    on_join: Callable[[str, str, str], Any] | None = None,
    require_authorization: bool = False,
    identify: Callable[[], Any] | None = None,
    scan: Callable[[], Iterable[tuple[str, int, bool]]] | None = None,
    device_info: Iterable[str] | None = None,
) -> str | None:
    """Serve Improv on `ble` until provisioned; return the redirect URL (or the IP)."""

class Client:
    """A connection to an Improv device. Use `connect`, or `provision`."""

    connection: Connection
    capabilities: int
    def __init__(self, connection: Connection, chars: Iterable[ClientCharacteristic]) -> None: ...
    @classmethod
    async def connect(cls, ble: BLE, name: str | None = None, *, device: Device | None = None, timeout_ms: int = 10000) -> Self:
        """Find the device (by `name`, or the first advertising Improv), connect, subscribe."""
    async def state(self) -> int:
        """The device's current `STATE_*`."""
    async def error(self) -> int:
        """The device's current `ERROR_*`."""
    async def close(self) -> None: ...
    async def send_wifi(self, ssid: str, password: str, timeout_ms: int = 60000) -> str:
        """Send credentials; return the redirect URL (`""` if the device sends none)."""
    async def device_info(self, timeout_ms: int = 5000) -> list[str]:
        """`[firmware, version, chip, device name, ...]` as strings."""
    async def identify(self) -> None: ...
    async def scan(self, timeout_ms: int = 20000) -> list[tuple[str, int, bool]]:
        """`[(ssid, rssi, secured), ...]` as the device sees them."""

async def provision(ble: BLE, ssid: str, password: str, name: str | None = None, *, device: Device | None = None, timeout_ms: int = 60000) -> str:
    """Connect to an Improv device, send it `ssid` and `password`, and return its redirect URL."""
