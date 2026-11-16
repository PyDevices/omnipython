# Bluetooth LE: REPL, files, pairing, MIDI and HID

Ready-made services built on `bledev`: a REPL and file transfer over
Bluetooth, pairing and bonding for them, Wi-Fi setup, BLE-MIDI, and keyboards,
mice and gamepads. [The Bluetooth LE guide](bluetooth-le.md) covers the
adapter, serving and connecting, and the byte stream the first two are built on;
[Bluetooth LE support](../reference/bluetooth-le-support.md) says what each host
can do. `ble` below is an adapter from that guide.

## A REPL over Bluetooth

`examples/bledev_repl_simpletest.py` is the board's side in a few lines.

A board can offer its REPL over nus, behind a password, the way WebREPL does
over Wi-Fi. It's opt-in; put this in `main.py`:

```python
import bledev.repl
bledev.repl.start(password="correct horse", name="rack")   # or webrepl_cfg.PASS
```

`start()` returns at once, and the REPL keeps being served at the `>>>`
prompt and while your program runs; Ctrl-C over Bluetooth interrupts a running
program. From a laptop or another board:

```python
import bledev.repl
link = await bledev.repl.connect(ble, "correct horse", name="rack")
print(await bledev.repl.run(link, "1 + 1"))    # "2"
```

Leave `name` out on both sides and the board advertises under
[its own name](board-name.md), and `connect()` finds the first board serving
the REPL.

The REPL runs beside WebREPL and owns the radio while it runs; `bledev.repl.stop()` gives it back. The link isn't encrypted, as with WebREPL, so [pair](#pairing-and-bonding) if someone nearby could sniff the password. Any terminal that speaks Nordic UART works too; the login protocol and what happens when both consoles are wanted are in [the internals page](../how-it-works/bledev-internals.md#details-the-guide-leaves-out).

## Files over Bluetooth

`examples/bledev_filetransfer_simpletest.py` is the board's side in a few lines.

`bledev.filetransfer` is the board side of CircuitPython's BLE file-transfer
protocol, so a MicroPython board serves files the same way a CircuitPython one
does, and one client reaches both. It's opt-in, like the REPL; in `main.py`:

```python
import bledev.filetransfer
bledev.filetransfer.start(password="correct horse", name="rack")   # files and the REPL
```

From a laptop or another board:

```python
import bledev.filetransfer as ft
files = await ft.connect(ble, "correct horse", name="rack")
await files.write("/lib/app.py", source)
print(await files.read("/lib/app.py"))
print(await files.listdir("/lib"))      # [(name, size, is_directory, mtime_ns), ...]
await files.mkdir("/data/logs")         # parents too
await files.move("/a.txt", "/data/a.txt")
await files.delete("/data")             # a directory and everything in it
```

`write()` takes an `offset`, and the file ends after what you wrote.
`read()` takes one too. The board paces every write with a free-space count,
so it never receives more than it can hold.

It's locked the way the REPL is, with the same password or [pairing](#pairing-and-bonding). The protocol has no checksum beyond the radio's own, so check what matters (mcuctl compares SHA-256 after every transfer). It's MicroPython only, and while it runs it owns the radio. 20 KB moves in a second or two; [more detail](../how-it-works/bledev-internals.md#details-the-guide-leaves-out).

## Pairing and bonding

Pairing encrypts the link and, with a passkey, proves who's on the other end.
It's off unless you ask; the password alone stays the default. On a board with
a display, use a passkey:

```python
import bledev.filetransfer
bledev.filetransfer.start(password=False, name="rack", pairing="passkey")
```

The first time a computer connects, the board draws a six-digit passkey on its
screen (and prints it to the console) and the computer asks for it. After that
the two are bonded: they reconnect encrypted, with no passkey, until one of
them forgets. `password=False` makes the passkey the only lock. From a laptop
or another board, pair when you connect, and pass the passkey or a function
that asks for it:

```python
link = await bledev.repl.connect(ble, name="rack", pair=True, passkey=lambda: input("Passkey: "))
files = await bledev.filetransfer.connect(ble, name="rack", passkey=ask)
```

On Windows pass `pair=True` rather than waiting for the board to ask; Windows
answers a late request out of sight and pairing fails. To pair a computer
once for tools that don't pair themselves (mcuctl), `python -m bledev.bleak
pair rack` asks for the passkey in the terminal, and `unpair rack` undoes it.

The other modes, for `bledev.repl.start()` and `bledev.filetransfer.start()`:

| `pairing=` | What the board does | Password |
|---|---|---|
| `None` (the default) | no pairing | required |
| `"passkey"` | shows a passkey the host types in | optional |
| `"justworks"` | pairs with no passkey; encrypted, but anyone can pair | required |
| `"numeric"` | shows a number both sides confirm; `confirm(number)` answers for the board (a button) | optional |
| `"auto"` | `"passkey"` with a display, `"justworks"` without | as above |

A board draws the passkey on `board_config.display_drv`; pass `show(passkey)`
and `hide()` to put it somewhere else.

**Where the keys live.** On an ESP32 they're in NVS, not the filesystem, so
reformatting the filesystem keeps them. A full chip erase
(`mcuctl firmware flash --erase`) loses them, and so does
`bledev.security.forget()`. On other boards they're in `ble_secrets.json`.

**When the board has lost its keys** and the computer still has its half, the
reconnect fails with `PairingError` ("unpair it on this host"). Unpair the
board on the computer (`python -m bledev.bleak unpair rack`, or Settings >
Bluetooth > Remove device) and pair again. A phone is the same: forget the
device, then pair. The same happens if you serve something else on the board
under the same address (HID, say), because hosts cache a paired device's
services. [How pairing gets there](../how-it-works/bledev-internals.md#how-pairing-gets-there)
has the reasons.

## Wi-Fi setup with Improv

`examples/bledev_improv_simpletest.py` is the board's side in a few lines.

`bledev.improv` speaks [Improv](https://www.improv-wifi.com/ble/), the BLE
Wi-Fi setup standard ESPHome, WLED and Home Assistant use. A board without
credentials serves it until someone provisions it:

```python
import bledev.improv as improv
url = await improv.serve(ble, name="kitchen")   # returns once the board has joined
```

Anything that speaks Improv can then set it up: Home Assistant, the Improv web
page, or another bledev host:

```python
url = await improv.provision(ble, ssid, password, name="kitchen")
```

A network the board can't join raises `improv.ImprovError` with
`code == improv.ERROR_UNABLE_TO_CONNECT`. Saving the credentials for the next
boot is up to you: pass `on_join=lambda ssid, password, ip: ...` to `serve()`.
`require_authorization=True` makes the board wait for `server.authorize()`
(from a button, say) before it accepts credentials. The credentials cross the
air unencrypted; that's the standard.

## MIDI

`bledev.midi` is BLE-MIDI, the standard every Mac, iPhone, Android phone,
DAW and Bluetooth MIDI controller speaks. The board advertises it; anything
else connects:

```python
import bledev.midi as midi

