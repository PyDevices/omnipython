# CircuitPython's APIs on MicroPython and CPython

Code written for CircuitPython's own modules can often run unchanged on
MicroPython-compatible firmware or on a desktop, because OmniPython provides
those modules under their CircuitPython names. This page says which ones, where
each runs, and where it differs from CircuitPython.

Where a module is in both CircuitPython and OmniPython, OmniPython follows
CircuitPython's names, arguments and behaviour. Where it can't, the difference is
listed under the module. On CircuitPython itself you use CircuitPython's own
native modules, so nothing here runs there unless it says so.

## At a glance

| Module | MicroPython firmware | Desktop CPython | Comes from |
|---|---|---|---|
| `audiocore`, `audiomixer`, `synthio`, `audiofilters`, `audiodelays`, `audiofreeverb`, `audiospeed`, `audiomp3` | yes | yes | [audiodsp](#audio) |
| `audiobusio.I2SOut`, `audioi2sin.I2SIn` | yes, with `audioif` built in | no | [audioif](#audio-hardware) |
| `jpegio` | yes, with `jpegio` built in | yes, over Pillow | [jpegio](#jpegio) |
| `mdns` | yes, on ESP32, RP2 with Wi-Fi, unix and Windows | yes, over python-zeroconf | [mdns](#mdns) |
| `wifi` | yes | no | [wifi](#wifi) |
| `usb_hid` | yes, on boards that can be a USB device | no | [usb_hid](#usb-hid) |
| `mipidsi`, `dotclockframebuffer`, `picodvi`, `rgbmatrix` | yes, on the chips named [below](#display-hardware) | no | [displayif](#display-hardware) |
| `picotts` | yes, opt-in, needs PSRAM | no | [picotts](#picotts) |
| `espcamera` | yes, on the ESP32-P4 | no | [cameraif](#espcamera) |
| `ulab` | yes, with `ulab` built in | no | [ulab](#ulab) |

"With X built in" means the firmware has to be built with that module. The
default `all` set includes each firmware module here except `picotts`, which is
opt-in, as
[Modules](https://docs.omnipython.org/en/latest/firmware/reference/modules.html)
lists. `wifi` and `usb_hid` are Python packages, installed with `mip`.

Not on this page: CircuitPython's `displayio`, `digitalio`, `busio` and `board`.
MicroPython has its own `machine` for pins and buses, and OmniPython's
[board config](../boards/board-contract.md) names a board's peripherals. A
CircuitPython program that uses those modules directly doesn't run on
MicroPython as it stands.

## Audio

[audiodsp](https://github.com/PyDevices/audiodsp/blob/main/docs/reference/modules.md)
gives MicroPython and CPython CircuitPython's audio modules with the same import
names: `audiocore` (`WaveFile` and `RawSample`), `audiomixer`, `synthio`
(including `MidiTrack`), `audiofilters`, `audiodelays`, `audiofreeverb`,
`audiospeed` and `audiomp3`. They follow CircuitPython's `play()`, `stop()`,
`pause()` and `resume()` behaviour too. On a desktop, `pip install
omnipython-audiodsp` brings them; in firmware, the `audiodsp` module does.

Where one of them behaves differently from the CircuitPython you have, the
[upstream differences](https://github.com/PyDevices/audiodsp/blob/main/docs/how-it-works/upstream-diff.md)
page says where.

### Audio hardware

The audio modules make sound but don't send it anywhere. On MicroPython
firmware built with `audioif`, `audiobusio.I2SOut` and `audioi2sin.I2SIn` do:

```python
import audiobusio, audiocore, board

out = audiobusio.I2SOut(board.GPIO12, board.GPIO13, board.GPIO14)
out.play(sample, loop=True)
```

CircuitPython's own `I2SOut` example runs unchanged apart from the three pins.
It differs in a few ways: a second `I2SOut` raises `"Peripheral in use"` as in
CircuitPython, `pause()` leaves the bus clocking zeros instead of disabling the
channel, and `left_justified` and `external_clock` raise `NotImplementedError`.
`I2SOut` also takes a few extras (`port=`, `sample_rate=`, `main_clock_fs=`,
`data_in=` and `sink=`, which writes to a file on a desktop build).
[audioif](https://github.com/PyDevices/omnipython-builds/blob/main/modules/audioif/README.md)
has the details, and [Portable audio](../guides/audio.md) shows the same sound
reaching hardware on every platform. `audiobusio` isn't available on desktop CPython: use `audiodev`
there.

## jpegio

`jpegio.JpegDecoder` has CircuitPython's API on MicroPython firmware built with
`jpegio`, and on a desktop in `omnipython-desktop`, where it runs over Pillow.
The firmware module also has a `JpegEncoder`, which CircuitPython doesn't. Output
is RGB565. The
[stub](https://github.com/PyDevices/omnipython-builds/blob/main/modules/jpegio/jpegio.pyi)
lists each argument.

## mdns

`mdns.Server` announces what a device offers on the network and finds what
others offer, with CircuitPython's API. On firmware it runs on ESP32, on RP2
boards with a CYW43 radio, on unix and on Windows. A browser build has none. On a
desktop, `omnipython-desktop`'s `mdns.py` gives the same API over python-zeroconf.
See [mdns](../guides/mdns.md).

## wifi

`wifi.radio` over `network.WLAN`, so board code that joins a network runs
unchanged:

```python
import wifi
wifi.radio.connect("ssid", "password")
print(wifi.radio.ipv4_address, wifi.radio.ap_info.rssi)
```

It differs from CircuitPython in these ways:

- Addresses are strings, not `ipaddress.IPv4Address`.
- `wifi.ConnectionError` is a subclass of `OSError`, so catch `OSError` to run on both.
- `connect(..., timeout=0)` starts joining and returns at once. `channel=` is accepted and ignored.
- `Network.authmode` is the port's integer.
- There is no `socketpool`: use `socket` or `requests`.

To join from `secrets.py` or a network the board remembered, use
[`wifi_manager`](../guides/wifi.md), which also runs on CircuitPython.

## usb_hid

CircuitPython's `usb_hid` on MicroPython boards that can be a USB device, from
the `usb-hid` package, over `usb-device-hid`. `usb_hid.enable()` takes
CircuitPython's `Device` objects, including the custom gamepad and absolute
pointer. See [USB, both ways round](../guides/usb.md).

## Display hardware

The display modules in
[displayif](https://github.com/PyDevices/omnipython-builds/tree/main/modules/displayif)
keep CircuitPython's names where there is a CircuitPython module of the same job:

| Module | Runs on |
|---|---|
| `mipidsi` | ESP32-P4, i.MX RT 1176, STM32H747 and H757 |
| `dotclockframebuffer` | ESP32 (RGB LCD), i.MX RT 1062 |
| `picodvi` | RP2040 and RP2350 |
| `rgbmatrix` | ESP32-S3, i.MX RT 1062, SAMD51, RP2 |

On a port that isn't listed, the constructor raises. Boards running
CircuitPython have these modules natively.

The arguments aren't always CircuitPython's: each module's stub, such as
[`mipidsi.pyi`](https://github.com/PyDevices/omnipython-builds/blob/main/modules/displayif/mipidsi.pyi),
has the exact signature. [Displays](../guides/displays.md) shows how a program
reaches any of them through `displaydev`.

## picotts

Text to speech on the board, behind the API of Adafruit's `adafruit_picotts`.
You hand it an OmniPython audio output instead of CircuitPython's `audiobusio`
object, and import it as `picotts`. It needs PSRAM and a firmware built with the
opt-in `picotts` module. See the
[picotts README](https://github.com/PyDevices/omnipython-builds/blob/main/modules/picotts/README.md).

## espcamera

On an ESP32-P4, `cameraif` is also importable as `espcamera`, with that module's
properties (`brightness`, `contrast`, `saturation`) alongside `cameraif`'s own.
The
[cameraif README](https://github.com/PyDevices/omnipython-builds/blob/main/modules/cameraif/README.md#written-for-espcamera)
says where a program written for `espcamera` needs a change.

## ulab

OmniPython firmware can carry `ulab`, the same project CircuitPython builds in.

## Everything else

A CircuitPython module that isn't on this page isn't provided on MicroPython or
CPython. If you need one,
[open an issue](https://github.com/PyDevices/omnipython/issues).
