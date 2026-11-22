# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""Providers with no hardware behind them, for tests and for trying a picker.

A `FakeProvider` finds the endpoints you give it, after as many polls as you
say, and records every start and stop the registry asks of it::

    import endpointkit
    from endpointkit.fake import FakeProvider

    bt = FakeProvider("audio.out", "a2dp", [("spk", "Speaker")], resources=("radio.bt",), delay=3)
    endpointkit.register(bt)
    endpointkit.select("audio.out", "a2dp:spk")   # chosen now, started when found
    for _ in range(3):
        endpointkit.poll()
    print(bt.started)                             # ['spk']

`bench` registers a set that stands in for a board's transports on a
desktop: I2S and Bluetooth audio, BLE and UART MIDI, Wi-Fi, Ethernet and
USB tethering, a CSI camera, ESP-NOW peers and a Thread network.
"""

import endpointkit


class FakeProvider(endpointkit.Provider):
    """A provider that finds what it's told to.

    Args:
        kind (str): the kind it provides.
        name (str): its name, the first part of its endpoint ids.
        found (list): ``(local_id, label)`` or ``(local_id, label, state)``
            for each endpoint.
        resources (tuple): the shared resources its endpoints take.
        delay (int): how many polls pass before the endpoints are found, to
            stand in for a slow scan. 0 finds them at once.
        fail (tuple): local ids whose start raises, to try error paths.
        secrets (dict): ``{local_id: (asks, secret)}`` for endpoints that
            ask for a password or a PIN to pair; `pair` refuses any other.
            An endpoint that needs pairing and isn't here pairs with nothing typed.

    Attributes:
        started (list): local ids started and not stopped, in order.
        log (list): ``("start", "stop" or "pair", local_id)`` for every call.
    """

    def __init__(self, kind, name, found=(), resources=(), delay=0, fail=(), secrets=None):
        endpointkit.Provider.__init__(self, kind, name, resources)
        self._want = [self._entry(e) for e in found]
        self._delay = delay
        self._dirty = False
        self.fail = list(fail)
        self.secrets = dict(secrets or {})
        self.started = []
        self.log = []

    @staticmethod
    def _entry(e):
        e = tuple(e)
        return [e[0], e[1], e[2] if len(e) > 2 else endpointkit.AVAILABLE]

    def _list(self):
        return [
            self.endpoint(i, label, state, asks=self.secrets[i][0] if i in self.secrets else None)
            for i, label, state in self._want
        ]

    def scan(self):
        return [] if self._delay else self._list()

    def poll(self):
        if self._delay:
            self._delay -= 1
            if self._delay:
                return None
            return self._list()
        if self._dirty:
            self._dirty = False
            return self._list()
        return None

    def apply(self, endpoint, chosen):
        local = endpoint.local_id
        self.log.append(("start" if chosen else "stop", local))
        if chosen:
            if local in self.fail:
                raise OSError("%s won't start" % endpoint.label)
            self.started.append(local)
        elif local in self.started:
            self.started.remove(local)

    def pair(self, endpoint, secret=None):
        local = endpoint.local_id
        self.log.append(("pair", local))
        if local in self.secrets and secret != self.secrets[local][1]:
            raise ValueError("Wrong %s for %s" % (self.secrets[local][0], endpoint.label))
        self.set_state(local, endpointkit.AVAILABLE)

    # -- changing what's found, reported on the next poll ------------------------

    def add(self, local_id, label, state=endpointkit.AVAILABLE):
        """Find another endpoint."""
        self._want.append([local_id, label, state])
        self._dirty = True

    def remove(self, local_id):
        """Lose an endpoint, as when a device is unplugged."""
        self._want = [e for e in self._want if e[0] != local_id]
        self._dirty = True

    def set_state(self, local_id, state):
        """Change an endpoint's state, as when a speaker connects."""
        for e in self._want:
            if e[0] == local_id:
                e[2] = state
        self._dirty = True


def bench(registry=None, delay=2):
    """Register fakes for a board's transports; returns them by name.

    Bluetooth audio, BLE MIDI and Bluetooth tethering share ``radio.bt``;
    Wi-Fi, ESP-NOW and the access point share ``radio.wifi``; Thread has the
    802.15.4 radio. Slow transports (Bluetooth, cast, ESP-NOW) take *delay*
    polls to find their endpoints.
    """
    registry = registry or endpointkit.registry
    endpointkit.add_kind("espnow.peer", endpointkit.MANY, "ESP-NOW peers", "hub")
    endpointkit.add_kind("thread.net", endpointkit.ONE, "Thread", "lan")
    na, cn = endpointkit.NEEDS_PAIRING, endpointkit.CONNECTED
    fakes = [
        FakeProvider("audio.out", "i2s", [("0", "Headphone jack")], ("i2s.0",)),
        FakeProvider("audio.out", "a2dp", [("spk", "Bluetooth speaker"), ("buds", "Earbuds", na)], ("radio.bt",), delay),
        FakeProvider("audio.in", "pdm", [("0", "Built-in mics")], ("i2s.1",)),
        FakeProvider("midi.in", "blemidi", [("pad", "BLE pad controller")], (), delay),
        FakeProvider("midi.in", "uart", [("1", "MIDI DIN in")], ("uart.1",)),
        FakeProvider("midi.out", "uartout", [("1", "MIDI DIN out")], ("uart.1",)),
        FakeProvider("net", "wlan", [("home", "Wi-Fi: home", cn), ("cafe", "Wi-Fi: cafe", na)], ("radio.wifi",),
                     secrets={"cafe": (endpointkit.PASSWORD, "espresso")}),
        FakeProvider("net", "eth", [("0", "Ethernet")], ("eth.0",)),
        FakeProvider("net", "usbnet", [("phone", "Phone tethering")], ("usb.host",)),
        FakeProvider("net", "btpan", [("phone", "Phone over Bluetooth", na)], ("radio.bt",), delay),
        FakeProvider("camera", "csi", [("0", "Camera module")], ("csi.0",)),
        FakeProvider("espnow.peer", "espnow", [("a", "Board A"), ("b", "Board B")], (), delay),
        FakeProvider("thread.net", "thread", [("home", "Thread: home")], ("radio.15_4",), delay),
    ]
    out = {}
    for f in fakes:
        registry.register(f)
        out[f.name] = f
    return out
