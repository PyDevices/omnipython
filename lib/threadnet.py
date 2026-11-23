# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""A board's Thread networks as endpointkit ``thread.net`` endpoints, formed or joined from a picker.

Register the provider on a board whose firmware has the ``openthread``
module, and Thread networks nearby appear under ``thread.net``. One board
forms a network; the others join it with its dataset, the hex string any
Thread device shows for its network (OpenThread's ``dataset active -x``)::

    import endpointkit
    import threadnet

    threadnet.register()
    shared = threadnet.form("bench")             # on the first board: it leads
    # on another board, with the hex from the first:
    endpointkit.pair("thread:" + threadnet.extpanid(shared), shared)
    endpointkit.select("thread.net", "thread:" + threadnet.extpanid(shared))

A network is listed by its extended PAN ID and shown by its name. The one
in the board's dataset is connected once the board is a child, router or
leader on it; another one found nearby needs its dataset, or just its
16-byte network key as 32 hex digits, which `pair` combines with what the
search found (name, channels and PAN IDs). Choosing a network brings the
board's Thread interface up on it; letting it go takes the interface down.

Searching for networks takes a few seconds on the radio, so the provider
doesn't search on its own: `scan` (a picker's Scan button, through
`endpointkit.refresh`) starts one, and `endpointkit.poll` collects what it
found. A search waits while the board is attaching to a network. Between searches, `poll` looks every ``rescan_ms`` at the board's
role on its network, which costs nothing.

Thread has the board's 802.15.4 radio to itself, so the provider claims
``radio.15_4``: choosing a Thread network stops nothing on Wi-Fi or
Bluetooth. Its traffic stays inside the Thread network, through the
``openthread`` module's own UDP sockets, so the board's Wi-Fi or Ethernet
keeps its default route.
"""

import binascii

import endpointkit

try:
    import openthread
except ImportError:  # a desktop, or a build without Thread; `register` says so
    openthread = None

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
KIND = "thread.net"
#: How often, in milliseconds, `endpointkit.poll` reads the board's role.
RESCAN_MS = 2000
#: The roles in which a board is on its network.
ON_NETWORK = ("child", "router", "leader")

# Operational dataset TLV types (Thread 1.3, section 8.10).
_CHANNEL = 0
_PANID = 1
_EXTPANID = 2
_NAME = 3
_KEY = 5


def parse(dataset):
    """The parts of a Thread dataset that the provider reads, as a dict.

    Args:
        dataset (bytes or str): the dataset as TLVs, or as their hex.

    Returns:
        dict: ``name``, ``extpanid`` (hex), ``panid``, ``channel`` and
        ``key`` (hex), each None when the dataset doesn't carry it.

    Raises:
        ValueError: *dataset* isn't well-formed TLVs.
    """
    tlvs = _bytes(dataset)
    out = {"name": None, "extpanid": None, "panid": None, "channel": None, "key": None}
    i = 0
    while i < len(tlvs):
        if i + 2 > len(tlvs):
            raise ValueError("a Thread dataset ends inside a TLV")
        kind, n = tlvs[i], tlvs[i + 1]
        value = tlvs[i + 2 : i + 2 + n]
        if len(value) != n:
            raise ValueError("a Thread dataset ends inside a TLV")
        if kind == _CHANNEL and n == 3:
            out["channel"] = value[1] << 8 | value[2]
        elif kind == _PANID and n == 2:
            out["panid"] = value[0] << 8 | value[1]
        elif kind == _EXTPANID and n == 8:
            out["extpanid"] = _hex(value)
        elif kind == _NAME:
            out["name"] = bytes(value).decode()
        elif kind == _KEY and n == 16:
            out["key"] = _hex(value)
        i += 2 + n
    return out


def build(name, extpanid, panid, channel, key):
    """A dataset as TLVs from a network's name, IDs, channel and key.

    Enough for a board to join the network: once it's on, the leader
    gives it the rest (the mesh-local prefix, the security policy).

    Args:
        name (str): the network name.
        extpanid (str): the extended PAN ID, 16 hex digits.
        panid (int): the PAN ID.
        channel (int): the channel, 11 to 26.
        key (str): the network key, 32 hex digits.

    Raises:
        ValueError: a part is the wrong size.
    """
    key_b = _unhex(key, 16, "a network key")
    ext_b = _unhex(extpanid, 8, "an extended PAN ID")
    name_b = name.encode()
    if not 1 <= len(name_b) <= 16:
        raise ValueError("a Thread network name is 1 to 16 bytes")
    if not 11 <= channel <= 26:
        raise ValueError("Thread channels are 11 to 26, not %d" % channel)
    out = bytearray()
    out += bytes((_CHANNEL, 3, 0, channel >> 8, channel & 0xFF))
    out += bytes((_PANID, 2, panid >> 8, panid & 0xFF))
    out += bytes((_EXTPANID, 8)) + ext_b
    out += bytes((_NAME, len(name_b))) + name_b
    out += bytes((_KEY, 16)) + key_b
    return bytes(out)


def extpanid(dataset):
    """The extended PAN ID of *dataset* (TLVs or hex), as hex: the network's local endpoint id."""
    return parse(dataset)["extpanid"]


