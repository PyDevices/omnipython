# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""CPython backend for Linux: a GATT server through BlueZ, and bleak's central.

    from bledev.bluez import BlueZBLE
    ble = BlueZBLE()

Needs bleak (``pip install "omnipython[ble]"``), which brings ``dbus-fast``,
and the BlueZ bleak needs. ``bledev.auto.adapter()`` picks it on Linux. It
takes both roles: the peripheral side registers a GATT application and an
advertisement with BlueZ over D-Bus, and scanning and connecting are
`bledev.bleak.BleakBLE`'s, unchanged.

Where BlueZ differs from the contract, this backend says so rather than
pretending:

* BlueZ sends a notification to every central that subscribed; its D-Bus
  API has no way to send one to a single central. So ``notify(connection)``
  raises `bledev.BLEError` while more than one central is connected. With one
  connected it behaves as everywhere else, and ``write(data,
  send_update=True)`` notifies all of them on purpose.
* BlueZ queues notifications itself, so there is no `bledev.BusyError`.
* The MTU comes from the options BlueZ passes with each read and write, so a
  connection reports 23 until its central has read or written something.
* A central becomes a `bledev.Connection` when BlueZ reports it connected
  while this adapter advertises, or with its first read or write.
* Prepared (long) writes are refused.
* ``config(gap_name=...)`` sets the adapter's alias, which BlueZ may refuse
  without the right D-Bus policy; ``addr_mode`` is BlueZ's to pick.
