# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""CPython backend for Windows: a GATT server through WinRT, and bleak's central.

    from bledev.winrt import WinRTBLE
    ble = WinRTBLE()

Needs bleak (``pip install "omnipython[ble]"``), which brings the WinRT
packages this uses. ``bledev.auto.adapter()`` picks it on Windows. It takes
both roles: the peripheral side is Windows' own GATT server, and scanning
and connecting are `bledev.bleak.BleakBLE`'s, unchanged.

Where Windows differs from the contract, this backend says so rather than
pretending:

* Windows advertises under the PC's Bluetooth name, and an app can't choose
  another. ``advertise(name=None)`` uses it; any other ``name`` raises
  `bledev.UnsupportedError`. ``config("gap_name")`` returns the name Windows
  will use. ``appearance``, ``manufacturer`` and ``connectable=False``
  raise too, and ``interval_us`` is Windows' to pick.
* Windows advertises services, not names, so ``advertise()`` needs
  ``services``, and each must be registered. ``service_data`` may only name
  one of those services.
* A central becomes a `bledev.Connection` with its first read, write or
  subscription, not when the link comes up: Windows tells an app nothing
  before that. Discovery alone doesn't count.
* The services stay published while any central is connected; only the
  advertisement stops. A central that already knows the PC and talks to it
  between two ``advertise()`` calls is handed to the next one.
* The peripheral can't drop a central: `Connection.disconnect` raises
  `bledev.UnsupportedError`. Windows pairs on its own, so ``pair()`` raises
  too; ``encrypted=True`` characteristics still make Windows insist on it.
* ``notify()`` queues the packet for that one central and returns. At most
  ``notify_buffers`` packets wait per connection; one more raises
  `bledev.BusyError`. A packet Windows fails to send raises from the next
  ``notify()`` on that connection.
