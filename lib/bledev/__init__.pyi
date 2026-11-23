# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
from collections.abc import Awaitable, Callable, Generator, Iterable
from types import TracebackType
from typing import Any, Literal, TypeVar
from typing_extensions import Self

_T = TypeVar("_T")
_Bytes = bytes | bytearray | memoryview
_UUIDLike = UUID | int | str | bytes | bytearray | memoryview
_Passkey = int | str | Callable[[], int | str | None | Awaitable[int | str | None]]

__version__: str
FLAG_READ: int
FLAG_WRITE_NO_RESPONSE: int
FLAG_WRITE: int
FLAG_NOTIFY: int
FLAG_INDICATE: int
DEFAULT_MTU: int
MAX_MTU: int
ADDR_PUBLIC: int
ADDR_RANDOM: int
ADDR_MODE_PUBLIC: int
ADDR_MODE_RANDOM: int
ADDR_MODE_RPA: int
ADDR_MODE_NRPA: int

class BLEError(Exception):
    """Base of every error bledev raises."""

class UnsupportedError(BLEError):
    """This backend cannot do that: a role it can't take, or a missing feature."""

class DisconnectedError(BLEError):
    """The connection dropped, or was already closed, before the operation finished."""

class BLETimeoutError(BLEError):
    """An operation given `timeout_ms` did not finish in time."""

class BusyError(BLEError):
    """The controller's transmit buffers are full. Wait a moment and send again."""

INSUFFICIENT_AUTHENTICATION: int
INSUFFICIENT_ENCRYPTION: int

class PairingError(BLEError):
    """Pairing failed: a wrong passkey, a refusal, or a peer that lost its keys."""

STALE_BOND: str
NEEDS_PAIRING: tuple[int, int]

class GattError(BLEError):
    """The peer answered a GATT request with an error `status`."""

    status: int
    def __init__(self, status: int, message: str | None = None) -> None: ...

async def sleep_ms(ms: float) -> None:
    """`asyncio.sleep_ms` on every interpreter."""

async def wait_ms(awaitable: Awaitable[_T], timeout_ms: float | None, what: str = 'operation') -> _T:
    """Await `awaitable`, raising `BLETimeoutError` after `timeout_ms` (`None` waits forever)."""

class UUID:
    """A Bluetooth UUID, the same value on every host."""

    def __init__(self, value: _UUIDLike) -> None: ...
    @property
    def short(self) -> int | None: ...
    def to_bytes(self) -> bytes: ...
    def __bytes__(self) -> bytes: ...
    def __eq__(self, other: object) -> bool: ...
    def __ne__(self, other: object) -> bool: ...
    def __hash__(self) -> int: ...

ADV_TYPE_FLAGS: int
ADV_TYPE_UUID16_INCOMPLETE: int
ADV_TYPE_UUID16_COMPLETE: int
ADV_TYPE_UUID32_INCOMPLETE: int
ADV_TYPE_UUID32_COMPLETE: int
ADV_TYPE_UUID128_INCOMPLETE: int
ADV_TYPE_UUID128_COMPLETE: int
ADV_TYPE_SHORT_NAME: int
ADV_TYPE_NAME: int
ADV_TYPE_SERVICE_DATA16: int
ADV_TYPE_APPEARANCE: int
ADV_TYPE_SERVICE_DATA32: int
ADV_TYPE_SERVICE_DATA128: int
ADV_TYPE_MANUFACTURER: int
ADV_PAYLOAD_MAX: int

def pack_advertisement(
    name: str | bytes | None = None,
    services: Iterable[_UUIDLike] | None = None,
    appearance: int = 0,
    manufacturer: tuple[int, _Bytes] | None = None,
    service_data: Iterable[tuple[_UUIDLike, _Bytes]] | None = None,
) -> tuple[bytes, bytes]:
    """Build `(adv_data, resp_data)`, in aioble's field order."""
def decode_fields(*payloads: _Bytes | None) -> Generator[tuple[int, bytes], None, None]:
    """Yield `(adv_type, value)` for every field in the given payloads."""
def decode_advertisement(*payloads: _Bytes | None) -> tuple[str | None, list[UUID], int, list[tuple[int, bytes]]]:
    """`(name, services, appearance, manufacturer)` from raw payloads."""