def _bytes(data):
    if isinstance(data, str):
        try:
            return binascii.unhexlify(data.strip())
        except (ValueError, TypeError):
            raise ValueError("a Thread dataset in hex has only hex digits")
    return bytes(data)


def _hex(data):
    return binascii.hexlify(bytes(data)).decode()


def _unhex(text, size, what):
    try:
        data = binascii.unhexlify(text.strip())
    except (ValueError, TypeError):
        data = b""
    if len(data) != size:
        raise ValueError("%s is %d hex digits" % (what, 2 * size))
    return data


class ThreadNet(endpointkit.Provider):
    """The board's Thread interface on its 802.15.4 radio.

    Args:
        ot: the ``openthread`` module, or a stand-in with its functions.
            Default: the firmware's, started.
        rescan_ms (int): how often `poll` reads the board's role. Default:
            `RESCAN_MS`.
    """

    kind = KIND
    name = "thread"
    resources = ("radio.15_4",)

    def __init__(self, ot=None, rescan_ms=None):
        endpointkit.Provider.__init__(self)
        self.ot = ot if ot is not None else _radio()
        self.rescan_ms = RESCAN_MS if rescan_ms is None else rescan_ms
        self._found = {}  # extpanid -> (name, panid, channel, rssi), from the last search
        self._datasets = {}  # extpanid -> TLVs, from pair
        self._searching = False
        self._last = _ticks_ms()
        self._shown = None

    def scan(self):
        if self.ot.role() != "detached":
            self._search()
        return self._list()

    def poll(self):
        if self._searching:
            got = self.ot.discovered()
            if got is not None:
                self._searching = False
                self._found = {}
                for name, ext, panid, channel, rssi in got:
                    self._found[ext] = (name, panid, channel, rssi)
                return self._list()
        if _ticks_diff(_ticks_ms(), self._last) < self.rescan_ms:
            return None
        before = self._shown
        found = self._list()
        return found if self._shown != before else None

    def apply(self, endpoint, chosen):
        if not chosen:
            if self.ot.up():
                self.ot.up(False)
            self._last = _ticks_ms() - self.rescan_ms
            return
        current = self._current()
        if current is None or current["extpanid"] != endpoint.local_id:
            dataset = self._datasets.get(endpoint.local_id)
            if dataset is None:
                raise OSError("%s needs its dataset or network key: join it first" % endpoint.label)
            if self.ot.up():
                self.ot.up(False)
            self.ot.dataset(dataset)
        if not self.ot.up():
            self.ot.up(True)
        self._last = _ticks_ms() - self.rescan_ms  # the next poll shows it attaching

    def pair(self, endpoint, secret=None):
        text = (secret or "").strip()
        if len(text) == 32:
            seen = self._found.get(endpoint.local_id)
            if seen is None:
                raise ValueError("Search for %s first, or give its whole dataset" % endpoint.label)
            name, panid, channel, _ = seen
            dataset = build(name, endpoint.local_id, panid, channel, text)
        else:
            try:
                info = parse(text)
            except ValueError:
                raise ValueError("A Thread network takes its dataset, or its network key as 32 hex digits")
            if info["key"] is None or info["channel"] is None or info["panid"] is None:
                raise ValueError("That dataset has no network key, channel or PAN ID")
            if info["extpanid"] != endpoint.local_id:
                raise ValueError("That dataset is for another network")
            dataset = _bytes(text)
        self._datasets[endpoint.local_id] = dataset
        self._shown = None  # the next poll shows it known

    def stop(self):
        if self.ot.up():
            self.ot.up(False)

    def form(self, name, channel=None):
        """Make a new network on this board, lead it, and return its dataset as hex.

        Give the hex to the boards that should join. The board leaves any
        network it was on.
        """
        dataset = self.ot.dataset_new(name, channel=channel)
        if self.ot.up():
            self.ot.up(False)
        self.ot.dataset(dataset)
        self._datasets[extpanid(dataset)] = dataset
        self.ot.up(True)
        self._shown = None
        self._last = _ticks_ms() - self.rescan_ms
        return _hex(dataset)

    def _search(self):
        if self._searching:
            return
        try:
            self.ot.discover()
            self._searching = True
        except OSError:
            # Busy attaching, or already searching: the list stays as it was.
            pass

    def _current(self):
        dataset = self.ot.dataset()
        return parse(dataset) if dataset else None

    def _list(self):
        self._last = _ticks_ms()
        current = self._current()
        role = self.ot.role()
        found = []
        snapshot = [role]
        if current is not None and current["extpanid"] is not None:
            ext = current["extpanid"]
            on = role in ON_NETWORK
            caps = {"role": role, "channel": current["channel"], "panid": current["panid"]}
            if on:
                caps["neighbors"] = len(self.ot.neighbors())
            seen = self._found.get(ext)
            caps["rssi"] = seen[3] if seen else None
            state = endpointkit.CONNECTED if on else endpointkit.AVAILABLE
            found.append(self.endpoint(ext, current["name"] or ext, state, caps))
            snapshot.append((ext, state, caps.get("neighbors")))
        else:
            ext = None
        for other in sorted(self._found, key=lambda e: -self._found[e][3]):
            if other == ext:
                continue
            name, panid, channel, rssi = self._found[other]
            caps = {"role": None, "channel": channel, "panid": panid, "rssi": rssi}
            if other in self._datasets:
                found.append(self.endpoint(other, name, endpointkit.AVAILABLE, caps))
            else:
                found.append(self.endpoint(other, name, endpointkit.NEEDS_PAIRING, caps, asks=endpointkit.PASSWORD))
            snapshot.append((other, other in self._datasets))
        self._shown = snapshot
        return found


