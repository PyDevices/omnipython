# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""bledev.winrt's GATT server without Windows: stand-ins for WinRT that
behave the way Windows 11 does where it matters.

Windows raises its GATT events on its own threads, so the stand-in does too.
It hands the app a passing ABORTED with no error on every start, as Windows
does, refuses ``stop_advertising()`` on a provider that isn't advertising and
``update_advertising_parameters()`` on one that never started, and sends a
notification only to the subscribed client it names. A central here is a
test helper that reads, writes, subscribes and disconnects the way a board
does through Windows.
"""

import asyncio
import enum
import sys
import threading
import types
import unittest
import uuid as _uuid

import _env  # noqa: F401  (puts lib/ on sys.path)

RADIO = "TESTPC"


class Error(enum.IntEnum):
    SUCCESS = 0
    RADIO_NOT_AVAILABLE = 1


class Props(enum.IntFlag):
    READ = 2
    WRITE_WITHOUT_RESPONSE = 4
    WRITE = 8
    NOTIFY = 16
    INDICATE = 32


class Comm(enum.IntEnum):
    SUCCESS = 0
    UNREACHABLE = 1


class Protection(enum.IntEnum):
    PLAIN = 0
    AUTHENTICATION_REQUIRED = 1
    ENCRYPTION_REQUIRED = 2
    ENCRYPTION_AND_AUTHENTICATION_REQUIRED = 3


class AdStatus(enum.IntEnum):
    CREATED = 0
    STOPPED = 1
    STARTED = 2
    ABORTED = 3


class SessionStatus(enum.IntEnum):
    CLOSED = 0
    ACTIVE = 1


class WriteOption(enum.IntEnum):
    WRITE_WITH_RESPONSE = 0
    WRITE_WITHOUT_RESPONSE = 1


ProtocolError = types.SimpleNamespace(
    invalid_attribute_value_length=0x0D, invalid_offset=0x07, request_not_supported=0x06
)


def on_windows_thread(fn, *args):
    t = threading.Thread(target=fn, args=args)
    t.start()
    t.join()


class Buffer:
    def __init__(self, capacity):
        self._data = bytearray(capacity)
        self.length = 0

    def __buffer__(self, flags):
        return memoryview(self._data)

    def __bytes__(self):
        return bytes(self._data[: self.length])


class Params:
    def __init__(self):
        self.characteristic_properties = 0
        self.read_protection_level = Protection.PLAIN
        self.write_protection_level = Protection.PLAIN
        self.static_value = None
        self.is_connectable = False
        self.is_discoverable = False
        self.service_data = None


class Deferral:
    def __init__(self):
        self.done = threading.Event()

    def complete(self):
        self.done.set()


class Session:
    def __init__(self, device_id, mtu=247):
        self.device_id = types.SimpleNamespace(id=device_id)
        self.max_pdu_size = mtu
        self.handlers = []
        self.session_status = SessionStatus.ACTIVE

    def add_session_status_changed(self, handler):
        self.handlers.append(handler)


class Client:
    def __init__(self, session):
        self.session = session
        self.max_notification_size = session.max_pdu_size - 3
        self.received = []


class Request:
    def __init__(self, value=b"", option=WriteOption.WRITE_WITH_RESPONSE, offset=0):
        self.value = bytes(value)
        self.option = option
        self.offset = offset
        self.answer = None

    def respond(self):
        self.answer = "ok"

    def respond_with_value(self, buffer):
        self.answer = bytes(buffer)

    def respond_with_protocol_error(self, code):
        self.answer = ("error", code)


class Args:
    def __init__(self, session, request, delay=0):
        self.session = session
        self._request = request
        self._delay = delay
        self.deferral = None

    def get_deferral(self):
        self.deferral = Deferral()
        return self.deferral

    async def get_request_async(self):
        # Windows resolves each request on its own, so a later one can be
        # ready first.
        await asyncio.sleep(self._delay)
        return self._request


class LocalCharacteristic:
    def __init__(self, uuid, params):
        self.uuid = uuid
        self.params = params
        self.read_handlers = []
        self.write_handlers = []
        self.sub_handlers = []
        self.subscribed_clients = []
        self.descriptors = []
        self.fail_next = False
        self.slow = None

    def add_read_requested(self, h):
        self.read_handlers.append(h)

    def add_write_requested(self, h):
        self.write_handlers.append(h)

    def add_subscribed_clients_changed(self, h):
        self.sub_handlers.append(h)

    async def create_descriptor_async(self, uuid, params):
        self.descriptors.append((uuid, bytes(params.static_value)))
        return types.SimpleNamespace(error=Error.SUCCESS)

    async def notify_value_for_subscribed_client_async(self, buffer, client):
        if self.slow is not None:
            await self.slow.wait()
        if self.fail_next:
            self.fail_next = False
            return types.SimpleNamespace(status=Comm.UNREACHABLE)
        assert client in self.subscribed_clients, "Windows sends only to a subscribed client"
        client.received.append(bytes(buffer))
        return types.SimpleNamespace(status=Comm.SUCCESS)


class LocalService:
    def __init__(self, uuid):
        self.uuid = uuid
        self.characteristics = []

    async def create_characteristic_async(self, uuid, params):
        char = LocalCharacteristic(uuid, params)
        self.characteristics.append(char)
        return types.SimpleNamespace(error=Error.SUCCESS, characteristic=char)


class Provider:
    made = []

    def __init__(self, uuid):
        self.service = LocalService(uuid)
        self.advertisement_status = AdStatus.CREATED
        self.status_handlers = []
        self.params = None
        self.log = []
        Provider.made.append(self)

    @staticmethod
    async def create_async(uuid):
        return types.SimpleNamespace(error=Error.SUCCESS, service_provider=Provider(uuid))

    def add_advertisement_status_changed(self, h):
        self.status_handlers.append(h)

    def _status(self, status, error=Error.SUCCESS):
        self.advertisement_status = status
        args = types.SimpleNamespace(status=status, error=error)
        for h in self.status_handlers:
            on_windows_thread(h, self, args)

    def start_advertising_with_parameters(self, params):
        self.params = params
        self.log.append(("start", params.is_discoverable))
        self._status(AdStatus.ABORTED)
        self._status(AdStatus.STARTED)

    def update_advertising_parameters(self, params):
        if self.advertisement_status != AdStatus.STARTED:
            raise OSError("update on a provider that isn't advertising")
        self.params = params
        self.log.append(("update", params.is_discoverable))

    def stop_advertising(self):
        if self.advertisement_status != AdStatus.STARTED:
            raise OSError("A call to StopAdvertising can only be made on a service that is already advertising")
        self.log.append(("stop",))
        self.advertisement_status = AdStatus.STOPPED

    @property
    def discoverable(self):
        return self.advertisement_status == AdStatus.STARTED and self.params.is_discoverable


class Adapter:
    is_peripheral_role_supported = True

    @staticmethod
    async def get_default_async():
        return Adapter()


class Central:
    """A board connected to the PC, as Windows reports it to the app."""

    count = 0

    def __init__(self, mtu=247):
        Central.count += 1
        self.address = "AA:BB:CC:DD:EE:%02X" % Central.count
        self.session = Session("BluetoothLE#BluetoothLEe0:8f:4c:ac:f9:fd-" + self.address.lower(), mtu)
        self.client = Client(self.session)

    def _char(self, uuid):
        for provider in Provider.made:
            for char in provider.service.characteristics:
                if str(char.uuid) == str(bledev.UUID(uuid)):
                    return char
        raise KeyError(uuid)

    async def _request(self, handlers, char, request):
        args = Args(self.session, request)
        for h in handlers:
            on_windows_thread(h, char, args)
        while not args.deferral.done.is_set():
            await asyncio.sleep(0.001)
        return request.answer

    async def write(self, uuid, data, response=True):
        char = self._char(uuid)
        option = WriteOption.WRITE_WITH_RESPONSE if response else WriteOption.WRITE_WITHOUT_RESPONSE
        return await self._request(char.write_handlers, char, Request(data, option))

    async def burst(self, uuid, payloads, delays):
        """Writes without response, raised back to back, each resolving after its delay."""
        char = self._char(uuid)
        sent = []
        for data, delay in zip(payloads, delays):
            args = Args(self.session, Request(data, WriteOption.WRITE_WITHOUT_RESPONSE), delay)
            sent.append(args)
            for h in char.write_handlers:
                on_windows_thread(h, char, args)
        while not all(a.deferral is not None and a.deferral.done.is_set() for a in sent):
            await asyncio.sleep(0.001)

    async def read(self, uuid):
        char = self._char(uuid)
        return await self._request(char.read_handlers, char, Request())

    async def subscribe(self, uuid):
        char = self._char(uuid)
        char.subscribed_clients.append(self.client)
        for h in char.sub_handlers:
            on_windows_thread(h, char, None)
        await asyncio.sleep(0.01)

    async def disconnect(self):
        self.session.session_status = SessionStatus.CLOSED
        args = types.SimpleNamespace(status=SessionStatus.CLOSED, error=Error.SUCCESS)
        for provider in Provider.made:
            for char in provider.service.characteristics:
                if self.client in char.subscribed_clients:
                    char.subscribed_clients.remove(self.client)
        for h in self.session.handlers:
            on_windows_thread(h, self.session, args)
        await asyncio.sleep(0.01)


def _install():
    def module(name, **attrs):
        m = types.ModuleType(name)
        m.__dict__.update(attrs)
        sys.modules[name] = m

    module("bleak", BleakClient=object, BleakScanner=object)
    module("bleak.exc", BleakError=Exception)
    for name in ("winrt", "winrt.windows", "winrt.windows.devices", "winrt.windows.storage"):
        module(name)
    module("winrt.windows.devices.bluetooth", BluetoothAdapter=Adapter, BluetoothError=Error)
    module(
        "winrt.windows.devices.bluetooth.genericattributeprofile",
        GattCharacteristicProperties=Props,
        GattCommunicationStatus=Comm,
        GattLocalCharacteristicParameters=Params,
        GattLocalDescriptorParameters=Params,
        GattProtectionLevel=Protection,
        GattProtocolError=ProtocolError,
        GattServiceProvider=Provider,
        GattServiceProviderAdvertisementStatus=AdStatus,
        GattServiceProviderAdvertisingParameters=Params,
        GattSessionStatus=SessionStatus,
        GattWriteOption=WriteOption,
    )
    module("winrt.windows.storage.streams", Buffer=Buffer)


_NAMES = (
    "bleak",
    "bleak.exc",
    "bledev.bleak",
    "bledev.winrt",
    "winrt",
    "winrt.windows",
    "winrt.windows.devices",
    "winrt.windows.storage",
    "winrt.windows.devices.bluetooth",
    "winrt.windows.devices.bluetooth.genericattributeprofile",
    "winrt.windows.storage.streams",
)
_saved = {name: sys.modules.get(name) for name in _NAMES}
_install()
sys.modules.pop("bledev.bleak", None)
sys.modules.pop("bledev.winrt", None)
import bledev  # noqa: E402
import bledev.midi as midi  # noqa: E402
import bledev.nus as nus  # noqa: E402
import bledev.winrt as bw  # noqa: E402
from bledev import midi_codec  # noqa: E402

bw.radio_name = lambda: RADIO
for _name, _module in _saved.items():
    if _module is None:
        sys.modules.pop(_name, None)
    else:
        sys.modules[_name] = _module

SERVICE = "8a1f1000-2b4d-4c5e-9f60-1a2b3c4d5e6f"
CHAR = "8a1f1001-2b4d-4c5e-9f60-1a2b3c4d5e6f"


def gatt(capture=True, max_len=64):
    service = bledev.Service(SERVICE)
    char = bledev.Characteristic(
        service, CHAR, read=True, write=True, write_no_response=True, notify=True, capture=capture,
        max_len=max_len, initial=b"hello",
    )
    return service, char


def run(coro):
    return asyncio.run(asyncio.wait_for(coro, 10))


class WinRTPeripheral(unittest.TestCase):
    def setUp(self):
        Provider.made = []

    def ble(self, **kw):
        ble = bw.WinRTBLE(**kw)
        self.addCleanup(ble.close)
        return ble

    def test_capabilities_say_both_roles_and_no_name(self):
        caps = self.ble().capabilities()
        self.assertTrue(caps["central"])
        self.assertTrue(caps["peripheral"])
        self.assertFalse(caps["advertise_name"])

    def test_names_other_than_the_pcs_raise(self):
        async def go():
            ble = self.ble()
            ble.register_services(gatt()[0])
            with self.assertRaises(bledev.UnsupportedError):
                await ble.advertise(name="synth", services=[SERVICE])
            with self.assertRaises(bledev.UnsupportedError):
                ble.config(gap_name="synth")
            self.assertEqual(ble.config("gap_name"), RADIO)
            ble.config(gap_name=RADIO)  # its own name is fine

        run(go())

    def test_what_windows_cant_advertise_raises(self):
        async def go():
            ble = self.ble()
            ble.register_services(gatt()[0])
            for kwargs in (
                {"services": [SERVICE], "appearance": 0x03C1},
                {"services": [SERVICE], "manufacturer": (0xFFFF, b"x")},
                {"services": [SERVICE], "connectable": False},
                {},
                {"services": ["00001234-0000-1000-8000-00805f9b34fb"]},
                {"services": [SERVICE], "service_data": [("0000fe00-0000-1000-8000-00805f9b34fb", b"x")]},
            ):
                with self.assertRaises(bledev.UnsupportedError, msg=repr(kwargs)):
                    await ble.advertise(**kwargs)

        run(go())

    def test_advertise_returns_on_the_first_request_and_stops_advertising(self):
        async def go():
            ble = self.ble()
            service, char = gatt()
            ble.register_services(service)
            task = asyncio.ensure_future(ble.advertise(services=[SERVICE]))
            await asyncio.sleep(0.02)
            provider = Provider.made[0]
            self.assertTrue(provider.discoverable, "advertising the service")
            central = Central()
            self.assertEqual(await central.read(CHAR), b"hello")
            connection = await task
            self.assertEqual(connection.role, "peripheral")
            self.assertEqual(connection.device.address, central.address)
            self.assertEqual(connection.mtu, 247)
            self.assertFalse(provider.discoverable, "advertising stops when a central connects")
            self.assertEqual(provider.advertisement_status, AdStatus.STARTED, "the service stays published")
            await central.disconnect()
            self.assertFalse(connection.is_connected())
            await connection.disconnected(timeout_ms=100)
            self.assertEqual(provider.advertisement_status, AdStatus.STOPPED, "unpublished with nobody left")
            # And again, from stopped.
            task = asyncio.ensure_future(ble.advertise(services=[SERVICE]))
            await asyncio.sleep(0.02)
            self.assertTrue(provider.discoverable)
            await Central().subscribe(CHAR)
            await task

        run(go())

    def test_a_timeout_unpublishes(self):
        async def go():
            ble = self.ble()
            ble.register_services(gatt()[0])
            with self.assertRaises(bledev.BLETimeoutError):
                await ble.advertise(services=[SERVICE], timeout_ms=30)
            self.assertEqual(Provider.made[0].advertisement_status, AdStatus.STOPPED)

        run(go())

    def test_writes_are_captured_in_order_with_their_writer(self):
        async def go():
            ble = self.ble()
            service, char = gatt()
            ble.register_services(service)
            task = asyncio.ensure_future(ble.advertise(services=[SERVICE]))
            await asyncio.sleep(0.01)
            central = Central()
            self.assertEqual(await central.write(CHAR, b"one"), "ok")
            connection = await task
            self.assertIsNone(await central.write(CHAR, b"two", response=False), "no answer without response")
            await central.write(CHAR, b"three")
            got = [await char.written(timeout_ms=100) for _ in range(3)]
            self.assertEqual(got, [(connection, b"one"), (connection, b"two"), (connection, b"three")])
            self.assertEqual(char.read(), b"three")

        run(go())

    def test_a_burst_of_writes_keeps_its_order(self):
        # A BLE-MIDI stream: each write must come out in the order the central
        # sent it, even when Windows resolves a later request first.
        async def go():
            ble = self.ble()
            service, char = gatt()
            ble.register_services(service)
            task = asyncio.ensure_future(ble.advertise(services=[SERVICE]))
            await asyncio.sleep(0.01)
            central = Central()
            await central.write(CHAR, b"first")
            await task
            await char.written(timeout_ms=100)
            payloads = [bytes([n]) for n in range(8)]
            await central.burst(CHAR, payloads, [0.02, 0, 0.01, 0, 0.015, 0.005, 0, 0])
            got = [(await char.written(timeout_ms=200))[1] for _ in payloads]
            self.assertEqual(got, payloads)

        run(go())

    def test_too_long_writes_fail_loudly(self):
        async def go():
            ble = self.ble()
            service, char = gatt(max_len=4)
            ble.register_services(service)
            task = asyncio.ensure_future(ble.advertise(services=[SERVICE]))
            await asyncio.sleep(0.01)
            central = Central()
            answer = await central.write(CHAR, b"1234567")
            self.assertEqual(answer, ("error", ProtocolError.invalid_attribute_value_length))
            await task
            await central.write(CHAR, b"1234567", response=False)
            with self.assertRaises(bledev.BLEError):
                await char.written(timeout_ms=100)

        run(go())

    def test_notify_reaches_only_that_central_in_order(self):
        async def go():
            ble = self.ble(notify_buffers=8)
            service, char = gatt()
            ble.register_services(service)
            one, two = Central(), Central()
            task = asyncio.ensure_future(ble.advertise(services=[SERVICE]))
            await asyncio.sleep(0.01)
            await one.subscribe(CHAR)
            first = await task
            task = asyncio.ensure_future(ble.advertise(services=[SERVICE]))
            await asyncio.sleep(0.01)
            await two.subscribe(CHAR)
            second = await task
            sent = 0
            while sent < 50:
                try:
                    char.notify(first, b"n%d" % sent)
                    sent += 1
                except bledev.BusyError:
                    await asyncio.sleep(0.001)
            char.notify(second, b"only two")
            await asyncio.sleep(0.05)
            self.assertEqual(one.client.received, [b"n%d" % i for i in range(50)])
            self.assertEqual(two.client.received, [b"only two"])

        run(go())

    def test_a_burst_reports_busy(self):
        async def go():
            ble = self.ble(notify_buffers=4)
            service, char = gatt()
            ble.register_services(service)
            task = asyncio.ensure_future(ble.advertise(services=[SERVICE]))
            await asyncio.sleep(0.01)
            central = Central()
            await central.subscribe(CHAR)
            connection = await task
            native = central._char(CHAR)
            native.slow = asyncio.Event()
            for i in range(4):
                char.notify(connection, b"%d" % i)
            with self.assertRaises(bledev.BusyError):
                char.notify(connection, b"one too many")
            native.slow.set()
            await asyncio.sleep(0.02)
            self.assertEqual(central.client.received, [b"0", b"1", b"2", b"3"])

        run(go())

    def test_notifications_are_bounded_and_failures_raise(self):
        async def go():
            ble = self.ble()
            service, char = gatt()
            ble.register_services(service)
            task = asyncio.ensure_future(ble.advertise(services=[SERVICE]))
            await asyncio.sleep(0.01)
            central = Central(mtu=23)
            await central.subscribe(CHAR)
            connection = await task
            with self.assertRaises(bledev.BLEError):
                char.notify(connection, bytes(21))
            central._char(CHAR).fail_next = True
            char.notify(connection, b"lost")
            await asyncio.sleep(0.02)
            with self.assertRaises(bledev.BLEError):
                char.notify(connection, b"next")
            char.notify(connection, b"after")  # raised once, then carries on
            await asyncio.sleep(0.02)
            self.assertEqual(central.client.received, [b"after"])

        run(go())

    def test_nothing_reaches_a_central_that_hasnt_subscribed(self):
        async def go():
            ble = self.ble()
            service, char = gatt()
            ble.register_services(service)
            task = asyncio.ensure_future(ble.advertise(services=[SERVICE]))
            await asyncio.sleep(0.01)
            central = Central()
            await central.read(CHAR)
            connection = await task
            char.notify(connection, b"early")
            await central.subscribe(CHAR)
            char.notify(connection, b"late")
            await asyncio.sleep(0.02)
            self.assertEqual(central.client.received, [b"late"])

        run(go())

    def test_a_closed_connection_is_loud(self):
        async def go():
            ble = self.ble()
            service, char = gatt()
            ble.register_services(service)
            task = asyncio.ensure_future(ble.advertise(services=[SERVICE]))
            await asyncio.sleep(0.01)
            central = Central()
            await central.subscribe(CHAR)
            connection = await task
            with self.assertRaises(bledev.UnsupportedError):
                await connection.disconnect()
            with self.assertRaises(bledev.UnsupportedError):
                await connection.pair()
            await central.disconnect()
            with self.assertRaises(bledev.DisconnectedError):
                char.notify(connection, b"x")

        run(go())

    def test_descriptors_and_protection(self):
        async def go():
            ble = self.ble()
            service = bledev.Service(SERVICE)
            char = bledev.Characteristic(service, CHAR, read=True, notify=True, encrypted=True)
            bledev.Descriptor(char, 0x2908, b"\x01\x01")
            ble.register_services(service)
            with self.assertRaises(bledev.BLETimeoutError):
                await ble.advertise(services=[SERVICE], timeout_ms=10)
            native = Provider.made[0].service.characteristics[0]
            self.assertEqual(native.params.read_protection_level, Protection.ENCRYPTION_REQUIRED)
            self.assertEqual(native.params.characteristic_properties, Props.READ | Props.NOTIFY)
            self.assertEqual(native.descriptors, [(_uuid.UUID(str(bledev.UUID(0x2908))), b"\x01\x01")])

        run(go())

    def test_midi_serve_takes_no_name_and_carries_midi(self):
        async def go():
            ble = self.ble()
            task = asyncio.ensure_future(midi.serve(ble))
            await asyncio.sleep(0.02)
            central = Central()
            await central.subscribe(midi.CHARACTERISTIC)
            port = await task
            for packet in midi_codec.encode([(100, b"\x90\x3c\x64")], 20):
                await central.write(midi.CHARACTERISTIC, packet, response=False)
            self.assertEqual(await port.receive(timeout_ms=500), (100, b"\x90\x3c\x64"))
            port.write(b"\x80\x3c\x00")
            await port.drain()
            await asyncio.sleep(0.02)
            got = [m for ts, m in midi_codec.decode(central.client.received)]
            self.assertEqual(got, [b"\x80\x3c\x00"])
            await central.disconnect()

        run(go())

    def test_nus_serves_two_links_separately(self):
        async def go():
            ble = self.ble()
            centrals, links = [], []
            for _ in range(2):
                task = asyncio.ensure_future(nus.serve(ble))
                await asyncio.sleep(0.02)
                central = Central()
                await central.subscribe(nus.TX)
                centrals.append(central)
                links.append(await task)
            await links[0].write(b"to one")
            await links[1].write(b"to two")
            await links[0].drain()
            await links[1].drain()
            await asyncio.sleep(0.02)
            self.assertEqual(b"".join(centrals[0].client.received), b"to one")
            self.assertEqual(b"".join(centrals[1].client.received), b"to two")
            await centrals[1].write(nus.RX, b"from two", response=False)
            self.assertEqual(await links[1].readexactly(8), b"from two")
            for central in centrals:
                await central.disconnect()

        run(go())


class AutoPicks(unittest.TestCase):
    def test_platforms(self):
        import bledev.auto as auto

        saved = (auto.sys, auto._importable)
        try:
            auto._importable = lambda name: name == "bleak"
            for platform, want in (("win32", "winrt"), ("linux", "bluez"), ("darwin", "bleak")):
                auto.sys = types.SimpleNamespace(platform=platform, implementation=sys.implementation)
                self.assertEqual(auto.backend_name(), want)
        finally:
            auto.sys, auto._importable = saved
        self.assertEqual(auto.BACKENDS["winrt"], ("bledev.winrt", "WinRTBLE"))
        self.assertEqual(auto.BACKENDS["bluez"], ("bledev.bluez", "BlueZBLE"))


if __name__ == "__main__":
    unittest.main()
