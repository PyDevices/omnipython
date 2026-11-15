# The board's name

Every board has one name, and everything that shows a name uses it: the
Wi-Fi hostname (so you reach the board as `NAME.local`), the setup access
point, Bluetooth LE services, Bluetooth Classic pairing, medialink and hmilink.
Read it or change it with `boarddev.name()`:

```python
import boarddev

print(boarddev.name())        # omnipython-a1b2c3
boarddev.name("kitchen")      # saved; the board is kitchen from its next start
boarddev.name(None)           # back to the default
```

A new name takes effect the next time each part starts: reset the board, or
reconnect Wi-Fi and restart the service.

## What a name can be

One label of letters, digits and hyphens, 1 to 20 characters, not starting or
ending with a hyphen. That works unchanged as a hostname and fits a Bluetooth
LE advertisement. Anything else raises `ValueError` before anything is saved:

```python
>>> boarddev.name("kitchen speaker")
ValueError: a board name holds only letters, digits and hyphens: 'kitchen speaker' has ' '
```

Case is kept as you type it. mDNS and DHCP compare names without case.

## The default, and where a name is kept

| Where | Default | A new name is kept in |
|---|---|---|
| ESP32 | `omnipython-` and the last three bytes of `machine.unique_id()` in hex | NVS, namespace `omnipython`, key `board_name` |
| Other MicroPython boards | the same | `/omnipython.json` (`/flash/omnipython.json` on an STM32) |
| CircuitPython | `omnipython-` and the last three bytes of `microcontroller.cpu.uid` | `OMNIPYTHON_BOARD_NAME` in `settings.toml` |
| A desktop | the computer's name | the `OMNIPYTHON_BOARD_NAME` environment variable, for this process |
| A browser | `omnipython-` and six random hex digits, new on each page load | the same, for this page |

On CircuitPython the board can't write `settings.toml` while a computer has
the CIRCUITPY drive mounted, so `boarddev.name("kitchen")` raises `OSError`.
Add the line from the computer instead:

```toml
OMNIPYTHON_BOARD_NAME = "kitchen"
```

On a desktop, `boarddev.name(new)` never renames the computer. Set the
environment variable to give a program a name of its own:

```bash
OMNIPYTHON_BOARD_NAME=kitchen python my_app.py
```

## Where it shows up

| Part | Uses the name when you don't pass one |
|---|---|
| [wifi_manager](wifi.md) | `connect()` and `run()` set it as the hostname before joining; the setup access point is named after it |
| [bledev](bluetooth-le.md) | `nus.serve()`, `repl.start()`, `filetransfer.start()`, `midi.serve()`, `improv.serve()` and the HID `Peripheral` advertise it |
| [medialink](medialink.md) | `MDNS`, `Hotspot` and `BLE` advertise it |
| hmilink | `tcp.serve(port, announce=True)` announces it over mDNS |
| [castdisplay](cast-to-a-tv.md) | the TV or laptop lists the cast under it |

Passing a name to any of these still wins: `wifi_manager.connect(hostname="garage")`
uses `garage` for that connection and saves nothing.
