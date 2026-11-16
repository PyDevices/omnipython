# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""BLE keyboards and game controllers, both ways: HID over GATT (HOGP)."""
from . import BLE, Characteristic, Connection, Device as _BleDevice, Service, UUID
from .hidreport import Decoder, ReportMap, _Event
from typing import Any
from typing_extensions import Self

__all__ = ['ticks_diff', 'ticks_us', 'report_map', 'identity', 'Peripheral', 'Host', 'connect']

HID_SERVICE: UUID
HID_INFORMATION: UUID
REPORT_MAP: UUID
HID_CONTROL_POINT: UUID
REPORT: UUID
PROTOCOL_MODE: UUID
REPORT_REFERENCE: UUID
INSPECT_SERVICE: UUID
APPEARANCE_HID: int
APPEARANCE_KEYBOARD: int
APPEARANCE_MOUSE: int
APPEARANCE_GAMEPAD: int
KEYBOARD_ID: int
MOUSE_ID: int
CONSUMER_ID: int
GAMEPAD_ID: int
VOLUME_UP: int
VOLUME_DOWN: int
MUTE: int
PLAY_PAUSE: int
NEXT_TRACK: int
PREV_TRACK: int
MOD_LCTRL: int
MOD_LSHIFT: int
MOD_LALT: int
MOD_LGUI: int
MOD_RCTRL: int
MOD_RSHIFT: int
MOD_RALT: int
MOD_RGUI: int
KEYBOARD_MAP: bytes
MOUSE_MAP: bytes
CONSUMER_MAP: bytes
GAMEPAD_MAP: bytes
SEND_WAIT_MS: int

def ticks_us() -> int: ...
def ticks_diff(a: int, b: int) -> int: ...
def report_map(keyboard: bool = True, mouse: bool = True, consumer: bool = True, gamepad: bool = False) -> bytes:
    """The Report Map a board serves for this set of functions, always the same bytes."""
def identity(keyboard: bool = True, mouse: bool = True, consumer: bool = True, gamepad: bool = False) -> tuple[str, int, int]:
    """`(name, appearance, product_id)` for a set of functions, derived the same way every time."""

class Device:
    """One HID function of a `Peripheral`, in CircuitPython's `usb_hid.Device` shape."""

    report_id: int
    usage_page: int
    usage: int
    in_report_length: int
    out_report_length: int
    def __init__(
        self,
        owner: Peripheral,
        characteristic: Characteristic,
        report_id: int,
        usage_page: int,
        usage: int,
        in_report_length: int,
        out_report_length: int = 0,
    ) -> None: ...
    def send_report(self, report: bytes | bytearray | memoryview, report_id: int | None = None) -> None:
        """Send one input report to the connected host, now."""
    def get_last_received_report(self, report_id: int | None = None) -> bytes | None:
        """The last output report the host wrote (the keyboard's LEDs), or `None`."""

class Peripheral:
    """A board that is a BLE keyboard, mouse, media remote and gamepad (any of them)."""

    ble: BLE
    name: str
    appearance: int
    report_map: bytes
    connection: Connection | None
    last_send_us: int | None
    service_uuid: UUID
    keyboard: Device | None
    devices: tuple[Device, ...]
    battery: Characteristic
    services: tuple[Service, Service, Service]
    def __init__(
        self,
        ble: BLE,
        *,
        keyboard: bool = True,
        mouse: bool = True,
        consumer: bool = True,
        gamepad: bool = False,
        name: str | None = None,
        encrypted: bool = False,
        battery: int = 100,
        manufacturer: str = 'PyDevices',
        service_uuid: UUID | int | str | bytes = ...,
    ) -> None: ...
    async def serve(self, timeout_ms: int | None = None) -> Connection:
        """Advertise until a host connects, and return the connection."""
    async def leds(self, timeout_ms: int | None = None) -> tuple[int, bytes]:
        """The next LED report the host writes, as `(ticks_us, data)`."""
    def close(self) -> None: ...

class Host:
    """One connected HID device, as a stream of OmniPython events."""

    connection: Connection
    service_uuid: UUID
    bond: bool
    instance_id: int
    report_map: ReportMap | None
    decoder: Decoder | None
    paired: bool
    last_report_us: int | None
    def __init__(
        self,
        connection: Connection,
        *,
        bond: bool = True,
        instance_id: int = 0,
        queue_limit: int = 256,
        service_uuid: UUID | int | str | bytes = ...,
    ) -> None: ...
    async def start(self, timeout_ms: int = 5000) -> Self: ...
    def poll(self) -> list[_Event]:
        """Every event decoded so far, as a list (possibly empty). Never waits."""
    async def events(self, timeout_ms: int | None = None) -> list[_Event]:
        """Wait for at least one event, and return every one waiting."""
    async def set_leds(self, bits: int) -> None:
        """Write the keyboard's LED report (Num Lock is bit 0), if it has one."""
    async def close(self) -> None: ...

async def connect(
    ble: BLE,
    name: str | None = None,
    *,
    device: _BleDevice | None = None,
    timeout_ms: int = 10000,
    bond: bool = True,
    instance_id: int = 0,
    service_uuid: UUID | int | str | bytes = ...,
    **options: Any,
) -> Host:
    """Find a BLE HID device (by `name`, or any advertising the HID service), connect, and return a started `Host`."""