def decode_service_data(*payloads: _Bytes | None) -> list[tuple[UUID, bytes]]:
    """`[(UUID, data), ...]` from the service-data fields of raw payloads."""

class BLE:
    """One radio. Backends subclass this; apps receive one from a board config."""

    backend: str
    def capabilities(self) -> dict[str, Any]: ...
    def config(self, *names: str, **settings: Any) -> Any: ...
    def close(self) -> None: ...
    def register_services(self, *services: Service) -> None: ...
    async def advertise(
        self,
        interval_us: int = 100000,
        *,
        name: str | bytes | None = None,
        services: Iterable[_UUIDLike] | None = None,
        appearance: int = 0,
        manufacturer: tuple[int, _Bytes] | None = None,
        connectable: bool = True,
        timeout_ms: int | None = None,
        service_data: Iterable[tuple[_UUIDLike, _Bytes]] | None = None,
    ) -> Connection: ...
    def scan(self, duration_ms: int, *, active: bool = False, interval_us: int | None = None, window_us: int | None = None) -> Scanner: ...
    async def find(self, name: str | None = None, service: _UUIDLike | None = None, *, timeout_ms: int = 10000, active: bool = True) -> Device: ...

class Service:
    """A GATT service you serve."""

    uuid: UUID
    characteristics: list[Characteristic]
    def __init__(self, uuid: _UUIDLike) -> None: ...

class Characteristic:
    """A characteristic in a `Service` you serve."""

    service: Service
    uuid: UUID
    flags: int
    capture: bool
    max_len: int
    encrypted: bool
    authenticated: bool
    descriptors: list[Descriptor]
    def __init__(
        self,
        service: Service,
        uuid: _UUIDLike,
        read: bool = False,
        write: bool = False,
        write_no_response: bool = False,
        notify: bool = False,
        indicate: bool = False,
        initial: _Bytes | None = None,
        capture: bool = False,
        max_len: int = 20,
        encrypted: bool = False,
        authenticated: bool = False,
    ) -> None: ...
    def read(self) -> bytes: ...
    def write(self, data: _Bytes, send_update: bool = False) -> None: ...
    def notify(self, connection: Connection, data: _Bytes | None = None) -> Any: ...
    async def indicate(self, connection: Connection, data: _Bytes | None = None, timeout_ms: int = 1000) -> Any: ...
    async def written(self, timeout_ms: int | None = None) -> Connection | tuple[Connection, bytes]: ...

class Descriptor:
    """A read-only descriptor on a `Characteristic` you serve."""

    characteristic: Characteristic
    uuid: UUID
    value: bytes
    def __init__(self, characteristic: Characteristic, uuid: _UUIDLike, initial: _Bytes = b'') -> None: ...

class Device:
    """A peer found by a scan, or named by address. `connect()` it."""

    addr: bytes | None
    address: str
    addr_type: int
    name: str | None
    native: Any
    def __init__(self, ble: BLE, address: str | bytes | bytearray, addr_type: int = ..., name: str | None = None, native: Any = None) -> None: ...
    def addr_hex(self) -> str: ...
    def __eq__(self, other: object) -> bool: ...
    def __ne__(self, other: object) -> bool: ...
    def __hash__(self) -> int: ...
    async def connect(self, timeout_ms: int = 10000, **options: Any) -> Connection: ...

class ScanResult:
    """One device's advertisement, as aioble reports it."""

    device: Device
    rssi: int | None
    appearance: int
    connectable: bool
    def __init__(
        self,
        device: Device,
        rssi: int | None = None,
        name: str | None = None,
        services: Iterable[_UUIDLike] = (),
        appearance: int = 0,
        manufacturer: Iterable[tuple[int, bytes]] = (),
        connectable: bool = True,
        service_data: Iterable[tuple[_UUIDLike, _Bytes]] = (),
    ) -> None: ...
    def name(self) -> str | None: ...
    def services(self) -> list[UUID]: ...
    def manufacturer(self, filter: int | None = None) -> list[tuple[int, bytes]]: ...
    def service_data(self, uuid: _UUIDLike | None = None) -> list[tuple[UUID, bytes]]: ...

