# endpointkit

One list of everything a device can connect to, by kind, and one choice per
kind for the whole device: where audio goes, which MIDI ports are in, which
network carries traffic, which camera, which cast target. It runs on
MicroPython and desktop Python and draws nothing, so a script can list and
pick, and a picker on screen can sit on top.

```python
import endpointkit
from endpointkit.fake import FakeProvider

endpointkit.register(FakeProvider("audio.out", "i2s", [("0", "Headphone jack")], ("i2s.0",)))
speaker = FakeProvider("audio.out", "a2dp", [("spk", "Speaker")], ("radio.bt",), delay=2)
endpointkit.register(speaker)

endpointkit.subscribe("audio.out", lambda event, kind: print(event, kind))
endpointkit.select("audio.out", "a2dp:spk")  # chosen now, used when found

while not endpointkit.selected("audio.out"):
    endpointkit.poll()  # call this from a timer in a real program

for ep in endpointkit.endpoints("audio.out"):
    print(ep.id, ep.label, ep.state)
print("playing on", speaker.started)
```

prints

```text
selection audio.out
endpoints audio.out
selection audio.out
i2s:0 Headphone jack available
a2dp:spk Speaker available
playing on ['spk']
```

`FakeProvider` stands in for a transport with no hardware behind it. A real
transport is a `Provider` subclass in the library that owns it: it says which
kind it provides, which shared resources it takes (a radio, the USB port, an
I2S bus), what it finds, and how to start and stop an endpoint.

On a computer, these register the real ones:

| Kind | Register with |
|---|---|
| `audio.out`, `audio.in` | `from audiodev import endpoints; endpoints.register()` |
| `midi.in`, `midi.out` | `from midiports import endpoints; endpoints.register()` |
| `cast.target` (Rokus) | `from castdisplay import endpoints; endpoints.register()` |
| `keys`, `pointer`, `gamepad` | `from displaydev import endpoints; endpoints.register()` |
| `net` (reported, never changed) | `import hostnet; hostnet.register()` |

On a board with Wi-Fi, `import wifinet; wifinet.register()` lists the
networks in range under `net`, and a picker joins them, asking for a new
network's password ([Wi-Fi guide](../../docs/guides/wifi.md#join-from-a-picker)).
Boards that each run `import espnowpeers; espnowpeers.register()` find one
another over ESP-NOW under a new kind, `espnow.peer`, and
`espnowpeers.send` and `espnowpeers.recv` talk to the ones chosen
([espnowpeers](../../lib/espnowpeers.py)).

The kinds are `audio.out`, `audio.in`, `midi.in`, `midi.out`, `net`,
`cast.target`, `camera`, `gamepad`, `keys`, `pointer` and `assistant` (the
chat server an assistant app talks to). `add_kind("storage", MANY,
"Storage", "sd_card")` adds another, with what a person calls it and its
Material Symbols icon, so a picker shows it like the built-in ones;
`title(kind)` and `icon(kind)` read them back. A choice that would stop something using the same resource raises
`Conflict` naming what it stops, so you can ask first and pass
`confirm=True`. An endpoint in the `NEEDS_PAIRING` state (a Wi-Fi network
not yet joined, a Bluetooth device) says in `asks` whether pairing wants a
`PASSWORD` or a `PIN`, and `pair("wlan:cafe", "its password")` hands that to
its provider, which keeps it; `select` it after. A program can `pin` a kind
for itself while it runs. Set a
file with `set_store` and choices survive a restart.

Install on a board with `mip`:

```python
import mip
mip.install("github:PyDevices/omnipython/packages/endpointkit")
```

Run its checks from the repo root with `python packages/endpointkit/tests/run.py`
or `micropython packages/endpointkit/tests/run.py`.
