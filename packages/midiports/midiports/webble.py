# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""Bluetooth MIDI devices a browser page connects to, through Web Bluetooth.

In a browser page, `midiports.endpoints.register` lists one more endpoint
under ``midi.in`` and ``midi.out``: "Choose a Bluetooth MIDI device".
Pairing it (a tap in appkit's picker, or `endpointkit.pair`) opens the
browser's device chooser for the BLE-MIDI service; the device the person
picks connects and is listed under both kinds by its name, to choose like
any other port. When the link drops, it connects to the same device again
without asking. The endpoint stays, to add another device.

This is the endpoints' backend, the way `midiports.webmidi` is for Web MIDI
ports: ``available()``, ``open_port(info)``, ``state()``, ``why()``,
``request()`` and ``changes()``. The links are `midiports.ble`'s, with the
browser as the central, over `bledev.webble`.

It needs Chrome or Edge (desktop or Android) and a secure context; elsewhere
the endpoint is unavailable and says why. The chooser only opens from a tap
or a click. A reload forgets the devices chosen: choose them again.
"""

from . import IN, OUT, PortIn, PortInfo, PortOut
from .ble import BleIn, _sleep_ms

#: What the endpoint that opens the chooser says.
ASK = "Choose a Bluetooth MIDI device"
#: Keep that endpoint listed beside the devices, to add another.
KEEP_ASKING = True
#: How long, in milliseconds, to wait after a reconnection fails before the next.
RETRY_MS = 2000

_links = []  # a PageBleIn for each device the person chose
_asking = []  # the PageBleIn still waiting on the chooser, if one is
_changes = [0]
_errors = []  # why the last choice failed, once


def _available():
    from bledev import webble

    return webble.available()


def _midi():
    import bledev.midi

    return bledev.midi


class PageBleIn(BleIn):
    """The link to one device the person chose: `midiports.ble`'s input,
    with the browser as the central. The first connection opens the
    chooser; later ones go back to the device it gave."""

    _idle = "choosing"

    def __init__(self, ble=None, connect=None, **options):
        if ble is None:
            from bledev.webble import WebBLE

            ble = WebBLE(services=[_midi().SERVICE])
        self._connect = connect or _midi().connect
        self._device = None
        self.retry_ms = RETRY_MS
        BleIn.__init__(self, None, ble, pump=False, **options)

    async def _open(self):
        if self._device is None:
            try:
                port = await self._connect(self._ble)
            except Exception as e:  # noqa: BLE001 - the person closed the chooser, or the device refused
                self._fail(e)
                return None
            self._device = port.connection.device
            self.name = port.name if getattr(port, "name", None) else self._device.name or self._device.address
            if self in _asking:
                _asking.remove(self)
            _links.append(self)
            _changes[0] += 1
            return port
        self.state = "reconnecting"
        try:
            return await self._connect(self._ble, device=self._device)
        except Exception:  # noqa: BLE001 - out of range or switched off: try again
            await _sleep_ms(self.retry_ms)
            return None

    def _fail(self, error):
        """The chooser gave no device: forget this link and say why, once."""
        self._closed = True
        self.state = "closed"
        if self in _asking:
            _asking.remove(self)
        _errors[:] = [str(error) or type(error).__name__]
        _changes[0] += 1


class _In(PortIn):
    """One device's input, as a chosen endpoint opens it. Letting the
    endpoint go leaves the link up for its output and for later."""

    def __init__(self, link):
        PortIn.__init__(self)
        self.link = link

    def any(self):
        return self.link.any()

    def readinto(self, buf, nbytes=None):
        return self.link.readinto(buf, nbytes)

    def read(self, nbytes=None):
        return self.link.read(nbytes)

    def take_timestamp(self):
        return self.link.take_timestamp()

    def close(self):
        pass

    deinit = close


class _Out(PortOut):
    """One device's output, as a chosen endpoint opens it."""

    def __init__(self, link):
        self.link = link

    def write(self, buf, nbytes=None):
        return self.link.write(buf, nbytes)

    def close(self):
        pass

    deinit = close


def state():
    """``"asking"`` while the chooser is open, ``"idle"`` otherwise, or
    ``"unavailable"`` where the browser has no Web Bluetooth."""
    if not _available():
        return "unavailable"
    return "asking" if _asking else "idle"


def why():
    """Why no device can be chosen, or why the last choice failed (once); None otherwise."""
    if not _available():
        return "This browser has no Web Bluetooth: Chrome or Edge has"
    if _errors:
        return _errors.pop()
    return None


def request(link=PageBleIn):
    """Open the browser's chooser; the device picked is listed once it connects.

    Call it from a tap or a click: the browser opens the chooser only then.
    *link* makes the link, for a test.
    """
    if _asking or not _available():
        return
    _asking.append(None)  # until the link exists: a second tap waits
    try:
        made = link()
    finally:
        _asking.remove(None)
    if not made._closed and made not in _links:
        _asking.append(made)
    _changes[0] += 1


def changes():
    """A count that moves whenever the devices or the chooser's state do."""
    return _changes[0]


def available():
    """``PortInfo`` for each device chosen, both ways round."""
    out = []
    for i, link in enumerate(_links):
        if link._closed:
            continue
        out.append(PortInfo(id=i, name=link.name, direction=IN))
        out.append(PortInfo(id=i, name=link.name, direction=OUT))
    return tuple(out)


def open_port(info):
    link = _links[info.id]
    return _In(link) if info.direction == IN else _Out(link)


def forget():
    """Close every device's link and forget them, as a page's restart would."""
    for link in _links + [l for l in _asking if l is not None]:
        link.close()
    del _links[:]
    del _asking[:]
    del _errors[:]
    _changes[0] += 1