def _radio():
    """The firmware's ``openthread`` module, started."""
    if openthread is None:
        raise ImportError("threadnet needs the openthread module, which this build lacks")
    openthread.start()
    return openthread


_provider = []
_registry = []


def register(registry=None, ot=None):
    """Make the ``thread.net`` kind known, register the board's Thread once, and choose the network it's on.

    When the board is already on a Thread network and ``thread.net`` has
    no choice yet, that network is chosen. Registering again returns the
    provider already registered.

    Args:
        registry (endpointkit.Registry): where to register; endpointkit's own when None.
        ot: as in `ThreadNet`.

    Raises:
        ImportError: the firmware has no ``openthread`` module.
    """
    if not _provider:
        endpointkit.add_kind(KIND, endpointkit.ONE, "Thread", "lan")
        registry = registry or endpointkit.registry
        provider = registry.register(ThreadNet(ot))
        _provider.append(provider)
        _registry.append(registry)
        current = provider._current()
        if current is not None and provider.ot.role() in ON_NETWORK and not registry.chosen(KIND):
            registry.select(KIND, "thread:" + current["extpanid"])
    return _provider[0]


def form(name, channel=None):
    """Make a new network through the registered provider, and choose it; see `ThreadNet.form`."""
    if not _provider:
        raise RuntimeError("call threadnet.register() first")
    shared = _provider[0].form(name, channel)
    registry = _registry[0]
    registry.refresh(KIND)
    registry.select(KIND, "thread:" + extpanid(shared))
    return shared