* Prepared (long) writes are refused with "request not supported".
"""

import asyncio
import uuid as _uuid

from winrt.windows.devices.bluetooth import BluetoothAdapter, BluetoothError
from winrt.windows.devices.bluetooth.genericattributeprofile import (
    GattCharacteristicProperties,
    GattCommunicationStatus,
    GattLocalCharacteristicParameters,
    GattLocalDescriptorParameters,
    GattProtectionLevel,
    GattProtocolError,
    GattServiceProvider,
    GattServiceProviderAdvertisementStatus,
    GattServiceProviderAdvertisingParameters,
    GattSessionStatus,
    GattWriteOption,
)
from winrt.windows.storage.streams import Buffer

from . import (
    ADDR_RANDOM,
    BLEError,
    BusyError,
    Connection,
    DEFAULT_MTU,
    Device,
    DisconnectedError,
    FLAG_INDICATE,
    FLAG_NOTIFY,
    FLAG_READ,
    FLAG_WRITE,
    FLAG_WRITE_NO_RESPONSE,
    MAX_MTU,
    UnsupportedError,
    UUID,
    wait_ms,
)
from .bleak import BleakBLE, _Inbox

_PROPERTIES = (
    (FLAG_READ, GattCharacteristicProperties.READ),
    (FLAG_WRITE, GattCharacteristicProperties.WRITE),
    (FLAG_WRITE_NO_RESPONSE, GattCharacteristicProperties.WRITE_WITHOUT_RESPONSE),
    (FLAG_NOTIFY, GattCharacteristicProperties.NOTIFY),
    (FLAG_INDICATE, GattCharacteristicProperties.INDICATE),
)

# Windows advertises the computer's NetBIOS name unless the radio's
# registry key has a "Local Name".
_COMPUTER_NAME_NETBIOS = 0


def _buffer(data):
    buf = Buffer(len(data))
    buf.length = len(data)
    if data:
        memoryview(buf)[:] = data
    return buf


def _guid(uuid):
    return _uuid.UUID(str(UUID(uuid)))


def _address(device_id):
    # "BluetoothLE#BluetoothLE<radio>-<peer>": the peer's address is last.
    return device_id[-17:].upper()


def _protection(characteristic):
    if characteristic.authenticated:
        return GattProtectionLevel.ENCRYPTION_AND_AUTHENTICATION_REQUIRED
    if characteristic.encrypted:
        return GattProtectionLevel.ENCRYPTION_REQUIRED
    return GattProtectionLevel.PLAIN


def radio_name():
    """The name Windows advertises for this PC's Bluetooth radio.

    The radio's "Local Name" in the registry when one was set, otherwise the
    computer's NetBIOS name, which is what Windows uses.
    """
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services\BTHUSB\Enum") as key:
            instance = winreg.QueryValueEx(key, "0")[0]
        path = r"SYSTEM\CurrentControlSet\Enum\%s\Device Parameters" % instance
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
            value = winreg.QueryValueEx(key, "Local Name")[0]
        if isinstance(value, bytes):
            value = value.split(b"\0")[0].decode("utf-8")
        return value
    except FileNotFoundError:
        pass
    import ctypes

    size = ctypes.c_ulong(256)
    buf = ctypes.create_unicode_buffer(size.value)
    if not ctypes.windll.kernel32.GetComputerNameExW(_COMPUTER_NAME_NETBIOS, buf, ctypes.byref(size)):
        raise OSError(ctypes.GetLastError(), "GetComputerNameExW failed")
    return buf.value


class WinRTBLE(BleakBLE):
    """The PC's Bluetooth radio: Windows' GATT server, and bleak's central.

    ``notify_buffers`` bounds the notifications waiting per connection.
    ``queue_limit``, ``mtu``, ``scanner_args`` and ``client_args`` are
    `bledev.bleak.BleakBLE`'s; ``queue_limit`` also bounds each
    characteristic's queue of captured writes.
    """

    backend = "winrt"

    def __init__(self, *, notify_buffers=16, queue_limit=1024, mtu=MAX_MTU, scanner_args=None, client_args=None):
        BleakBLE.__init__(self, queue_limit=queue_limit, mtu=mtu, scanner_args=scanner_args, client_args=client_args)
        self.notify_buffers = notify_buffers
        self._services = ()
        self._providers = []
        self._running = set()
        self._built = False
        self._loop = None
        # device id -> the live peripheral-side connection
        self._centrals = {}
        self._backlog = []
        self._arrived = None
        self._aborted = None
        self._waiting = 0

    def capabilities(self):
        caps = BleakBLE.capabilities(self)
        caps.update(peripheral=True, advertise_name=False)
        return caps

    def config(self, *names, **settings):
        if "gap_name" in settings:
            name = settings.pop("gap_name")
            if name != radio_name():
                raise UnsupportedError(
                    "Windows names the PC {!r}; an app can't change the Bluetooth name".format(radio_name())
                )
        if names == ("gap_name",):
            BleakBLE.config(self, **settings)
            return radio_name()
        return BleakBLE.config(self, *names, **settings)

    def close(self):
        """Stop the GATT server, forget its centrals, and drop bleak's connections."""
        self._unpublish()
        self._providers = []
        self._built = False
        for connection in list(self._centrals.values()):
            connection._closed("adapter closed")
        self._centrals = {}
        self._backlog = []
        if self._arrived is not None:
            self._arrived.set()
        BleakBLE.close(self)

    # -- peripheral

    def register_services(self, *services):
        self._unpublish()
        self._providers = []
        self._built = False
        for service in self._services:
            for characteristic in service.characteristics:
                characteristic._impl = None
        self._services = tuple(services)
        for service in services:
            for characteristic in service.characteristics:
                characteristic._impl = _ServerCharacteristic(self, characteristic)

    async def _build(self):
        self._loop = asyncio.get_running_loop()
        adapter = await BluetoothAdapter.get_default_async()
        if adapter is None:
            raise BLEError("this PC has no Bluetooth radio, or it is turned off")
        if not adapter.is_peripheral_role_supported:
            raise UnsupportedError("this PC's Bluetooth radio can't be a peripheral")
        providers = []
        for service in self._services:
            result = await GattServiceProvider.create_async(_guid(service.uuid))
            if result.error != BluetoothError.SUCCESS:
                raise BLEError("Windows refused service {}: {}".format(service.uuid, result.error))
            provider = result.service_provider
            provider.add_advertisement_status_changed(self._status_changed)
            for characteristic in service.characteristics:
                await characteristic._impl._create(provider.service)
            providers.append((provider, service))
        self._providers = providers
        self._built = True

    def _from_windows(self, function, *args):
        # WinRT raises its events on its own threads; everything else
        # happens on the event loop.
        loop = self._loop
        if loop is not None and not loop.is_closed():
            loop.call_soon_threadsafe(function, *args)

    def _status_changed(self, provider, args):
        # Windows reports a passing ABORTED with no error on every start,
        # then STARTED; only an abort with an error means it failed.
        if args.status == GattServiceProviderAdvertisementStatus.ABORTED and args.error != BluetoothError.SUCCESS:
            self._from_windows(self._abort, "Windows stopped advertising: {}".format(args.error))

    def _abort(self, message):
        self._aborted = BLEError(message)
        if self._arrived is not None:
            self._arrived.set()

    def _connection_for(self, session):
        key = session.device_id.id
        connection = self._centrals.get(key)
        if connection is not None and connection.is_connected():
            return connection
        connection = _WinRTConnection(self, Device(self, _address(key), ADDR_RANDOM), session, key)
        self._centrals[key] = connection
        self._backlog.append(connection)
        if self._arrived is not None:
            self._arrived.set()
        return connection

    def _forget(self, connection):
        if self._centrals.get(connection._key) is connection:
            del self._centrals[connection._key]
        if connection in self._backlog:
            self._backlog.remove(connection)
        for service in self._services:
            for characteristic in service.characteristics:
                if characteristic._impl is not None:
                    characteristic._impl._subscribers.pop(connection._key, None)
        if not self._centrals and not self._waiting:
            self._unpublish()

    def _unpublish(self):
        # Windows' own status lags behind the calls, so this keeps its own.
        for provider, _ in self._providers:
            if id(provider) in self._running:
                self._running.discard(id(provider))
                provider.stop_advertising()

    def _publish(self, advertised, service_data):
        for provider, service in self._providers:
            parameters = GattServiceProviderAdvertisingParameters()
            parameters.is_connectable = True
            parameters.is_discoverable = service.uuid in advertised
            data = service_data.get(service.uuid)
            if data is not None:
                parameters.service_data = _buffer(data)
            if id(provider) in self._running:
                provider.update_advertising_parameters(parameters)
            else:
                provider.start_advertising_with_parameters(parameters)
                self._running.add(id(provider))

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
        if name is not None and name != radio_name():
            raise UnsupportedError(
                "Windows advertises this PC as {!r} and an app can't choose another name; "
                "pass name=None".format(radio_name())
            )
        if appearance:
            raise UnsupportedError("Windows can't advertise an appearance")
        if manufacturer:
            raise UnsupportedError("Windows can't put manufacturer data in a GATT service's advertisement")
        if not connectable:
            raise UnsupportedError("Windows only advertises a GATT service as connectable")
        if not self._services:
            raise BLEError("nothing to advertise: call register_services() first")
        if not services:
            raise UnsupportedError("Windows advertises services, not a name alone: pass services=")
        registered = [service.uuid for service in self._services]
        advertised = [UUID(u) for u in services]
        for u in advertised:
            if u not in registered:
                raise UnsupportedError("Windows only advertises a registered service, and {} isn't one".format(u))
        data = {}
        for u, payload in service_data or ():
            u = UUID(u)
            if u not in advertised:
                raise UnsupportedError(
                    "Windows only sends service data for an advertised service, and {} isn't one".format(u)
                )
            data[u] = bytes(payload)
        if not self._built:
            await self._build()
        if self._arrived is None:
            self._arrived = asyncio.Event()
        self._aborted = None
        self._waiting += 1
        try:
            while self._backlog and not self._backlog[0].is_connected():
                self._backlog.pop(0)
            if not self._backlog:
                self._publish(advertised, data)

                async def arrival():
                    while not self._backlog:
                        if self._aborted is not None:
                            raise self._aborted
                        if not self._built:
                            raise BLEError("adapter closed while advertising")
                        self._arrived.clear()
                        await self._arrived.wait()

                await wait_ms(arrival(), timeout_ms, "advertise")
            return self._backlog.pop(0)
        finally:
            self._waiting -= 1
            if self._built and not self._waiting:
                if self._centrals:
                    self._publish((), {})
                else:
                    self._unpublish()


