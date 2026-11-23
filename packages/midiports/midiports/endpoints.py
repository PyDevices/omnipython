# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""A computer's MIDI ports as endpointkit endpoints, chosen once for every program.

Register the providers, choose ports in a picker or a script, and read every
chosen input as one port and write every chosen output at once::

    import adafruit_midi
    import endpointkit
    from midiports import endpoints

    endpoints.register()
    endpointkit.select("midi.in", [ep.id for ep in endpointkit.endpoints("midi.in")])
    midi = adafruit_midi.MIDI(midi_in=endpoints.merged_in(), midi_out=endpoints.fan_out())

Windows' ports come from `midiports.windows`, Linux raw MIDI from
`midiports.linux`. An endpoint's id holds the port's name, which stays put
across reboots where Windows' indices don't, so a saved choice finds its port
again. Choosing a port opens it, and letting it go closes it: on Windows a
port is held by one program at a time, so read it through `merged_in` rather
than opening it again.

Ports plugged in later are found by `endpointkit.poll`, which rescans every
``rescan_ms``.
"""

import sys
import time

import endpointkit

from . import IN, OUT, PortIn, PortOut

#: How often, in milliseconds, `endpointkit.poll` looks for new ports.
RESCAN_MS = 2000

_ticks_ms = getattr(time, "ticks_ms", None)
_ticks_diff = getattr(time, "ticks_diff", None)
if _ticks_ms is None:

    def _ticks_ms():
        return int(time.monotonic() * 1000)

    def _ticks_diff(a, b):
        return a - b


def _backend():
    """The module that lists and opens this host's ports, or None."""
    if sys.platform == "win32":
        from . import windows

        return windows
    if sys.platform == "linux":
        from . import linux

        return linux
    return None


class HostMidi(endpointkit.Provider):
    """One direction of the host's MIDI ports.

    Args:
        direction (str): `midiports.IN` or `midiports.OUT`.
        backend (module): what lists and opens the ports, with ``available()``
            and ``open_port(info)``; the host's own when None.
        rescan_ms (int): how often `poll` lists the ports again.
    """

    def __init__(self, direction, backend=None, rescan_ms=RESCAN_MS):
        self.backend = backend or _backend()
        if self.backend is None:
            raise OSError("no MIDI ports on %s" % sys.platform)
        where = self.backend.__name__.rsplit(".", 1)[-1]
        endpointkit.Provider.__init__(
            self, "midi.in" if direction == IN else "midi.out", "%s-midi-%s" % (where, direction)
        )
        self.direction = direction
        self.rescan_ms = rescan_ms
        self.open = {}  # local id -> open port
        self._infos = {}  # local id -> PortInfo
        self._last = _ticks_ms()
        self._seen = None

    def scan(self):
        self._last = _ticks_ms()
        infos = {}
        found = []
        for info in self.backend.available():
            if info.direction != self.direction:
                continue
            local = info.name
            n = 2
            while local in infos:  # two of the same device
                local = "%s #%d" % (info.name, n)
                n += 1
            infos[local] = info
            found.append(self.endpoint(local, local, endpointkit.CONNECTED if local in self.open else endpointkit.AVAILABLE))
        self._infos = infos
        self._seen = [ep.id for ep in found]
        return found

    def poll(self):
        if _ticks_diff(_ticks_ms(), self._last) < self.rescan_ms:
            return None
        before = self._seen
        found = self.scan()
        return found if [ep.id for ep in found] != before else None

    def apply(self, endpoint, chosen):
        local = endpoint.local_id
        if chosen:
            if local not in self.open:
                self.open[local] = self.backend.open_port(self._infos[local])
            endpoint.state = endpointkit.CONNECTED
        else:
            port = self.open.pop(local, None)
            endpoint.state = endpointkit.AVAILABLE
            if port is not None:
                port.close()

    def stop(self):
        for port in self.open.values():
            port.close()
        self.open.clear()


class Merged(PortIn):
    """Every chosen input as one port.

    It reads one port until it has nothing waiting, then the next, so a
    message is never cut by another port's bytes. ``take_timestamp`` hands
    out the stamps of the port it last read from.
    """

    def __init__(self, provider):
        PortIn.__init__(self)
        self.provider = provider
        self._order = []
        self._at = 0
        self._last = None

    def _ports(self):
        ports = list(self.provider.open.values())
        if ports != self._order:
            self._order = ports
            self._at = 0
        return ports

    def any(self):
        return sum(p.any() for p in self._ports() if hasattr(p, "any"))

    def readinto(self, buf, nbytes=None):
        ports = self._ports()
        for _ in range(len(ports)):
            port = ports[self._at % len(ports)]
            got = port.readinto(buf, nbytes)
            if got:
                self._last = port
                return got
            self._at += 1
        return None

    def read(self, nbytes=None):
        """The next waiting bytes from one chosen input, as ``bytes``, or
        ``None``. Each port's own ``read`` does the reading, so a SysEx comes
        out whole where that port hands one out whole."""
        ports = self._ports()
        for _ in range(len(ports)):
            port = ports[self._at % len(ports)]
            got = port.read(nbytes)
            if got:
                self._last = port
                return got
            self._at += 1
        return None

    def take_timestamp(self):
        return self._last.take_timestamp() if self._last is not None else None


class FanOut(PortOut):
    """Every chosen output at once: what you write goes to each."""

    def __init__(self, provider):
        self.provider = provider

    def write(self, buf, nbytes=None):
        n = len(buf) if nbytes is None else nbytes
        for port in list(self.provider.open.values()):
            port.write(buf, n)
        return n


_providers = {}


def register(registry=None, backend=None):
    """Register the host's MIDI inputs and outputs; returns ``(inputs, outputs)``.

    Registering again returns the providers already registered.
    """
    if not _providers:
        registry = registry or endpointkit.registry
        _providers[IN] = registry.register(HostMidi(IN, backend))
        _providers[OUT] = registry.register(HostMidi(OUT, backend))
    return _providers[IN], _providers[OUT]


def merged_in():
    """One port reading every chosen MIDI input. `register` first."""
    return Merged(_providers[IN])


def fan_out():
    """One port writing to every chosen MIDI output. `register` first."""
    return FanOut(_providers[OUT])
