# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""Bluetooth LE transport: the Nordic UART service, one frame per line.

A board advertises and a laptop, a phone's browser or another board connects.
Frames cross as `hmilink.stream` sends them over a UART, so the same panel
works over either::

    from hmilink import ble

    device.add(ble.serve("rack"))               # a board: every central that connects is a panel
    panel = hmilink.Panel(ble.connect("rack"))  # a laptop or another board connects to it

Roles in Bluetooth don't follow roles in hmilink. A laptop and a browser can
only connect, never advertise, so when one of them holds the document and a
board is its panel, the board advertises with `advertise`, which waits for
one central::

    panel = hmilink.Panel(ble.advertise("desk"))   # on the board
    device.add(ble.connect("desk"))                 # on the laptop

The service is Nordic's, so nRF Connect and Web Bluetooth serial pages see
it, and a page can be a panel with ``hmilink.js`` (see `hmilink.web`). It's
`bledev.nus` underneath: pass ``adapter=`` to choose the radio, or leave it
out for `bledev.auto.adapter()` (the board's radio, or bleak on a laptop).

Every call here returns at once. Connecting, advertising and sending run as
``asyncio`` tasks, as ``bledev`` does. A program with no event loop of its
own needs nothing more: each ``poll()`` runs the waiting tasks once, at most
every `PUMP_MS`. A program that runs an event loop makes its links from
inside it and gives the loop time between polls (``await asyncio.sleep(0.005)``),
and the loop runs them.

A link's ``state`` says what it's doing: ``"connecting"``, ``"advertising"``,
``"connected"`` or ``"closed"``, and ``error`` holds what stopped it. Frames
sent before it connects wait and go out once it does. When the other side
goes away the link closes: a device drops it, and a panel's ``closed`` turns
true. `serve` keeps advertising, so the next central that connects becomes a
new panel.

Needs ``bledev``: OmniPython firmware with Bluetooth, ``omnipython[ble]`` on a
computer, or ``bledev.fake`` in tests.
"""

import asyncio
import sys

from bledev import nus

from . import stream, ticks_diff, ticks_ms

#: The shortest time between two runs of the waiting tasks, in milliseconds,
#: when the program has no event loop of its own.
PUMP_MS = 4

_MP = sys.implementation.name in ("micropython", "circuitpython")


def _loop_running():
    # current_task() raises with no loop running on every interpreter;
    # CircuitPython's get_running_loop() returns its loop even then.
    try:
        asyncio.current_task()
        return True
    except RuntimeError:
        return False


async def _yield():
    await asyncio.sleep(0)


class _Driver:
    """Where the transport's tasks run.

    With a running event loop, on it. Without one, MicroPython's single loop
    runs one pass on each call to `pump`; CPython gets a private loop that
    does the same, so every link shares one loop either way.
    """

    def __init__(self):
        self.pumping = not _loop_running()
        self.loop = None
        if self.pumping and not _MP:
            self.loop = asyncio.new_event_loop()
        self.pumped = ticks_ms()

    def task(self, coro):
        if self.loop is not None:
            return self.loop.create_task(coro)
        return asyncio.create_task(coro)

    def pump(self, force=False):
        if not self.pumping:
            return
        now = ticks_ms()
        if not force and ticks_diff(now, self.pumped) < PUMP_MS:
            return
        self.pumped = now
        if self.loop is not None:
            self.loop.run_until_complete(_yield())
        else:
            asyncio.run(_yield())


_driver = None


def _get_driver():
    global _driver
    if _driver is None:
        _driver = _Driver()
    return _driver


def _adapter(adapter):
    if adapter is not None:
        return adapter
    from bledev import auto

    return auto.adapter()


class _Pipe:
    """The byte stream `stream.Link` reads and writes, fed by the tasks."""

    def __init__(self, driver):
        self.driver = driver
        self.nus = None
        self.inbuf = b""
        self.out = None
        self.done = False
        self.error = None
        # Whether the other side can hear us yet; see `Link._run`.
        self.heard = False
        self.wake = asyncio.Event()

    def read(self, n):
        self.driver.pump()
        if self.inbuf:
            data = self.inbuf[:n]
            self.inbuf = self.inbuf[n:]
            return data
        if self.done:
            raise OSError("Bluetooth link closed")
        return None

    def write(self, data):
        # All or nothing, one write in flight: while one is still going out,
        # the frames wait in the link, which reads as busy, so the device
        # holds back telemetry rather than queue it.
        self.driver.pump()
        if self.done:
            raise OSError("Bluetooth link closed")
        if self.out is not None:
            return 0
        self.out = bytes(data)
        self.wake.set()
        return len(data)


class Link(stream.Link):
    """One Bluetooth LE connection carrying frames. Made by `serve`,
    `connect` and `advertise`."""

    def __init__(self, opener, state, central):
        driver = _get_driver()
        stream.Link.__init__(self, _Pipe(driver))
        self.state = state
        self._central = central
        self._task = driver.task(self._run(opener))

    @property
    def error(self):
        """What stopped the link, or ``None``."""
        return self.obj.error

    def busy(self):
        return len(self._out) > 0 or self.obj.out is not None

    def recv(self):
        frame = stream.Link.recv(self)
        if self.closed:
            self.state = "closed"
        return frame

    def close(self):
        if not self.closed:
            stream.Link.close(self)
            self.state = "closed"
            self._task.cancel()
            self.obj.driver.pump(force=True)

    async def _run(self, opener):
        pipe = self.obj
        writer = None
        try:
            pipe.nus = await opener()
            self.state = "connected"
            # A peripheral's notifications are lost until the central has
            # subscribed, and only the central knows when it has. So the
            # central opens with an empty line, which no reader counts as a
            # frame, and the peripheral sends nothing until it hears from it.
            if self._central:
                await pipe.nus.write(b"\n")
                pipe.heard = True
            writer = pipe.driver.task(self._write())
            while True:
                data = await pipe.nus.read()
                if not data:
                    break
                pipe.inbuf += data
                if not pipe.heard:
                    pipe.heard = True
                    pipe.wake.set()
        except Exception as e:  # noqa: BLE001 - kept in error; the link closes
            pipe.error = e
        finally:
            pipe.done = True
            if writer is not None:
                writer.cancel()
            if pipe.nus is not None and pipe.nus.connection.is_connected():
                try:
                    await pipe.nus.close()
                except Exception:  # noqa: BLE001 - closing either way
                    pass

    async def _write(self):
        pipe = self.obj
        try:
            while True:
                if pipe.out is None or not pipe.heard:
                    pipe.wake.clear()
                    await pipe.wake.wait()
                    continue
                await pipe.nus.write(pipe.out)
                pipe.out = None
        except Exception as e:  # noqa: BLE001 - a dropped link; the reader sees it close
            if pipe.error is None:
                pipe.error = e
            await pipe.nus.close()


class Listener:
    """Advertises for a device and hands it each central that connects as a
    new link. Made by `serve`."""

    def __init__(self, ble, name, options):
        self.state = "advertising"
        self.error = None
        #: How many centrals have connected.
        self.links = 0
        self._ble = ble
        self._name = name
        self._options = options
        self._pending = []
        self._driver = _get_driver()
        self._task = self._driver.task(self._keep())

    async def _keep(self):
        try:
            while True:
                link = await nus.serve(self._ble, self._name, **self._options)
                self.links += 1
                self._pending.append(Link(_Opened(link), "connected", False))
        except Exception as e:  # noqa: BLE001 - kept in error and state
            self.error = e
            self.state = "stopped: %s" % (e,)

    def accept(self):
        self._driver.pump()
        if self._pending:
            return self._pending.pop(0)
        return None

    def close(self):
        self._task.cancel()
        for link in self._pending:
            link.close()
        self._pending = []
        self.state = "closed"
        self._driver.pump(force=True)


class _Opened:
    """An opener for a NUS link that is already connected."""

    def __init__(self, link):
        self.link = link

    async def __call__(self):
        return self.link


def serve(name=None, *, adapter=None, **options):
    """Advertise as ``name`` and take any number of centrals, each a link.

    Give it to ``Device.add``. ``name`` defaults to the board's name.
    ``options`` go to `bledev.nus.serve` (``interval_us``, ``mtu``).
    """
    return Listener(_adapter(adapter), name, options)


def connect(name=None, *, adapter=None, **options):
    """A link to the peripheral advertising as ``name``, connecting in the background.

    With no ``name``, the first one advertising the service. ``options`` go
    to `bledev.nus.connect` (``timeout_ms``, and the connection interval on a
    board). A link that can't connect closes, with ``error`` saying why.
    """
    ble = _adapter(adapter)

    async def opener():
        return await nus.connect(ble, name, **options)

    return Link(opener, "connecting", True)


def advertise(name=None, *, adapter=None, **options):
    """A link that advertises as ``name`` and waits for one central.

    For a board that's a panel to a laptop or a browser. ``options`` go to
    `bledev.nus.serve`.
    """
    ble = _adapter(adapter)

    async def opener():
        return await nus.serve(ble, name, **options)

    return Link(opener, "advertising", False)