class _WinRTConnection(Connection):
    """A central talking to Windows' GATT server."""

    def __init__(self, ble, device, session, key):
        Connection.__init__(self, ble, device, "peripheral")
        self._session = session
        self._key = key
        self._open = True
        self._gone = asyncio.Event()
        self._outbox = []
        self._sender = None
        self._error = None
        session.add_session_status_changed(self._status_changed)

    def _status_changed(self, session, args):
        if args.status == GattSessionStatus.CLOSED:
            self._ble._from_windows(self._closed, "the central disconnected")

    def _closed(self, why):
        if not self._open:
            return
        self._open = False
        self._error = DisconnectedError(why)
        for entry in self._outbox:
            if entry[3] is not None and not entry[3].done():
                entry[3].set_exception(DisconnectedError(why))
        self._outbox = []
        self._gone.set()
        self._ble._forget(self)

    @property
    def mtu(self):
        if self._open:
            self._mtu = max(DEFAULT_MTU, self._session.max_pdu_size)
        return self._mtu

    def is_connected(self):
        return self._open

    async def disconnect(self, timeout_ms=2000):
        raise UnsupportedError("Windows can't drop a central from the peripheral side; the central disconnects")

    async def disconnected(self, timeout_ms=None):
        if self._open:
            await wait_ms(self._gone.wait(), timeout_ms, "disconnected")

    async def pair(self, bond=True, timeout_ms=30000, passkey=None):
        raise UnsupportedError("Windows pairs with a central on its own; an app can't start it")

    def _check(self):
        error = self._error
        if error is not None:
            if self._open:
                self._error = None
            raise error

    def _send(self, server, client, data, done):
        self._check()
        if done is None and len(self._outbox) >= self._ble.notify_buffers:
            raise BusyError("{} notifications already waiting for this central".format(len(self._outbox)))
        self._outbox.append((server, client, data, done))
        if self._sender is None:
            self._sender = asyncio.ensure_future(self._drain())

    def _fail(self, error):
        for entry in self._outbox:
            if entry[3] is not None and not entry[3].done():
                entry[3].set_exception(error)
        self._outbox = []

    async def _drain(self):
        try:
            while self._outbox and self._open:
                entry = self._outbox[0]
                server, client, data, done = entry
                try:
                    result = await server._native.notify_value_for_subscribed_client_async(_buffer(data), client)
                    status = result.status
                except OSError as e:
                    status = e
                if not self._outbox or self._outbox[0] is not entry:
                    break  # the connection closed while Windows sent
                self._outbox.pop(0)
                if status == GattCommunicationStatus.SUCCESS:
                    if done is not None and not done.done():
                        done.set_result(None)
                    continue
                error = BLEError("Windows failed to send to {}: {}".format(self.device.address, status))
                if done is not None and not done.done():
                    done.set_exception(error)
                else:
                    self._error = error
                self._fail(error)
        finally:
            self._sender = None