port = await midi.serve(ble, name="synth")      # on the board
port = await midi.connect(ble, name="synth")    # on a laptop or another board
```

What you get is a MIDI port in the shape of CircuitPython's `usb_midi`
ports, so Adafruit's `adafruit_midi` reads and writes it, and the script you
run over USB or a 5-pin cable runs over BLE with only the line that opens the
port changed:

```python
import adafruit_midi
from adafruit_midi.note_on import NoteOn

midi = adafruit_midi.MIDI(midi_in=port, midi_out=port, in_buf_size=512)
midi.send(NoteOn(60, 100))
while True:
    if port.any():
        msg = midi.receive()
        while msg is not None:
            ...
            msg = midi.receive()
    await asyncio.sleep(0.001)
```

The port follows the [`midiports`](https://github.com/PyDevices/omnipython/blob/main/packages/midiports/README.md) contract. `ts, message = await port.receive()` gives messages with the sender's timestamp; [the rest](../how-it-works/bledev-internals.md#details-the-guide-leaves-out) covers sizes, SysEx and drains.

On a board, ask for the shortest connection interval: `midi.connect(ble, name="synth", min_conn_interval_us=7500, max_conn_interval_us=7500)`.

## Keyboards, mice and gamepads (HID)

`bledev.hid` turns a BLE keyboard, mouse, media remote or game controller
into the same `events` SDL gives you on the desktop: `events.Key` with `keys.K_*` codes and modifiers,
`events.Motion`, `Button` and `Wheel` for a mouse, and
`events.JoyAxisMotion`, `JoyHatMotion`, `JoyButtonDown` and `JoyButtonUp`.
Your app can't tell which one it's talking to.

```python
import bledev.hid as hid

host = await hid.connect(ble, name="Keyboard K380")   # or no name: any HID device
while True:
    for event in await host.events():                 # waits for at least one
        print(event)
```

`host.poll()` returns whatever has arrived without waiting, the way usbif's
`poll()` does, so it fits a frame loop. Media keys arrive as `Key` events
too (`keys.K_VOLUMEUP`, `K_AUDIOPLAY`). Axes run from -1.0 to 1.0 and are
numbered X, Y, Z, Rx, Ry, Rz, then triggers; buttons count from 0; a hat is
an `(x, y)` tuple with y up. A mouse's buttons are numbered as SDL does
(1 left, 2 middle, 3 right), and since a mouse only reports movement, `pos`
is where its motion has taken it from (0, 0); set `host.decoder.bounds =
(width, height)` to keep it on your screen.

A keyboard that wants an encrypted link gets one ([details](../how-it-works/bledev-internals.md#details-the-guide-leaves-out)); call `ble.enable_bonding()` once before connecting so the keys are kept.

**A board can be the keyboard, too.** It advertises as a keyboard, mouse and
media remote (and a gamepad if you ask), and its `devices` are CircuitPython's
`usb_hid.devices`, so Adafruit's `adafruit_hid` drives them exactly as it
drives USB:

```python
from adafruit_hid.consumer_control import ConsumerControl
from adafruit_hid.consumer_control_code import ConsumerControlCode
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS
from adafruit_hid.keycode import Keycode
from adafruit_hid.mouse import Mouse

per = hid.Peripheral(ble)                 # keyboard, mouse, consumer control
await per.serve()                         # returns when a host connects
kb = Keyboard(per.devices)
KeyboardLayoutUS(kb).write("Hello\n")
kb.send(Keycode.CONTROL, Keycode.C)
ConsumerControl(per.devices).send(ConsumerControlCode.VOLUME_INCREMENT)
Mouse(per.devices).move(x=40, y=-12)
```

Install `adafruit_hid` on MicroPython with `mip.install("github:PyDevices/omnipython/bledev_hid")`. `bledev.hid_gamepad` adds the gamepad `adafruit_hid` lacks, for `Peripheral(ble, gamepad=True)`. A board can also act as a presence key that notices a bonded phone arriving; both, and how a host caches a device's identity, are in [the internals page](../how-it-works/bledev-internals.md#details-the-guide-leaves-out).

**Don't pair a test board with the computer you're testing from.** Once paired, Windows and phones use it as a real keyboard, and it types into them.

The parser underneath, `bledev.hidreport`, knows nothing about Bluetooth: give it any HID report descriptor and it decodes that device's reports. See [How HID gets there](../how-it-works/bledev-internals.md#how-hid-gets-there).
