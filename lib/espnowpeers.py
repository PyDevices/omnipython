# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""Boards nearby as endpointkit ``espnow.peer`` endpoints, found and chosen over ESP-NOW.

Register the provider on each board, and every board running it within
radio range appears under ``espnow.peer``, by its name (`boarddev.name`).
Choose one or more, then send to them and read what they send back::

    import endpointkit
    import espnowpeers

    espnowpeers.register()
    endpointkit.poll()                    # from a timer: finds boards and reads
    endpointkit.select("espnow.peer", [ep.id for ep in endpointkit.endpoints("espnow.peer")])
    espnowpeers.send(b"hello")            # to every chosen board
    got = espnowpeers.recv()              # (endpoint id, bytes) or None

Boards find each other with a short broadcast, a beacon carrying the
board's name, sent every ``beacon_ms`` from `endpointkit.poll` and at once
when a new board is heard. A board heard within ``forget_ms`` is listed;
after that silence it drops out of the list, and a chosen one stays chosen
and is used again when it's heard. Choosing a board adds it to ESP-NOW's
peers; letting it go removes it. Only chosen boards' messages are kept,
up to `INBOX` of them; older ones are dropped and counted.

Nothing waits: `poll` reads what has arrived without blocking, at most
`MAX_READS` messages a call, and sends without waiting for an answer.

ESP-NOW rides on the Wi-Fi radio and its channel, alongside a Wi-Fi
connection, so the provider claims no resource: choosing a board stops
nothing, and two boards talk only while they're on the same channel (on the
same access point, or neither joined to one). Every message this module
sends starts with two bytes that mark it, so its beacons and messages
pass by other ESP-NOW programs, and theirs pass by it. A message carries at
most `MAX_DATA` bytes.

This runs on MicroPython's ``espnow`` module. CircuitPython's ``espnow`` has
another API (``ESPNow.send(message, peer)``, ``read()`` returning packets,
peers as ``espnow.Peer`` objects in ``ESPNow.peers``), so `register` raises
there until the provider gets a CircuitPython radio of its own.
"""

import binascii
import sys

import boarddev
import endpointkit

try:
    import espnow
except ImportError:  # a desktop, or a build without ESP-NOW; `register` says so
    espnow = None

try:
    import network
except ImportError:
    network = None

try:
    from time import ticks_diff as _ticks_diff
    from time import ticks_ms as _ticks_ms
except ImportError:  # CPython
    import time as _time

    def _ticks_ms():
        return int(_time.monotonic() * 1000)

    def _ticks_diff(a, b):
        return a - b


#: The kind's name.
KIND = "espnow.peer"
#: How often, in milliseconds, a board says it's here.
BEACON_MS = 2000
#: How long, in milliseconds, a board stays listed after it was last heard.
FORGET_MS = 7000
#: The most messages one `poll` or `recv` reads from the radio.
MAX_READS = 16
#: How many chosen boards' messages wait for `recv`.
INBOX = 16
#: The longest message `send` takes, in bytes: ESP-NOW's 250 less the mark.
MAX_DATA = 248

_BEACON = b"\xe5B"
_DATA = b"\xe5D"
_BROADCAST = b"\xff" * 6


def _hex(mac):
    return binascii.hexlify(mac).decode()


def _benign(exc, code):
    """True when *exc* is ESP-NOW's *code* error (a peer already added, or already gone)."""
    return code in str(exc)