class Scanner:
    """What `ble.scan()` returns: an async context manager and async iterator."""

    duration_ms: int
    active: bool
    interval_us: int | None
    window_us: int | None
    def __init__(self, ble: BLE, duration_ms: int, active: bool = False, interval_us: int | None = None, window_us: int | None = None) -> None: ...
    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None: ...
    async def cancel(self) -> None: ...
    def __aiter__(self) -> Self: ...
    async def __anext__(self) -> ScanResult: ...

class _Discovery:
    def __init__(self, fetch: Callable[[], Awaitable[Iterable[Any]]]) -> None: ...
    def __aiter__(self) -> Self: ...
    async def __anext__(self) -> Any: ...

class Connection:
    """A live link to one peer, from either side."""

    device: Device
    role: Literal["central", "peripheral"]
    def __init__(self, ble: BLE, device: Device, role: Literal["central", "peripheral"]) -> None: ...
    @property
    def mtu(self) -> int: ...
    def is_connected(self) -> bool: ...
    async def disconnect(self, timeout_ms: int = 2000) -> None: ...
    async def disconnected(self, timeout_ms: int | None = None) -> None: ...
    @property
    def encrypted(self) -> bool: ...
    async def pair(self, bond: bool = True, timeout_ms: int = 30000, passkey: _Passkey | None = None) -> None: ...
    @property
    def authenticated(self) -> bool: ...
    async def unpair(self) -> None: ...
    async def exchange_mtu(self, mtu: int | None = None, timeout_ms: int = 1000) -> int: ...
    def services(self, uuid: _UUIDLike | None = None, timeout_ms: int = 2000) -> _Discovery: ...
    async def service(self, uuid: _UUIDLike, timeout_ms: int = 2000) -> ClientService | None: ...
    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None: ...

class ClientService:
    """A service on the peer, found by discovery."""

    connection: Connection
    uuid: UUID
    def __init__(self, connection: Connection, uuid: _UUIDLike) -> None: ...
    def characteristics(self, uuid: _UUIDLike | None = None, timeout_ms: int = 2000) -> _Discovery: ...
    async def characteristic(self, uuid: _UUIDLike, timeout_ms: int = 2000) -> ClientCharacteristic | None: ...

class ClientCharacteristic:
    """A characteristic on the peer. `properties` holds its `FLAG_*` bits."""

    arrival: int | None
    service: ClientService
    connection: Connection
    uuid: UUID
    properties: int
    def __init__(self, service: ClientService, uuid: _UUIDLike, properties: int) -> None: ...
    async def read(self, timeout_ms: int = 1000) -> bytes: ...
    def descriptors(self, uuid: _UUIDLike | None = None, timeout_ms: int = 2000) -> _Discovery: ...
    async def descriptor(self, uuid: _UUIDLike, timeout_ms: int = 2000) -> ClientDescriptor | None: ...
    async def write(self, data: _Bytes, response: bool | None = None, timeout_ms: int = 1000) -> None: ...
    async def subscribe(self, notify: bool = True, indicate: bool = False) -> None: ...
    async def notified(self, timeout_ms: int | None = None) -> bytes: ...
    async def indicated(self, timeout_ms: int | None = None) -> bytes: ...

class ClientDescriptor:
    """A descriptor on the peer, found by `ClientCharacteristic.descriptors`."""

    characteristic: ClientCharacteristic
    connection: Connection
    uuid: UUID
    def __init__(self, characteristic: ClientCharacteristic, uuid: _UUIDLike) -> None: ...
    async def read(self, timeout_ms: int = 1000) -> bytes: ...

def is_adapter(obj: object) -> bool:
    """True for a bledev `BLE`; False for a raw `bluetooth.BLE` or anything else."""
async def passkey_value(passkey: _Passkey | None) -> int | None: ...
def advertised_name(ble: BLE, name: str | None, default: Callable[[], str]) -> str | None:
    """The name a profile's `serve()` advertises: `name`, else `default()`, else `None` on a host that can't choose (Windows)."""
async def connect_and_set_up(
    ble: BLE,
    setup: Callable[[Connection], Awaitable[_T]],
    *,
    name: str | None = None,
    service: _UUIDLike | None = None,
    device: Device | None = None,
    timeout_ms: int = 10000,
    attempts: int = 3,
    setup_timeout_ms: int = 4000,
    **options: Any,
) -> tuple[Connection, _T]:
    """Find a device, connect, and run `await setup(connection)`, retrying a link that comes up dead."""