class _ServerCharacteristic:
    """WinRTBLE's half of a `bledev.Characteristic`."""

    def __init__(self, ble, characteristic):
        self._ble = ble
        self._char = characteristic
        self._value = characteristic._initial or b""
        self._native = None
        self._writes = _Inbox(ble.queue_limit, "writes to {}".format(characteristic.uuid))
        self._last_writer = None
        self._written = asyncio.Event()
        self._error = None
        # device id -> GattSubscribedClient
        self._subscribers = {}
        self._requests = []
        self._worker = None

    async def _create(self, service):
        char = self._char
        parameters = GattLocalCharacteristicParameters()
        properties = 0
        for flag, native in _PROPERTIES:
            if char.flags & flag:
                properties |= native
        parameters.characteristic_properties = properties
        parameters.read_protection_level = _protection(char)
        parameters.write_protection_level = _protection(char)
        result = await service.create_characteristic_async(_guid(char.uuid), parameters)
        if result.error != BluetoothError.SUCCESS:
            raise BLEError("Windows refused characteristic {}: {}".format(char.uuid, result.error))
        native = result.characteristic
        for descriptor in char.descriptors:
            dp = GattLocalDescriptorParameters()
            dp.static_value = _buffer(descriptor.value)
            dp.read_protection_level = _protection(char)
            made = await native.create_descriptor_async(_guid(descriptor.uuid), dp)
            if made.error != BluetoothError.SUCCESS:
                raise BLEError("Windows refused descriptor {}: {}".format(descriptor.uuid, made.error))
        if char.flags & FLAG_READ:
            native.add_read_requested(self._read_requested)
        if char.flags & (FLAG_WRITE | FLAG_WRITE_NO_RESPONSE):
            native.add_write_requested(self._write_requested)
        if char.flags & (FLAG_NOTIFY | FLAG_INDICATE):
            native.add_subscribed_clients_changed(self._subscribers_changed)
        self._native = native

    # Windows' threads: take the deferral, then hand over to the event loop.

    def _read_requested(self, sender, args):
        deferral = args.get_deferral()
        self._ble._from_windows(self._arrive, self._answer_read, args, deferral)

    def _write_requested(self, sender, args):
        deferral = args.get_deferral()
        self._ble._from_windows(self._arrive, self._take_write, args, deferral)

    def _subscribers_changed(self, sender, args):
        self._ble._from_windows(self._resubscribe, list(sender.subscribed_clients or ()))

    # The event loop. Requests are answered one at a time, in the order they
    # arrived: a task each would let a later write overtake an earlier one
    # while Windows hands over the request.

    def _arrive(self, handler, args, deferral):
        self._requests.append((handler, args, deferral))
        if self._worker is None:
            self._worker = asyncio.ensure_future(self._answer())

    async def _answer(self):
        try:
            while self._requests:
                handler, args, deferral = self._requests.pop(0)
                try:
                    await handler(args, deferral)
                except Exception as e:
                    self._fail(BLEError("Windows' request to {} failed: {!r}".format(self._char.uuid, e)))
        finally:
            self._worker = None

    async def _answer_read(self, args, deferral):
        try:
            request = await args.get_request_async()
            self._ble._connection_for(args.session)
            if request.offset > len(self._value):
                request.respond_with_protocol_error(GattProtocolError.invalid_offset)
            else:
                request.respond_with_value(_buffer(self._value[request.offset :]))
        finally:
            deferral.complete()

    async def _take_write(self, args, deferral):
        try:
            request = await args.get_request_async()
            connection = self._ble._connection_for(args.session)
            respond = request.option == GattWriteOption.WRITE_WITH_RESPONSE
            if request.offset:
                if respond:
                    request.respond_with_protocol_error(GattProtocolError.request_not_supported)
                return
            data = bytes(request.value)
            if len(data) > self._char.max_len:
                if respond:
                    request.respond_with_protocol_error(GattProtocolError.invalid_attribute_value_length)
                else:
                    error = BLEError(
                        "{} bytes written to {} without response; max_len is {}".format(
                            len(data), self._char.uuid, self._char.max_len
                        )
                    )
                    self._fail(error)
                return
            self._remote_write(connection, data)
            if respond:
                request.respond()
        finally:
            deferral.complete()

    def _fail(self, error):
        # Raised by written(), in order with the writes around it.
        if self._char.capture:
            self._writes.put(error)
        else:
            self._error = error
            self._written.set()

    def _resubscribe(self, clients):
        now = {}
        for client in clients:
            connection = self._ble._connection_for(client.session)
            now[connection._key] = client
        self._subscribers = now

    def _remote_write(self, connection, data):
        self._value = data
        if self._char.capture:
            self._writes.put((connection, data))
        else:
            self._last_writer = connection
            self._written.set()

    # The contract.

    def read(self):
        return self._value

    def write(self, data, send_update):
        self._value = data
        if send_update:
            for key, client in list(self._subscribers.items()):
                connection = self._ble._centrals.get(key)
                if connection is not None:
                    self._queue(connection, client, data, None)

    def _client(self, connection):
        if not isinstance(connection, _WinRTConnection) or connection._ble is not self._ble:
            raise BLEError("{!r} is not a peripheral-side connection of this adapter".format(connection))
        connection._check()
        if not connection.is_connected():
            raise DisconnectedError("the connection is closed")
        return self._subscribers.get(connection._key)

    def _queue(self, connection, client, data, done):
        if len(data) > client.max_notification_size:
            raise BLEError(
                "notification of {} bytes exceeds the {} this central takes (mtu {} - 3)".format(
                    len(data), client.max_notification_size, connection.mtu
                )
            )
        connection._send(self, client, data, done)

    def notify(self, connection, data):
        client = self._client(connection)
        if client is None:
            return  # not subscribed: a radio sends it and the central drops it
        self._queue(connection, client, self._value if data is None else data, None)

    async def indicate(self, connection, data, timeout_ms):
        client = self._client(connection)
        if client is None:
            return
        done = asyncio.get_running_loop().create_future()
        self._queue(connection, client, self._value if data is None else data, done)
        await wait_ms(done, timeout_ms, "indicate")

    async def written(self, timeout_ms):
        if self._char.capture:
            item = await self._writes.get(timeout_ms)
            if isinstance(item, Exception):
                raise item
            return item
        if not self._written.is_set():
            await wait_ms(self._written.wait(), timeout_ms, "written")
        self._written.clear()
        if self._error is not None:
            error, self._error = self._error, None
            raise error
        return self._last_writer