class EspNowPeers(endpointkit.Provider):
    """The boards in ESP-NOW range that run this provider too.

    Args:
        esp: the ESP-NOW interface, active, as MicroPython's
            ``espnow.ESPNow()`` gives it. Default: the board's own.
        name (str): what this board calls itself in its beacon. Default:
            `boarddev.name`.
        beacon_ms (int): how often the beacon goes out. Default: `BEACON_MS`.
        forget_ms (int): how long a board stays listed after its last
            beacon or message. Default: `FORGET_MS`.

    Attributes:
        dropped (int): chosen boards' messages dropped because `INBOX` was full.
        ignored (int): messages that weren't this module's, or were from
            boards not chosen.
    """

    kind = KIND
    name = "espnow"
    # ESP-NOW shares the radio with Wi-Fi rather than taking it, and every
    # resource endpointkit knows is taken whole: naming the radio here would
    # make two peers, or a peer and the Wi-Fi network, refuse each other.
    resources = ()

    def __init__(self, esp=None, name=None, beacon_ms=None, forget_ms=None):
        endpointkit.Provider.__init__(self)
        self.esp = esp if esp is not None else _radio()
        self.board_name = name if name is not None else boarddev.name()
        self.beacon_ms = BEACON_MS if beacon_ms is None else beacon_ms
        self.forget_ms = FORGET_MS if forget_ms is None else forget_ms
        self.dropped = 0
        self.ignored = 0
        self._heard = {}  # mac hex -> [mac bytes, name, last heard ms]
        self._added = {}  # mac hex -> mac bytes, the peers this provider added
        self._inbox = []  # (endpoint id, bytes), oldest first
        self._shown = None  # what the last list showed, to tell when it changes
        self._beacon_now = True
        self._last_beacon = 0
        self._add(_BROADCAST)
        self._beacon = _BEACON + self.board_name.encode()

    def scan(self):
        return self._list()

    def poll(self):
        self._read()
        now = _ticks_ms()
        if self._beacon_now or _ticks_diff(now, self._last_beacon) >= self.beacon_ms:
            self._beacon_now = False
            self._last_beacon = now
            self.esp.send(_BROADCAST, self._beacon, False)
        for key in list(self._heard):
            if _ticks_diff(now, self._heard[key][2]) > self.forget_ms:
                del self._heard[key]
        if self._snapshot() == self._shown:
            return None
        return self._list()

    def apply(self, endpoint, chosen):
        key = endpoint.local_id
        if chosen:
            heard = self._heard.get(key)
            mac = heard[0] if heard else binascii.unhexlify(key)
            self._add(mac)
            self._added[key] = mac
        elif key in self._added:
            self._remove(self._added.pop(key))
        self._shown = None  # the next poll shows the new state

    def stop(self):
        for mac in self._added.values():
            self._remove(mac)
        self._added.clear()
        self._remove(_BROADCAST)

    def send(self, data, to=None):
        """Send *data* to every chosen board, or to the one with endpoint id *to*.

        Returns how many boards it went to. It doesn't wait for them to
        answer, so a board out of range doesn't slow it down.

        Raises:
            ValueError: *data* is longer than `MAX_DATA`, or *to* isn't chosen.
        """
        if len(data) > MAX_DATA:
            raise ValueError("ESP-NOW carries %d bytes at most, not %d" % (MAX_DATA, len(data)))
        if to is None:
            macs = list(self._added.values())
        else:
            key = to.split(":", 1)[1] if ":" in to else to
            if key not in self._added:
                raise ValueError("%s isn't a chosen ESP-NOW peer" % to)
            macs = [self._added[key]]
        msg = _DATA + data
        for mac in macs:
            self.esp.send(mac, msg, False)
        return len(macs)

    def recv(self):
        """The oldest message from a chosen board, as ``(endpoint id, bytes)``, or None."""
        self._read()
        if not self._inbox:
            return None
        return self._inbox.pop(0)

    def _add(self, mac):
        try:
            self.esp.add_peer(mac)
        except OSError as exc:
            if not _benign(exc, "ESPNOW_EXIST"):
                raise

    def _remove(self, mac):
        try:
            self.esp.del_peer(mac)
        except OSError as exc:
            if not _benign(exc, "ESPNOW_NOT_FOUND"):
                raise

    def _read(self):
        esp = self.esp
        now = _ticks_ms()
        for _ in range(MAX_READS):
            mac, msg = esp.recv(0)
            if mac is None:
                return
            head = msg[:2]
            key = _hex(mac)
            if head == _BEACON:
                try:
                    name = bytes(msg[2:]).decode()
                except UnicodeError:
                    self.ignored += 1
                    continue
                heard = self._heard.get(key)
                if heard is None:
                    self._heard[key] = [bytes(mac), name, now]
                    self._beacon_now = True  # answer, so it finds this board as fast
                else:
                    heard[1] = name
                    heard[2] = now
            elif head == _DATA and key in self._added:
                heard = self._heard.get(key)
                if heard is not None:
                    heard[2] = now
                if len(self._inbox) >= INBOX:
                    self._inbox.pop(0)
                    self.dropped += 1
                self._inbox.append(("%s:%s" % (self.name, key), bytes(msg[2:])))
            else:
                self.ignored += 1

    def _snapshot(self):
        return sorted((key, h[1], key in self._added) for key, h in self._heard.items())

    def _list(self):
        self._shown = self._snapshot()
        table = getattr(self.esp, "peers_table", None) or {}
        found = []
        for key, name, added in sorted(self._shown, key=lambda s: (s[1], s[0])):
            mac = self._heard[key][0]
            rssi = table.get(mac)
            caps = {
                "mac": binascii.hexlify(mac, ":").decode(),
                "rssi": rssi[0] if rssi else None,
            }
            state = endpointkit.CONNECTED if added else endpointkit.AVAILABLE
            found.append(self.endpoint(key, name, state, caps))
        return found


def _radio():
    """The board's ESP-NOW interface, active, with the Wi-Fi station up to carry it."""
    if sys.implementation.name == "circuitpython":
        raise NotImplementedError(
            "espnowpeers runs on MicroPython's espnow; CircuitPython's espnow has another API",
        )
    if espnow is None or network is None:
        raise ImportError("espnowpeers needs MicroPython's espnow and network modules, which this build lacks")
    sta = network.WLAN(network.STA_IF)
    if not sta.active():
        sta.active(True)  # ESP-NOW needs the radio on; joining a network is left to wifi_manager
    esp = espnow.ESPNow()
    esp.active(True)
    return esp


_provider = []


def register(registry=None, esp=None, name=None):
    """Make the ``espnow.peer`` kind known and register this board's ESP-NOW once.

    Registering again returns the provider already registered.

    Args:
        registry (endpointkit.Registry): where to register; endpointkit's own when None.
        esp, name: as in `EspNowPeers`.

    Raises:
        NotImplementedError: on CircuitPython, whose ``espnow`` this doesn't drive yet.
        ImportError: the build has no ``espnow``.
    """
    if not _provider:
        endpointkit.add_kind(KIND, endpointkit.MANY, "ESP-NOW peers", "hub")
        registry = registry or endpointkit.registry
        _provider.append(registry.register(EspNowPeers(esp, name)))
    return _provider[0]


def send(data, to=None):
    """Send *data* to the chosen boards through the registered provider; see `EspNowPeers.send`."""
    return _registered().send(data, to)


def recv():
    """The oldest message from a chosen board through the registered provider; see `EspNowPeers.recv`."""
    return _registered().recv()


def _registered():
    if not _provider:
        raise RuntimeError("call espnowpeers.register() first")
    return _provider[0]