"""

import asyncio

from dbus_fast import BusType, DBusError, Message, MessageType, Variant
from dbus_fast.aio import MessageBus
from dbus_fast.service import PropertyAccess, ServiceInterface, dbus_property, method

from . import (
    ADDR_RANDOM,
    BLEError,
    Connection,
    Device,
    DisconnectedError,
    FLAG_INDICATE,
    FLAG_NOTIFY,
    FLAG_READ,
    FLAG_WRITE,
    FLAG_WRITE_NO_RESPONSE,
    MAX_MTU,
    UUID,
    wait_ms,
)
from .bleak import BleakBLE, _Inbox

BLUEZ = "org.bluez"
_PROPERTIES = "org.freedesktop.DBus.Properties"
_ROOT = "/org/omnipython/bledev"
_TYPE_NOT_SUPPORTED = "org.bluez.Error.NotSupported"
_INVALID_LENGTH = "org.bluez.Error.InvalidValueLength"
_INVALID_OFFSET = "org.bluez.Error.InvalidOffset"
_FAILED = "org.bluez.Error.Failed"


def _address(path):
    # /org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF
    return path.rsplit("/", 1)[-1][4:].replace("_", ":")


def _value(options, key, default=None):
    entry = options.get(key)
    return default if entry is None else entry.value


def _flags(characteristic):
    flags = []
    char = characteristic
    for flag, name in (
        (FLAG_READ, "read"),
        (FLAG_WRITE, "write"),
        (FLAG_WRITE_NO_RESPONSE, "write-without-response"),
        (FLAG_NOTIFY, "notify"),
        (FLAG_INDICATE, "indicate"),
    ):
        if char.flags & flag:
            flags.append(name)
    if char.authenticated:
        if char.flags & FLAG_READ:
            flags.append("encrypt-authenticated-read")
        if char.flags & (FLAG_WRITE | FLAG_WRITE_NO_RESPONSE):
            flags.append("encrypt-authenticated-write")
    elif char.encrypted:
        if char.flags & FLAG_READ:
            flags.append("encrypt-read")
        if char.flags & (FLAG_WRITE | FLAG_WRITE_NO_RESPONSE):
            flags.append("encrypt-write")
    return flags


class BlueZBLE(BleakBLE):
    """The Linux host's Bluetooth adapter: BlueZ's GATT server, and bleak's central.

    ``adapter`` is BlueZ's name for the radio (``"hci0"``). ``queue_limit``,
    ``mtu``, ``scanner_args`` and ``client_args`` are
    `bledev.bleak.BleakBLE`'s; ``queue_limit`` also bounds each
    characteristic's queue of captured writes.
    """

    backend = "bluez"

    def __init__(self, *, adapter="hci0", queue_limit=1024, mtu=MAX_MTU, scanner_args=None, client_args=None):
        BleakBLE.__init__(self, queue_limit=queue_limit, mtu=mtu, scanner_args=scanner_args, client_args=client_args)
        self.adapter_path = "/org/bluez/" + adapter
        self._bus = None
        self._services = ()
        self._exported = []
        self._registered = False
        self._generation = 0
        self._advertisement = None
        # device path -> the live peripheral-side connection
        self._centrals = {}
        self._backlog = []
        self._arrived = None
        self._waiting = 0

    def capabilities(self):
        caps = BleakBLE.capabilities(self)
        caps.update(peripheral=True)
        return caps

    def config(self, *names, **settings):
        if "gap_name" in settings:
            name = settings.pop("gap_name")
            self._pending_alias = name
        if names == ("gap_name",):
            BleakBLE.config(self, **settings)
            return getattr(self, "_alias", None)
        return BleakBLE.config(self, *names, **settings)

    def close(self):
        """Unregister the GATT application and advertisement, and drop bleak's connections."""
        for connection in list(self._centrals.values()):
            connection._closed("adapter closed")
        self._centrals = {}
        self._backlog = []
        if self._arrived is not None:
            self._arrived.set()
        if self._bus is not None:
            for path, _ in self._exported:
                self._bus.unexport(path)
            self._exported = []
            self._bus.disconnect()
            self._bus = None
        self._registered = False
        BleakBLE.close(self)

    # -- D-Bus

    async def _call(self, path, interface, member, signature="", body=()):
        reply = await self._bus.call(
            Message(destination=BLUEZ, path=path, interface=interface, member=member, signature=signature, body=list(body))
        )
        if reply.message_type == MessageType.ERROR:
            raise BLEError("BlueZ {}.{}: {} {}".format(interface, member, reply.error_name, reply.body))
        return reply.body

    async def _connect_bus(self):
        if self._bus is not None:
            return
        self._bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        self._bus.add_message_handler(self._signal)
        rule = "type='signal',sender='{}',interface='{}',member='PropertiesChanged',arg0='org.bluez.Device1'".format(
            BLUEZ, _PROPERTIES
        )
        reply = await self._bus.call(
            Message(
                destination="org.freedesktop.DBus",
                path="/org/freedesktop/DBus",
                interface="org.freedesktop.DBus",
                member="AddMatch",
                signature="s",
                body=[rule],
            )
        )
        if reply.message_type == MessageType.ERROR:
            raise BLEError("D-Bus refused the match for BlueZ's devices: {}".format(reply.body))

    def _signal(self, message):
        if message.message_type != MessageType.SIGNAL or message.member != "PropertiesChanged":
            return False
        if not message.path.startswith(self.adapter_path + "/dev_") or message.body[0] != "org.bluez.Device1":
            return False
        connected = message.body[1].get("Connected")
        if connected is None:
            return False
        if connected.value:
            if self._advertisement is not None and not self._is_ours_as_central(message.path):
                self._connection_for(message.path)
        else:
            connection = self._centrals.get(message.path)
            if connection is not None:
                connection._closed("the central disconnected")
        return False

    def _is_ours_as_central(self, path):
        address = _address(path)
        for connection in self._connections:
            if connection.device.address.upper() == address:
                return True
        return False

    def _connection_for(self, path, mtu=None):
        connection = self._centrals.get(path)
        if connection is None or not connection.is_connected():
            connection = _BlueZConnection(self, Device(self, _address(path), ADDR_RANDOM), path)
            self._centrals[path] = connection
            self._backlog.append(connection)
            if self._arrived is not None:
                self._arrived.set()
        if mtu:
            connection._mtu = mtu
        return connection

    def _forget(self, connection):
        if self._centrals.get(connection.path) is connection:
            del self._centrals[connection.path]
        if connection in self._backlog:
            self._backlog.remove(connection)

    # -- peripheral

    def register_services(self, *services):
        for service in self._services:
            for characteristic in service.characteristics:
                characteristic._impl = None
        self._services = tuple(services)
        self._registered = False
        for service in services:
            for characteristic in service.characteristics:
                characteristic._impl = _ServerCharacteristic(self, characteristic)

    async def _register(self):
        await self._connect_bus()
        if self._registered:
            return
        for path, _ in self._exported:
            self._bus.unexport(path)
        self._exported = []
        self._generation += 1
        app = "{}/app{}".format(_ROOT, self._generation)
        for s, service in enumerate(self._services):
            spath = "{}/service{}".format(app, s)
            self._export(spath, _GattService(service, spath))
            for c, characteristic in enumerate(service.characteristics):
                cpath = "{}/char{}".format(spath, c)
                impl = characteristic._impl
                impl.path = cpath
                self._export(cpath, _GattCharacteristic(impl, spath, cpath))
                for d, descriptor in enumerate(characteristic.descriptors):
                    dpath = "{}/desc{}".format(cpath, d)
                    self._export(dpath, _GattDescriptor(descriptor, characteristic, cpath))
        self._export(app, _Application())
        await self._call(
            self.adapter_path, "org.bluez.GattManager1", "RegisterApplication", "oa{sv}", (app, {})
        )
        alias = getattr(self, "_pending_alias", None)
        if alias is not None:
            await self._set_alias(alias)
        self._registered = True

    async def _set_alias(self, alias):
        await self._call(
            self.adapter_path, _PROPERTIES, "Set", "ssv", ("org.bluez.Adapter1", "Alias", Variant("s", alias))
        )
        self._alias = alias
        self._pending_alias = None

    def _export(self, path, interface):
        self._bus.export(path, interface)
        self._exported.append((path, interface))

    async def advertise(
        self,
        interval_us=100000,
        *,
        name=None,
        services=None,
        appearance=0,
        manufacturer=None,
        connectable=True,
        timeout_ms=None,
        service_data=None,
    ):
        if not self._services:
            raise BLEError("nothing to advertise: call register_services() first")
        await self._register()
        if getattr(self, "_pending_alias", None) is not None:
            await self._set_alias(self._pending_alias)
        fields = {"Type": ("s", "peripheral" if connectable else "broadcast")}
        if services:
            fields["ServiceUUIDs"] = ("as", [str(UUID(u)) for u in services])
        if name is not None:
            fields["LocalName"] = ("s", name)
        if appearance:
            fields["Appearance"] = ("q", appearance)
        if manufacturer:
            company, data = manufacturer
            fields["ManufacturerData"] = ("a{qv}", {company: Variant("ay", bytes(data))})
        if service_data:
            fields["ServiceData"] = ("a{sv}", {str(UUID(u)): Variant("ay", bytes(d)) for u, d in service_data})
        # BlueZ takes the interval in milliseconds, 20 ms at least.
        interval_ms = max(20, interval_us // 1000)
        fields["MinInterval"] = ("u", interval_ms)
        fields["MaxInterval"] = ("u", interval_ms)
        if self._arrived is None:
            self._arrived = asyncio.Event()
        self._waiting += 1
        try:
            while self._backlog and not self._backlog[0].is_connected():
                self._backlog.pop(0)
            if not self._backlog:
                await self._start_advertising(fields)

                async def arrival():
                    while not self._backlog:
                        if self._bus is None:
                            raise BLEError("adapter closed while advertising")
                        self._arrived.clear()
                        await self._arrived.wait()

                await wait_ms(arrival(), timeout_ms, "advertise")
            return self._backlog.pop(0)
        finally:
            self._waiting -= 1
            if not self._waiting:
                await self._stop_advertising()

    async def _start_advertising(self, fields):
        await self._stop_advertising()
        self._generation += 1
        path = "{}/advert{}".format(_ROOT, self._generation)
        self._bus.export(path, _advertisement(fields))
        try:
            await self._call(
                self.adapter_path, "org.bluez.LEAdvertisingManager1", "RegisterAdvertisement", "oa{sv}", (path, {})
            )
        except Exception:
            self._bus.unexport(path)
            raise
        self._advertisement = path

    async def _stop_advertising(self):
        path, self._advertisement = self._advertisement, None
        if path is None or self._bus is None:
            return
        try:
            await self._call(self.adapter_path, "org.bluez.LEAdvertisingManager1", "UnregisterAdvertisement", "o", (path,))
        finally:
            self._bus.unexport(path)


class _BlueZConnection(Connection):
    """A central connected to BlueZ's GATT server."""

    def __init__(self, ble, device, path):
        Connection.__init__(self, ble, device, "peripheral")
        self.path = path
        self._open = True
        self._gone = asyncio.Event()

    def _closed(self, why):
        if not self._open:
            return
        self._open = False
        self._gone.set()
        self._ble._forget(self)

    def is_connected(self):
        return self._open

    async def disconnect(self, timeout_ms=2000):
        if not self._open:
            return
        await self._ble._call(self.path, "org.bluez.Device1", "Disconnect")
        await self.disconnected(timeout_ms)

    async def disconnected(self, timeout_ms=None):
        if self._open:
            await wait_ms(self._gone.wait(), timeout_ms, "disconnected")


class _ServerCharacteristic:
    """BlueZBLE's half of a `bledev.Characteristic`."""

    def __init__(self, ble, characteristic):
        self._ble = ble
        self._char = characteristic
        self._value = characteristic._initial or b""
        self._writes = _Inbox(ble.queue_limit, "writes to {}".format(characteristic.uuid))
        self._last_writer = None
        self._written = asyncio.Event()
        self.notifying = False
        self.path = None
        self.interface = None
        self._confirmed = None

    # From BlueZ, through _GattCharacteristic.

    def remote_read(self, options):
        offset = _value(options, "offset", 0)
        device = _value(options, "device")
        if device is not None:
            self._ble._connection_for(device, _value(options, "mtu"))
        if offset > len(self._value):
            raise DBusError(_INVALID_OFFSET, "offset {} past the value's {} bytes".format(offset, len(self._value)))
        return self._value[offset:]

    def remote_write(self, value, options):
        if _value(options, "offset", 0):
            raise DBusError(_TYPE_NOT_SUPPORTED, "prepared writes aren't supported")
        data = bytes(value)
        if len(data) > self._char.max_len:
            raise DBusError(_INVALID_LENGTH, "{} bytes; max_len is {}".format(len(data), self._char.max_len))
        device = _value(options, "device")
        connection = None if device is None else self._ble._connection_for(device, _value(options, "mtu"))
        self._value = data
        if self._char.capture:
            self._writes.put((connection, data))
        else:
            self._last_writer = connection
            self._written.set()

    def confirmed(self):
        if self._confirmed is not None and not self._confirmed.done():
            self._confirmed.set_result(None)

    # The contract.

    def read(self):
        return self._value

    def write(self, data, send_update):
        self._value = data
        if send_update and self.notifying and self.interface is not None:
            self.interface.emit_properties_changed({"Value": data})

    def _check(self, connection, data):
        if not isinstance(connection, _BlueZConnection) or connection._ble is not self._ble:
            raise BLEError("{!r} is not a peripheral-side connection of this adapter".format(connection))
        if not connection.is_connected():
            raise DisconnectedError("the connection is closed")
        others = len(self._ble._centrals) - 1
        if others:
            raise BLEError(
                "BlueZ notifies every subscribed central, and {} more are connected; "
                "notify(connection) can't reach just one. write(data, send_update=True) sends to all".format(others)
            )
        if len(data) > connection.mtu - 3:
            raise BLEError(
                "notification of {} bytes exceeds the ATT payload of {} (mtu {} - 3)".format(
                    len(data), connection.mtu - 3, connection.mtu
                )
            )

    def notify(self, connection, data):
        data = self._value if data is None else data
        self._check(connection, data)
        if self.notifying and self.interface is not None:
            self.interface.emit_properties_changed({"Value": data})

    async def indicate(self, connection, data, timeout_ms):
        data = self._value if data is None else data
        self._check(connection, data)
        if not self.notifying or self.interface is None:
            return
        self._confirmed = asyncio.get_running_loop().create_future()
        self.interface.emit_properties_changed({"Value": data})
        await wait_ms(self._confirmed, timeout_ms, "indicate")

    async def written(self, timeout_ms):
        if self._char.capture:
            return await self._writes.get(timeout_ms)
        if not self._written.is_set():
            await wait_ms(self._written.wait(), timeout_ms, "written")
        self._written.clear()
        return self._last_writer


# The D-Bus objects BlueZ reads. dbus-fast takes the D-Bus types from the
# annotations, so these stay thin and hand everything to the classes above.


class _Application(ServiceInterface):
    """The application root; dbus-fast answers GetManagedObjects for it."""

    def __init__(self):
        ServiceInterface.__init__(self, "org.omnipython.bledev.Application")


class _GattService(ServiceInterface):
    def __init__(self, service, path):
        ServiceInterface.__init__(self, "org.bluez.GattService1")
        self._uuid = str(service.uuid)

    @dbus_property(access=PropertyAccess.READ)
    def UUID(self) -> "s":  # noqa: F722, F821, N802
        return self._uuid

    @dbus_property(access=PropertyAccess.READ)
    def Primary(self) -> "b":  # noqa: F722, F821, N802
        return True


class _GattCharacteristic(ServiceInterface):
    def __init__(self, impl, service_path, path):
        ServiceInterface.__init__(self, "org.bluez.GattCharacteristic1")
        self._impl = impl
        self._service = service_path
        impl.interface = self

    @dbus_property(access=PropertyAccess.READ)
    def UUID(self) -> "s":  # noqa: F722, F821, N802
        return str(self._impl._char.uuid)

    @dbus_property(access=PropertyAccess.READ)
    def Service(self) -> "o":  # noqa: F722, F821, N802
        return self._service

    @dbus_property(access=PropertyAccess.READ)
    def Flags(self) -> "as":  # noqa: F722, F821, N802
        return _flags(self._impl._char)

    @dbus_property(access=PropertyAccess.READ)
    def Value(self) -> "ay":  # noqa: F722, F821, N802
        return self._impl._value

    @method()
    def ReadValue(self, options: "a{sv}") -> "ay":  # noqa: F722, F821, N802
        return self._impl.remote_read(options)

    @method()
    def WriteValue(self, value: "ay", options: "a{sv}"):  # noqa: F722, F821, N802
        self._impl.remote_write(value, options)

    @method()
    def StartNotify(self):  # noqa: N802
        self._impl.notifying = True

    @method()
    def StopNotify(self):  # noqa: N802
        self._impl.notifying = False

    @method()
    def Confirm(self):  # noqa: N802
        self._impl.confirmed()


class _GattDescriptor(ServiceInterface):
    def __init__(self, descriptor, characteristic, characteristic_path):
        ServiceInterface.__init__(self, "org.bluez.GattDescriptor1")
        self._descriptor = descriptor
        self._characteristic = characteristic_path
        self._flags = ["read"]
        if characteristic.authenticated:
            self._flags.append("encrypt-authenticated-read")
        elif characteristic.encrypted:
            self._flags.append("encrypt-read")

    @dbus_property(access=PropertyAccess.READ)
    def UUID(self) -> "s":  # noqa: F722, F821, N802
        return str(self._descriptor.uuid)

    @dbus_property(access=PropertyAccess.READ)
    def Characteristic(self) -> "o":  # noqa: F722, F821, N802
        return self._characteristic

    @dbus_property(access=PropertyAccess.READ)
    def Flags(self) -> "as":  # noqa: F722, F821, N802
        return self._flags

    @method()
    def ReadValue(self, options: "a{sv}") -> "ay":  # noqa: F722, F821, N802
        offset = _value(options, "offset", 0)
        return self._descriptor.value[offset:]


def _advertisement(fields):
    """An LEAdvertisement1 with only the given properties, so BlueZ adds
    nothing an advertisement didn't ask for."""

    def prop(name, signature, value):
        def getter(self) -> signature:
            return value

        getter.__name__ = name
        return dbus_property(access=PropertyAccess.READ, name=name)(getter)

    def release(self):
        pass

    release.__name__ = "Release"
    namespace = {"Release": method(name="Release")(release)}
    for name, (signature, value) in fields.items():
        namespace[name] = prop(name, signature, value)
    cls = type("_Advertisement", (ServiceInterface,), namespace)
    advert = cls.__new__(cls)
    ServiceInterface.__init__(advert, "org.bluez.LEAdvertisement1")
    advert.fields = dict(fields)
    return advert
