# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""bledev.bluez's GATT server without a Linux radio: stand-ins for dbus-fast
and BlueZ.

The stand-in bus records what the backend exports and the calls it makes,
answers BlueZ's methods the way bluetoothd does, and lets a test play a
central: it reports a device connected or gone with BlueZ's
``PropertiesChanged`` signal, and calls the exported characteristic's
``ReadValue``, ``WriteValue`` and ``StartNotify`` with the options BlueZ
passes. A notification is the ``Value`` change the backend emits, which
BlueZ sends to every subscribed central.
"""

import asyncio
import enum
import sys
import types
import unittest

import _env  # noqa: F401  (puts lib/ on sys.path)

ADAPTER = "/org/bluez/hci0"


class MessageType(enum.Enum):
    METHOD_CALL = 1
    METHOD_RETURN = 2
    ERROR = 3
    SIGNAL = 4


class BusType(enum.Enum):
    SYSTEM = 1


class DBusError(Exception):
    def __init__(self, name, text):
        Exception.__init__(self, name, text)
        self.type = name


class Variant:
    def __init__(self, signature, value):
        self.signature = signature
        self.value = value


class Message:
    def __init__(self, destination=None, path=None, interface=None, member=None, signature="", body=(),
                 message_type=MessageType.METHOD_CALL, error_name=None):
        self.destination = destination
        self.path = path
        self.interface = interface
        self.member = member
        self.signature = signature
        self.body = list(body)
        self.message_type = message_type
        self.error_name = error_name


class ServiceInterface:
    def __init__(self, name):
        self.name = name
        self.changes = []

    def emit_properties_changed(self, changed):
        self.changes.append(dict(changed))


class PropertyAccess(enum.Enum):
    READ = 1


def dbus_property(access=None, name=None):
    def wrap(fn):
        fn.dbus_property = name or fn.__name__
        return fn

    return wrap


def method(name=None):
    def wrap(fn):
        return fn

    return wrap


class Bus:
    """The system bus, with bluetoothd behind it."""

    last = None

    def __init__(self, bus_type=None):
        self.exported = {}
        self.calls = []
        self.handlers = []
        self.adverts = []
        self.apps = []
        self.refuse = None
        self.adapter = {"Name": "laptop", "Alias": "laptop"}
        Bus.last = self

    async def connect(self):
        return self

    def disconnect(self):
        pass

    def export(self, path, interface):
        assert path not in self.exported, "exported twice: " + path
        self.exported[path] = interface

    def unexport(self, path):
        self.exported.pop(path, None)

    def add_message_handler(self, handler):
        self.handlers.append(handler)

    async def call(self, message):
        self.calls.append((message.path, message.interface, message.member, message.body))
        if self.refuse == message.member:
            return Message(message_type=MessageType.ERROR, error_name="org.bluez.Error.Failed", body=["refused"])
        if message.member == "RegisterApplication":
            self.apps.append(message.body[0])
        elif message.member == "RegisterAdvertisement":
            self.adverts.append(message.body[0])
        elif message.member == "UnregisterAdvertisement":
            self.adverts.remove(message.body[0])
        elif message.member == "Disconnect":
            self.signal_connected(message.path, False)
        elif message.member == "Get" and message.body[0] == "org.bluez.Adapter1":
            return Message(message_type=MessageType.METHOD_RETURN, body=[Variant("s", self.adapter[message.body[1]])])
        elif message.member == "Set" and message.body[:2] == ["org.bluez.Adapter1", "Alias"]:
            # BlueZ keeps the alias across restarts; an empty one means the adapter's name.
            self.adapter["Alias"] = message.body[2].value or self.adapter["Name"]
        return Message(message_type=MessageType.METHOD_RETURN)

    def signal_connected(self, path, connected):
        msg = Message(
            path=path, interface="org.freedesktop.DBus.Properties", member="PropertiesChanged",
            body=["org.bluez.Device1", {"Connected": Variant("b", connected)}, []],
            message_type=MessageType.SIGNAL,
        )
        for handler in self.handlers:
            handler(msg)

    def advert(self):
        assert len(self.adverts) == 1, self.adverts
        return self.exported[self.adverts[0]]

    def characteristic(self, uuid):
        for interface in self.exported.values():
            if interface.name == "org.bluez.GattCharacteristic1" and interface.UUID() == str(uuid):
                return interface
        raise KeyError(uuid)


class Central:
    count = 0

    def __init__(self, bus, mtu=247):
        Central.count += 1
        self.bus = bus
        self.path = "{}/dev_AA_BB_CC_DD_EE_{:02X}".format(ADAPTER, Central.count)
        self.mtu = mtu

    def options(self, **extra):
        options = {"device": Variant("o", self.path), "mtu": Variant("q", self.mtu)}
        options.update(extra)
        return options

    def connect(self):
        self.bus.signal_connected(self.path, True)

    def disconnect(self):
        self.bus.signal_connected(self.path, False)

    def write(self, uuid, data, command=False):
        options = self.options(type=Variant("s", "command" if command else "request"))
        self.bus.characteristic(uuid).WriteValue(bytes(data), options)

    def read(self, uuid, offset=0):
        return self.bus.characteristic(uuid).ReadValue(self.options(offset=Variant("q", offset)))


def _install():
    def module(name, **attrs):
        m = types.ModuleType(name)
        m.__dict__.update(attrs)
        sys.modules[name] = m

    module("bleak", BleakClient=object, BleakScanner=object)
    module("bleak.exc", BleakError=Exception)
    module("dbus_fast", BusType=BusType, DBusError=DBusError, Message=Message, MessageType=MessageType, Variant=Variant)
    module("dbus_fast.aio", MessageBus=Bus)
    module(
        "dbus_fast.service",
        PropertyAccess=PropertyAccess, ServiceInterface=ServiceInterface, dbus_property=dbus_property, method=method,
    )


_NAMES = ("bleak", "bleak.exc", "bledev.bleak", "bledev.bluez", "dbus_fast", "dbus_fast.aio", "dbus_fast.service")
_saved = {name: sys.modules.get(name) for name in _NAMES}
_install()
sys.modules.pop("bledev.bleak", None)
sys.modules.pop("bledev.bluez", None)
import bledev  # noqa: E402
import bledev.bluez as bz  # noqa: E402
import bledev.midi as midi  # noqa: E402
from bledev import midi_codec  # noqa: E402

for _name, _module in _saved.items():
    if _module is None:
        sys.modules.pop(_name, None)
    else:
        sys.modules[_name] = _module

SERVICE = "8a1f1000-2b4d-4c5e-9f60-1a2b3c4d5e6f"
CHAR = "8a1f1001-2b4d-4c5e-9f60-1a2b3c4d5e6f"


def gatt(**kw):
    service = bledev.Service(SERVICE)
    options = dict(read=True, write=True, write_no_response=True, notify=True, capture=True, max_len=64, initial=b"hello")
    options.update(kw)
    char = bledev.Characteristic(service, CHAR, **options)
    return service, char


def run(coro):
    return asyncio.run(asyncio.wait_for(coro, 10))


class BlueZPeripheral(unittest.TestCase):
    def ble(self):
        ble = bz.BlueZBLE()
        self.addCleanup(ble.close)
        return ble

    def test_capabilities_say_both_roles_and_a_name(self):
        caps = self.ble().capabilities()
        self.assertTrue(caps["central"] and caps["peripheral"])
        self.assertTrue(caps["advertise_name"])

    def test_registers_the_application_and_advertises_what_was_asked(self):
        async def go():
            ble = self.ble()
            service, char = gatt(encrypted=True)
            bledev.Descriptor(char, 0x2908, b"\x01\x01")
            ble.register_services(service)
            task = asyncio.ensure_future(
                ble.advertise(name="synth", services=[SERVICE], manufacturer=(0xFFFF, b"hi"), interval_us=50000)
            )
            await asyncio.sleep(0.01)
            bus = Bus.last
            self.assertEqual(len(bus.apps), 1)
            fields = bus.advert().fields
            self.assertEqual(fields["Type"], ("s", "peripheral"))
            self.assertEqual(fields["LocalName"], ("s", "synth"))
            self.assertEqual(fields["ServiceUUIDs"], ("as", [SERVICE]))
            self.assertEqual(fields["MinInterval"], ("u", 50))
            self.assertNotIn("Appearance", fields, "nothing it wasn't asked for")
            exported = bus.characteristic(CHAR)
            self.assertEqual(
                exported.Flags(), ["read", "write", "write-without-response", "notify", "encrypt-read", "encrypt-write"]
            )
            descs = [i for i in bus.exported.values() if i.name == "org.bluez.GattDescriptor1"]
            self.assertEqual(descs[0].ReadValue({}), b"\x01\x01")
            central = Central(bus)
            central.connect()
            connection = await task
            self.assertEqual(connection.device.address, "AA:BB:CC:DD:EE:%02X" % Central.count)
            self.assertEqual(bus.adverts, [], "advertising stops when a central connects")

        run(go())

    def test_writes_reads_and_mtu(self):
        async def go():
            ble = self.ble()
            service, char = gatt()
            ble.register_services(service)
            task = asyncio.ensure_future(ble.advertise(services=[SERVICE]))
            await asyncio.sleep(0.01)
            central = Central(Bus.last, mtu=185)
            central.connect()
            connection = await task
            self.assertEqual(connection.mtu, 23, "23 until BlueZ passes the MTU with a request")
            self.assertEqual(central.read(CHAR), b"hello")
            self.assertEqual(connection.mtu, 185)
            self.assertEqual(central.read(CHAR, offset=2), b"llo")
            central.write(CHAR, b"one")
            central.write(CHAR, b"two", command=True)
            got = [await char.written(timeout_ms=100) for _ in range(2)]
            self.assertEqual(got, [(connection, b"one"), (connection, b"two")])
            with self.assertRaises(DBusError):
                central.write(CHAR, bytes(65))
            with self.assertRaises(DBusError):
                Bus.last.characteristic(CHAR).WriteValue(b"x", central.options(offset=Variant("q", 1)))

        run(go())

    def test_notify_with_one_central(self):
        async def go():
            ble = self.ble()
            service, char = gatt()
            ble.register_services(service)
            task = asyncio.ensure_future(ble.advertise(services=[SERVICE]))
            await asyncio.sleep(0.01)
            central = Central(Bus.last)
            central.connect()
            connection = await task
            exported = Bus.last.characteristic(CHAR)
            char.notify(connection, b"early")
            self.assertEqual(exported.changes, [], "nothing goes out before a subscription")
            exported.StartNotify()
            for i in range(20):
                char.notify(connection, b"n%d" % i)
            self.assertEqual([c["Value"] for c in exported.changes], [b"n%d" % i for i in range(20)])
            with self.assertRaises(bledev.BLEError):
                char.notify(connection, bytes(21))  # mtu 23 until a request says otherwise

        run(go())

    def test_notify_refuses_when_it_would_reach_more_than_one(self):
        async def go():
            ble = self.ble()
            service, char = gatt()
            ble.register_services(service)
            task = asyncio.ensure_future(ble.advertise(services=[SERVICE]))
            await asyncio.sleep(0.01)
            one = Central(Bus.last)
            one.connect()
            first = await task
            two = Central(Bus.last)
            task = asyncio.ensure_future(ble.advertise(services=[SERVICE]))
            await asyncio.sleep(0.01)
            two.connect()
            await task
            exported = Bus.last.characteristic(CHAR)
            exported.StartNotify()
            with self.assertRaises(bledev.BLEError):
                char.notify(first, b"just one?")
            char.write(b"everyone", send_update=True)
            self.assertEqual(exported.changes, [{"Value": b"everyone"}])
            two.disconnect()
            char.notify(first, b"now just one")
            self.assertEqual(exported.changes[-1], {"Value": b"now just one"})

        run(go())

    def test_disconnects_both_ways(self):
        async def go():
            ble = self.ble()
            ble.register_services(gatt()[0])
            task = asyncio.ensure_future(ble.advertise(services=[SERVICE]))
            await asyncio.sleep(0.01)
            central = Central(Bus.last)
            central.connect()
            connection = await task
            await connection.disconnect(timeout_ms=100)
            self.assertFalse(connection.is_connected())
            self.assertIn((central.path, "org.bluez.Device1", "Disconnect", []), Bus.last.calls)
            task = asyncio.ensure_future(ble.advertise(services=[SERVICE]))
            await asyncio.sleep(0.01)
            other = Central(Bus.last)
            other.connect()
            connection = await task
            other.disconnect()
            await connection.disconnected(timeout_ms=100)

        run(go())

    def test_a_timeout_and_a_refusal(self):
        async def go():
            ble = self.ble()
            ble.register_services(gatt()[0])
            with self.assertRaises(bledev.BLETimeoutError):
                await ble.advertise(services=[SERVICE], timeout_ms=20)
            self.assertEqual(Bus.last.adverts, [], "unregistered after the timeout")
            Bus.last.refuse = "RegisterAdvertisement"
            with self.assertRaises(bledev.BLEError):
                await ble.advertise(services=[SERVICE], timeout_ms=20)

        run(go())

    def test_a_device_we_connected_to_isnt_a_central(self):
        async def go():
            ble = self.ble()
            ble.register_services(gatt()[0])
            task = asyncio.ensure_future(ble.advertise(services=[SERVICE], timeout_ms=100))
            await asyncio.sleep(0.01)
            central = Central(Bus.last)
            address = central.path.rsplit("/", 1)[-1][4:].replace("_", ":")
            ble._connections.append(types.SimpleNamespace(device=types.SimpleNamespace(address=address)))
            central.connect()
            with self.assertRaises(bledev.BLETimeoutError):
                await task
            ble._connections.clear()

        run(go())

    def test_midi_serve_with_a_name(self):
        async def go():
            ble = self.ble()
            task = asyncio.ensure_future(midi.serve(ble, name="synth"))
            await asyncio.sleep(0.02)
            bus = Bus.last
            self.assertEqual(bus.advert().fields["LocalName"], ("s", "synth"))
            self.assertIn((ADAPTER, "org.freedesktop.DBus.Properties", "Set"), [c[:3] for c in bus.calls])
            central = Central(bus)
            central.connect()
            port = await task
            exported = bus.characteristic(midi.CHARACTERISTIC)
            exported.StartNotify()
            for packet in midi_codec.encode([(5, b"\x90\x40\x7f")], 20):
                central.write(midi.CHARACTERISTIC, packet, command=True)
            self.assertEqual(await port.receive(timeout_ms=500), (5, b"\x90\x40\x7f"))
            port.write(b"\x80\x40\x00")
            await port.drain()
            got = [m for ts, m in midi_codec.decode([c["Value"] for c in exported.changes])]
            self.assertEqual(got, [b"\x80\x40\x00"])

        run(go())

    def test_close_puts_the_adapters_alias_back(self):
        async def go(before):
            ble = bz.BlueZBLE()
            task = asyncio.ensure_future(midi.serve(ble, name="synth"))
            await asyncio.sleep(0.02)
            bus = Bus.last
            self.assertEqual(bus.adapter["Alias"], "synth")
            task.cancel()
            await ble.aclose()
            return bus

        # Set before serve() registers, so the fake starts from what each case wants.
        for before in ("laptop", "studio"):
            Bus.__init__ = _with_alias(before)
            try:
                bus = run(go(before))
            finally:
                Bus.__init__ = _plain_init
            self.assertEqual(bus.adapter["Alias"], before, "the alias it had before serve()")
            sets = [c[3] for c in bus.calls if c[2] == "Set"]
            self.assertEqual(sets[0][2].value, "synth")
            self.assertEqual(sets[-1][2].value, "" if before == "laptop" else "studio",
                             "back to the adapter's own name when it had no alias of its own")


_plain_init = Bus.__init__


def _with_alias(alias):
    def init(self, bus_type=None):
        _plain_init(self, bus_type)
        self.adapter["Alias"] = alias

    return init


if __name__ == "__main__":
    unittest.main()
