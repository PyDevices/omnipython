# midiports

MIDI ports for Adafruit's [`adafruit_midi`](https://docs.circuitpython.org/projects/midi/en/latest/),
on MicroPython and desktop Python. Your MIDI code is CircuitPython's: the
same `MIDI` object, the same `NoteOn` and `ControlChange` messages. This
package supplies the two ports `MIDI` reads and writes, for each way MIDI
can reach you:

```python
import adafruit_midi
from adafruit_midi.note_on import NoteOn

from midiports import usb_device
midi_in, midi_out = usb_device.ports()        # the board is a USB MIDI device

midi = adafruit_midi.MIDI(midi_in=midi_in, midi_out=midi_out)
midi.send(NoteOn(60, 100))
while True:
    msg = midi.receive()
    if msg is not None:
        print(msg)
```

On a desktop, `pip install omnipython-desktop` installs `midiports` and
`adafruit_midi` together; on a board, install with `mip`.

To use another transport, change the line that opens the ports:

| Transport | The ports line |
|---|---|
| USB, the board as a device | `usb_device.ports()` |
| USB, a keyboard or synth plugged into the board | `usb_host.ports()` |
| USB, every MIDI device plugged into the board, merged | `usb_host.all_ports()` |
| A UART (5-pin DIN, TRS, board to board) | `uart.ports(1, tx=17, rx=18)` |
| Bluetooth LE, the board as an instrument a controller, phone or computer connects to | `ble.ports("Synth")` |
| Windows' MIDI ports (a keyboard, loopMIDI, a DAW) | `windows.ports("loopMIDI")` |
| Windows' loopback, for trying MIDI with no hardware | `windows.ports(midiports.LOOPBACK)` |
| Linux raw MIDI | `linux.ports("DMK25")` |
| Linux, 5-pin DIN on a serial port (a Pi's UART) | `linux.serial_ports("/dev/ttyAMA0")` |
| Web MIDI, in a browser page (Pyodide) | `await webmidi.open("DMK25")` |
| Web MIDI, in a browser page (MicroPython) | `webmidi.page_in("DMK25")`, `webmidi.page_out("synth")` |
| Web MIDI, in a Web Worker, relayed by the page | `webmidi.relay_ports(port)` |

Import each from `midiports`.

Over Bluetooth LE the board advertises the standard BLE-MIDI service under the
name you give, and advertises again when a link drops. `ble.available()` says
whether the firmware has Bluetooth without starting it, so a program can offer
the choice and start nothing until it's picked. When a link drops with notes
still sounding, the input hands out a note-off for each, so none is left
hanging. It needs [`bledev`](../../docs/guides/bluetooth-le.md), and `aioble` on
MicroPython; an app with no event loop of its own needs nothing more, as each
`any()` runs Bluetooth's tasks. To make the board the central that connects to
a named controller instead, use `bledev.midi.connect`.

An Android phone works as the keyboard. Plug it into the board's host port,
pick **MIDI** in its USB settings (the notification that appears when it's
plugged in), and open a free pad or keyboard app such as MIDIPadidi: the
phone is then a USB MIDI device, and `usb_host.ports()` opens it like any
other. It's a high-speed device, so on an ESP32-P4 it needs no
`full_speed=True`, even behind a hub.

It works the other way round too: the phone can play the board. Plug the
board's native USB port into the phone with a USB-C cable, so the phone is
the host, and call `usb_device.ports()` on the board. Android lists the board
as a MIDI device, and a synth app that takes USB MIDI input, such as Perfect
Piano in its Keyboard mode, plays what the board sends.

[`examples/midiports_simpletest.py`](examples/midiports_simpletest.py) plays a scale; on Windows you hear it from the built-in synth.

## Install

On a board, with `mip`:

```python
import mip
mip.install("github:PyDevices/omnipython/packages/midiports")
```

That fetches `midiports` and Adafruit's `adafruit_midi`, pinned to a release
tag. MIDI over USB also needs micropython-lib's `usb-device-midi` and a
firmware with `machine.USBDevice`. Install it first from MicroPython's own
index, unless your firmware already has it frozen in:

```python
mip.install("usb-device-midi")
```

It needs version 0.1.1 or later. With 0.1.0, a fast burst from the computer fills the
board's schedule queue, and the board stops receiving MIDI until it resets. The index
has had 0.1.1 since September 2026, but a firmware that freezes the package may carry
0.1.0.

From a computer, `mpremote mip install github:PyDevices/omnipython/midiports`
does the same.

From release 0.7.6, `midiports` is in the OmniPython index too, so a board
config can `require("midiports")` and you can install it by name:

```python
omip.install("midiports")
```

`omip` comes with OmniPython firmware. On other MicroPython firmware, run
`mip.install("github:PyDevices/omnipython/lib/omip.py")` once to put it on the board.

That installs `midiports` alone, because `adafruit_midi` isn't in any mip
index. If your board doesn't have it, use the `github:` install above, which
fetches both.

On desktop Python, the Windows port needs `uwin32` from `omnipython-desktop`.
`midiports` isn't on PyPI yet, so put this folder on your path. Adafruit
publishes `adafruit_midi` there as `adafruit-circuitpython-midi`.

## Try MIDI with no hardware

On Windows, a loopback port lets two programs talk MIDI to each other with no
keyboard, board or cable: what one writes to the port's output comes out of its
input. `midiports.LOOPBACK` is its name, `"PyDevices Loopback"`. Make sure it
exists with desktop Python:

```text
> python -m midiports.loopback
PyDevices Loopback: created
Windows didn't save it because it has no MIDI configuration yet, so it lasts until the MIDI service restarts or Windows reboots. Run midisettings.exe once as administrator and finish its first-run setup, then run python -m midiports.loopback again.
```

It makes the port with [Windows MIDI Services](https://aka.ms/midi) (Windows 11),
and says so if `midi.exe` isn't installed. When Windows has no MIDI configuration yet, the port only lasts until the MIDI service restarts or Windows reboots; run Windows MIDI Services' settings app (`midisettings.exe`) once as administrator and finish its first-run setup, and the port is saved from then on. Run it again any time: it says
`present` when the port is there and changes nothing. `--check` only reports,
and exits 1 when the port is missing, for a script that wants to stop early.

Then open it from CPython or from MicroPython on Windows:

```python
import time

import midiports
from midiports import windows

midi_in, midi_out = windows.ports(midiports.LOOPBACK)
buf = bytearray(16)
midi_out.write(bytes([0x90, 60, 100]), 3)
time.sleep(0.1)
n = midi_in.readinto(buf)
print("read", n, bytes(buf[:n]).hex())
midi_out.close()
midi_in.close()
```

```text
read 3 903c64
```

Two programs work the same way: one opens the ports and writes, the other
opens them and reads. Start the reader first.

Other systems have their own loopback, and the command names it rather than
making one. On Linux, `sudo modprobe snd-virmidi` adds virtual MIDI cards, and
the "Midi Through" port that ALSA provides loops back too; open either with
`linux.ports("Midi Through")`. On macOS, turn on the IAC Driver in Audio MIDI
Setup.

## The ports

The contract is CircuitPython's `usb_midi`. An input port has
`read(nbytes)`, which returns `bytes`, or `None` when nothing has arrived,
and `readinto(buf, nbytes)`. An output port has `write(buf, nbytes)`. None
of them block. The [package docstring](packages/midiports/__init__.py) has the whole
contract.

Input ports hand out whole messages. A 5-pin cable sends running status
(the status byte left off repeated messages) and may put a clock byte in the
middle of a note, and `adafruit_midi` reads neither. So the UART and Linux
ports wrap their input in `midiports.WholeMessages`, which fixes both. Wrap
any other byte stream the same way. USB-MIDI and Windows already deliver
whole messages, and so does Web MIDI.

A port that polls beside audio should call `readinto` with a buffer of its
own. `read` makes a new `bytes` for every message that arrives, though an
empty poll allocates nothing.

## When each message arrived

Every input port keeps the time each message arrived, so a looper or a
recorder can place notes where they were played, not where your loop got
round to them. Call `midi_in.take_timestamp()` once for each message
`receive()` gives you, whatever its type, clocks included:

```python
import midiports

msg = midi.receive()
if msg is not None:
    when = midi_in.take_timestamp()      # microseconds, or None
    played_ago = midiports.ticks_diff(midiports.ticks_us(), when)
```

Times are whole microseconds: `time.ticks_us()` on MicroPython, which wraps,
so subtract with `midiports.ticks_diff`; `time.monotonic_ns() // 1000` on
CPython and CircuitPython; Web MIDI's own `performance.now()` clock in a
browser. Leave `MIDI`'s `in_channel` at its default and filter on
`msg.channel` yourself, because a message `adafruit_midi` filters out never
reaches you but its time would.

How close a time is depends on the transport:

| Port | Stamped | As fine as |
|---|---|---|
| `usb_device` | in the USB event callback | one USB frame (1 ms at full speed), plus the wait for the scheduled callback |
| Web MIDI | by the browser | the browser's event time |
| `uart`, `linux`, `windows`, `usb_host` | by the read that finds the bytes | how often you poll |

The [package docstring](packages/midiports/__init__.py) has the rules: one time per
message in order, how running status, SysEx and a message split across reads
are stamped, and what happens if you don't take them.

## In a browser

Python running in Pyodide reaches MIDI devices through Web MIDI. The browser
asks the person for permission the first time.

On the page (Pyodide on the main thread, as PyScript runs it), `open` is
awaitable:

```python
from midiports import webmidi

midi_in, midi_out = await webmidi.open("DMK25", sysex=False)
midi = adafruit_midi.MIDI(midi_in=midi_in, midi_out=midi_out)
```

The name matches part of a port's name, ignoring case. Leave it out to merge
every input and send to the first output. A device plugged in later, or
unplugged and plugged back in, joins while the ports are open. If you
already hold a `MIDIAccess`, `webmidi.ports(access, "DMK25")` does the same
without awaiting. Sending SysEx needs `sysex=True`.

In MicroPython's WebAssembly port, `webmidi.page_in("DMK25")` opens an input
and `webmidi.page_out("synth")` an output, both without awaiting and with no
timestamps. The browser asks for MIDI in the background, so `midi_in.names` and
`midi_out.names` stay empty until the person says yes, and `why` says why if the
answer was no. `midi_out.names` lists every output that matches, and
`midi_out.name` is the one it sends to; until there is one, writes are dropped
and counted in `midi_out.dropped`.

Web MIDI doesn't exist in a Web Worker, so a worker gets its MIDI from the
page over a `MessagePort`, and a few lines of JavaScript on the page relay
it. Open the worker's end with `webmidi.relay_ports(port)`. The relay's
messages are plain objects:

| Direction | Message |
|---|---|
| page to worker | `{data: Uint8Array, timeStamp: number}`: one whole MIDI message per post, `timeStamp` from its `MIDIMessageEvent` |
| worker to page | `{data: Uint8Array}`: whole messages to `send()` to the page's output |

Every Web MIDI input keeps the browser's time for each message; see
[When each message arrived](#when-each-message-arrived). The
[module docstring](packages/midiports/webmidi.py) has the details, including which
clock a worker's relayed times are on.

## Limits

- Windows: a write holds a SysEx until its 0xF7, then returns once the port
  has sent it, so a long one blocks for as long as it takes to send.
- Linux: MicroPython's unix port can list ports but not open them, since its
  `os` has no `open` or `read`. CPython opens them.
- Linux serial: `serial_ports()` sets MIDI's 31250 baud through the driver's
  custom-rate call, and raises if the driver can't come within 1% of it. A
  Pi whose UART clock was changed so that 38400 comes out as 31250 takes
  `baudrate=38400`. The framing is tested over a pseudo-terminal; a real
  5-pin jack on a serial port hasn't been tried yet.
- USB: if the host stops reading, messages that don't fit within a few
  milliseconds are dropped and counted in `MIDIPortsInterface.dropped`, so
  your loop never stalls.
- `usb_host` needs `usb.core` (the `usb-core` package) and a firmware with a
  USB host. On an ESP32-P4 with the keyboard behind a hub, call
  `usb.core.start(full_speed=True)` before `ports()`.
- `usb_host.all_ports()` hears every MIDI device on the host at once, and
  ones plugged in later. It never splits one device's message with
  another's, so a long SysEx from one holds the rest until it ends. Writes
  go to every device.
