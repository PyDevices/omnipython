# bledev: Bluetooth Low Energy

You write one BLE program and it runs on a board, on a laptop, in a browser, or
against a pretend radio in your tests. `bledev` is async throughout and shaped
like [aioble](https://github.com/micropython/micropython-lib/tree/master/micropython/bluetooth/aioble),
so if you know aioble you already know most of it.

The quickest useful thing is a byte stream between a board and anything else:

```python
import asyncio
import bledev.mpble
import bledev.nus as nus

async def main():
    ble = bledev.mpble.get()
    link = await nus.serve(ble, name="rack")    # the board advertises; you connect
    await link.write(b"hello\n")
    async for line in link:                     # lines until the other side hangs up
        await link.write(b"you said " + line)

asyncio.run(main())
```

The other side runs the same code with `nus.connect(ble, name="rack")`. That's
the Nordic UART service, so nRF Connect on a phone and Workbench's Bluetooth
transport can talk to it too.

## What runs where

| Backend | Host | Central (scan, connect) | Peripheral (advertise, serve) |
|---|---|---|---|
| `bledev.mpble` | MicroPython with `bluetooth` (ESP32, S3, P4 + C6, Pico W) | yes | yes |
| `bledev.cpble` | CircuitPython with `_bleio` (ESP32-S3 measured) | yes | yes |
| `bledev.bleak` | CPython on Windows, Linux, macOS | yes | no |
| `bledev.webble` | Browsers: PyScript, the Workbench simulator | yes | no |
| `bledev.fake` | Anywhere: tests | yes | yes |

Roles aren't symmetric. A laptop or a browser can only scan and connect, so
when a board talks to one, the board advertises. Only board-to-board links put
a board in the central role. `ble.capabilities()` tells you which roles you
have, and anything a backend can't do raises `bledev.UnsupportedError` rather
than doing nothing.

[Bluetooth LE support](../reference/bluetooth-le-support.md) lists what each host can do and what it can't.

## Installing it

On a board:

```python
import omip
omip.install("bledev")
```

That brings aioble with it. [Bring up a
board](bring-up-a-board.md#2-installing-over-wi-fi) shows how to get
`omip` onto a board that doesn't have it. Plain `mip` takes every file from the
one index you give it, so install aioble first, once per board:

```python
import mip
mip.install("aioble")
mip.install("bledev", index="https://lib.omnipython.org")
```

Firmware that freezes aioble doesn't need it. On a laptop, bledev is inside
the `omnipython` wheel, and `pip install --pre "omnipython[ble]"` adds bleak, which
the laptop backend needs.

CircuitPython has its own steps: `omip.install("bledev")` works on a board with
Wi-Fi, and the files can be copied by hand. They are in
[On CircuitPython](../reference/bluetooth-le-support.md#on-circuitpython).

## Getting an adapter

The adapter is one radio. On a board with a OmniPython board config, it's the
`ble` role:

```python
from board_config import ble    # a bledev adapter
```

It still answers every `bluetooth.BLE` method (`active()`, `gap_advertise()`,
`gatts_notify()`), so code written for the raw radio keeps working. The one
difference is `ble.irq(handler)`: your handler runs beside aioble's instead of
replacing it. A board without bledev installed gets the raw `bluetooth.BLE()`,
as before. Without a board config:

```python
import bledev.mpble
ble = bledev.mpble.get()        # the board has one radio, so get() shares one adapter
```

On a laptop:

```python
import bledev.bleak
ble = bledev.bleak.BleakBLE()   # central only
```

On CircuitPython ([copied onto the board by hand](../reference/bluetooth-le-support.md#installing-bledev), with the `asyncio` library):

```python
import bledev.cpble
ble = bledev.cpble.get()        # CircuitPython's _bleio.adapter, both roles
```

Anywhere, if you don't want to name the backend:

```python
import bledev.auto
ble = bledev.auto.adapter()     # mpble, cpble, webble or bleak, whichever this host has
```

`bledev.auto` is optional, and nothing else in bledev imports it. Set
`BLEDEV_BACKEND=fake` to force the fake one.

## Serving a service (peripheral)

Describe the service, register it, then advertise. `advertise()` returns when
a central connects:

```python
import bledev

SENSOR = bledev.UUID("12345678-1234-5678-1234-56789abcdef0")

service = bledev.Service(SENSOR)
level = bledev.Characteristic(service, 0x2A19, read=True, notify=True, initial=b"\x64")
command = bledev.Characteristic(service, "12345678-1234-5678-1234-56789abcdef1",
                                write=True, capture=True, max_len=64)
ble.register_services(service)

connection = await ble.advertise(name="sensor", services=[SENSOR])
level.notify(connection, b"\x63")
peer, data = await command.written()          # capture=True: every write, in order
```

`register_services()` replaces whatever was registered before, so register
everything at once, before you advertise. Call `advertise()` again to accept
another connection.

## Standard services

Phones and fitness apps already know the Bluetooth SIG's services, so serving
one gets you a screen in an app you didn't write. Each is a small class whose
`service` you pass to `register_services()` with the rest:

The table of services and their modules is in [Bluetooth LE support](../reference/bluetooth-le-support.md#what-the-parts-give-you).

```python
from bledev.battery import Battery
from bledev.deviceinfo import DeviceInformation

battery = Battery(level=87)
info = DeviceInformation(manufacturer="PyDevices", model="rack-1", firmware="0.3.0")
ble.register_services(battery.service, info.service)
connection = await ble.advertise(name="rack", services=[battery.SERVICE])
battery.set_level(86)               # subscribed centrals are notified
```

The cycling and running services each have a control point that a central
writes and the board answers by indication: run `sensor.run()` as a task. Each
module's docstring lists what its measurement carries, and each has an
example under `examples/` named `bledev_<service>.py` that a phone app can
read.

## Connecting to one (central)

```python
device = await ble.find(name="sensor")        # or find(service=SENSOR)
async with await device.connect() as connection:
    service = await connection.service(SENSOR)
    level = await service.characteristic(0x2A19)
    print(await level.read())
    await level.subscribe()
    while True:
        print(await level.notified())
```

`find()` scans actively, so it sees a name that only fits in the scan
response. For more control, scan yourself:

```python
async with ble.scan(5000, active=True) as scanner:
    async for result in scanner:
        print(result.device, result.rssi, result.name(), result.services())
```

A device can come back more than once as its advertisement and scan response
arrive, and `device.name` is whatever the scan had seen by then.

## In a browser

`bledev.webble` runs the same code in Chrome or Edge, on desktop or Android,
under PyScript (Pyodide or MicroPython) or the MicroPython WebAssembly build
Workbench uses. The page must be served from `https://` or `http://localhost`.

```python
from bledev.webble import WebBLE
import bledev.nus as nus

ble = WebBLE(mtu=247)                       # see below for the MTU
link = await nus.connect(ble, name="rack")  # call this from a click or tap
```

Three things differ from a board:

- **The browser's chooser is the scan.** `find()` and `nus.connect()` open
  it, and the person picks the device. It only opens during a click or tap,
  so start from one. `scan()` raises `UnsupportedError`.
- **Only services you name are reachable.** The one in `find()`'s filter is;
  list any others as `WebBLE(services=[...])`.
- **The browser won't tell you the MTU.** `connection.mtu` is 23 unless you
  pass `WebBLE(mtu=...)`, and writes are sized to it. Chrome asks for a large
  MTU on every connect (a board running nus ends up at 247), but a write
  longer than the link carries can be cut short without an error, so only
  raise it when you know. At 23 everything still works, about five times
  slower.

A Web Bluetooth page can be tested without a person: Chrome's DevTools
protocol can answer the chooser. How the gate was run on a phone and a
laptop is in [bledev-internals.md](../how-it-works/bledev-internals.md#webble).

## Byte streams with nus

`bledev.nus` gives you a `Link` from either end, and it reads like an asyncio
stream: `read(n)`, `readexactly(n)`, `readline()`, `write(data)`, `close()`,
and `async for line in link`. `write()` splits your data to the link's MTU and
handles a full transmit buffer for you. `read()` returns `b""` at end of
stream, and only after everything that arrived before the disconnect has been
read.

`nus.serve()` registers the Nordic UART service on the adapter the first time
you call it, so don't register other services on that adapter afterwards. It
can serve several links at once; each gets only its own central's bytes.

On a board, `nus.connect(ble, name=..., min_conn_interval_us=7500,
max_conn_interval_us=15000)` asks for a short connection interval, which
raises a round trip's throughput by about half (see [How fast it goes](#how-fast-it-goes)).

From a laptop, `nus.connect(ble, name=..., priority="throughput")` asks
Windows for its short-interval parameters. It speeds up an echo by about a
fifth and a file transfer by about half (see [How fast it goes](#how-fast-it-goes)).

## A changing address

A board that advertises with the same address every time can be followed from
place to place by anyone who scans. Ask for a resolvable private address and
it advertises under an address that changes about every fifteen minutes, which
only a phone that bonded with the board can match to it:

```python
ble.config(addr_mode=bledev.ADDR_MODE_RPA)    # before advertise() or scan()
connection = await ble.advertise(name="rack", services=[SENSOR])
```

`ADDR_MODE_NRPA` uses an address that rotates and that nobody can resolve,
for a broadcaster that never connects. `ADDR_MODE_PUBLIC` is the board's own
address, and `ADDR_MODE_RANDOM` a fixed random one. `ble.config("addr_mode")`
reads the mode back. MicroPython on NimBLE (the ESP32 family)
supports all four; the Pico W's BTstack has no RPA or NRPA, and
`UnsupportedError` says so. CircuitPython, a laptop and a browser have no such
setting. [`examples/bledev_private_address.py`](../../examples/bledev_private_address.py)
shows it running.

## More services

A REPL and file transfer over Bluetooth, pairing and bonding, Wi-Fi setup with Improv, BLE-MIDI, and HID keyboards, mice and gamepads are on [their own page](bluetooth-le-services.md).

## On CircuitPython

The same code runs on a CircuitPython board with `bledev.cpble`, in either
role, and `adafruit_midi` and `adafruit_hid` work over BLE through
`bledev.midi` and `bledev.hid`. A few things differ, because `_bleio` has no
async calls and fewer features; [On CircuitPython](../reference/bluetooth-le-support.md#on-circuitpython)
lists them, with how to copy bledev onto a board.

## How fast it goes

Two ESP32-S3s a metre apart, MicroPython 1.30 preview, Wi-Fi off, 16 KB each
way verified byte for byte. "7.5 ms" is a connection interval of 7.5 to 15 ms
asked for in `connect()`.

| Over nus | Default interval | 7.5 ms interval |
|---|---|---|
| Central to peripheral (writes) | 44-70 KB/s | 57-70 KB/s |
| Peripheral to central (notifications) | 28-38 KB/s | 34-35 KB/s |
| Echo round trip, each way | 19-27 KB/s | 31-35 KB/s |

A laptop (Windows, bleak) to an S3 moves 59-68 KB/s up, 40-48 KB/s down and
32-38 KB/s echoed each way (40-47 with `priority="throughput"`). A single GATT
read or write takes two connection intervals: 100 ms at the default and 31 ms
at 7.5 ms. A note crosses a link in a median 46 ms at the default interval and
9 ms at 7.5 ms, so a MIDI link wants the shortest interval. Turning the radio
on costs about 62 KB of the S3's internal RAM.

## Testing without a radio

`bledev.fake` is an in-process loopback that runs on CPython and MicroPython.
Adapters on the same `Air` see each other:

```python
from bledev.fake import Air, FakeBLE

air = Air()
board = FakeBLE(air=air)                      # either role, like a board
laptop = FakeBLE(air=air, peripheral=False)   # central only, like bleak
```

It's stricter than a radio on purpose, and it models what trips people up on
hardware: a name that only reaches an active scan, a transmit buffer that fills
(`notify_buffers`), and a reader that falls behind (`queue_limit`). The rules
it enforces are in [the internals page](../how-it-works/bledev-internals.md#the-rules-every-backend-keeps).
`tests/bledev_contract.py` is a plain script, so it runs on both interpreters:
`python tests/bledev_contract.py` or `micropython tests/bledev_contract.py`.

## Writing a backend

A backend subclasses the classes in `bledev/__init__.py` and fills in a few
hooks. What each hook must do, how the fake and mpble do it, and the checks
to run are in [bledev internals](../how-it-works/bledev-internals.md).
