# wifi_manager

`wifi_manager` gets a board onto Wi-Fi without putting a password in your
code. It joins a network the board already knows. When none is in range, it
can turn the board into a small access point with a setup page, so you pick
the network and type its password on your phone. The board remembers every
network it joins.

```python
import wifi_manager

ip = wifi_manager.connect()
```

It runs on MicroPython and CircuitPython. It's part of the `omnipython`
package, so a firmware that freezes OmniPython already has it. Otherwise:

```python
import omip
omip.install("omnipython")
```

`omip` comes with OmniPython firmware. On other MicroPython firmware, run
`mip.install("github:PyDevices/omnipython/lib/omip.py")` once to put it on the board.

On CircuitPython, copy [`lib/wifi_manager.py`](https://github.com/PyDevices/omnipython/blob/main/lib/wifi_manager.py) to the board's `/lib`.

## Three kinds of app

How you call it depends on what your app does without a network. Here are
the three cases: an app that can't work without the network, one that works
offline, and one that only needs Wi-Fi while you maintain it.

### The app needs the network

A voice assistant, a dashboard or anything that fetches what it shows is no
use offline. Call `connect()` before anything else. It returns once the board
has an address, and if no known network is in range it stays in setup mode
until you've given it one:

```python
import wifi_manager

ip = wifi_manager.connect(hostname="kitchen-panel")
```

A weak link fails a join now and then. `connect()` tries every known network
twice before it decides none is there, so a board at the edge of your router's
range still joins at boot rather than showing the setup page. If your board
lives somewhere marginal, call it with `setup=False` a couple of times first,
and only then without.

### The app works without it

A synthesizer that can also stream, or a sensor that uploads when it can,
should start at once and join quietly when it can. Pass `setup=False`:
`connect()` then returns `None` instead of starting setup mode, and the app
carries on offline.

```python
ip = wifi_manager.connect(setup=False, hostname="devkit")
if ip is None:
    print("offline")
```

Give the user a way to add a network later, such as a "Wi-Fi setup" button,
that calls `wifi_manager.run()`. `run()` starts setup mode even when a known
network is in range, and waits until you've picked a new one.

Call `run()` from your main loop, not from inside a timer or a button's
callback. Setup mode keeps your app's timers (and LVGL) running by delivering
them from its own waits, and it can't do that from inside one of them. From a
callback, hand the work on: set a flag your loop checks, or use
`micropython.schedule`.

### Wi-Fi only for maintenance

A watch or a battery sensor doesn't need Wi-Fi to do its job. You only want
it when you're updating files or poking at the REPL, and a radio left on
drains the battery. Join when you ask for it, start WebREPL, and turn both
off when you're done:

```python
import network
import webrepl
import wifi_manager

def wifi_on():
    ip = wifi_manager.connect(setup=False, hostname="watch")
    if ip:
        webrepl.start()   # the password is PASS in /webrepl_cfg.py
    return ip

def wifi_off():
    wifi_manager.cancel()  # in case setup mode is waiting
    webrepl.stop()
    network.WLAN(network.STA_IF).active(False)
```

If no known network is in range, offer `run()` to add one. Call `cancel()`
when the user leaves while setup mode is still waiting: `run()` returns
`None` and the access point goes away. Keep the board awake while Wi-Fi is
on, because a light sleep drops the link.

## Reaching the board over Wi-Fi

With the board's remote access on, [mcuctl](https://github.com/PyDevices/mcuctl)
and Workbench can reach it without a cable. Each interpreter uses the files it
already reads, so stock firmware needs nothing from PyDevices.

**MicroPython.** Put a `secrets.py` on the board with `WIFI_SSID` and
`WIFI_PASSWORD`, then run `mcuctl wifi enable` over USB. It shows you the change
and writes two files: `/webrepl_cfg.py` with `PASS = "..."` (4 to 9 characters),
and a block at the top of `boot.py` that joins the network with `network.WLAN`
and calls `webrepl.start()`. Set a `hostname` when you connect, and the board
answers as `NAME.local`:

```bash
mcuctl put secrets.py /secrets.py
mcuctl wifi enable
mcuctl exec -d ws://kitchen-panel.local "print(1 + 1)"
```

`mcuctl wifi disable` puts both files back as they were. If the board has
`wifi_manager`, the block tries `wifi_manager.connect(setup=False)` first, so
it joins any network the board remembers; without it the block joins the one in
`secrets.py`.

**CircuitPython.** The same `secrets.py`, or `CIRCUITPY_WIFI_SSID` and
`CIRCUITPY_WIFI_PASSWORD` already in `settings.toml`. `mcuctl wifi enable` puts
the missing settings, and `CIRCUITPY_WEB_API_PASSWORD`, at the top of
`settings.toml`; reset the board and it serves CircuitPython's web workflow.
CircuitPython has no WebREPL, so `webrepl_cfg.py` is MicroPython-only.
`wifi_manager` reads the same `settings.toml` and `secrets.py`.

WebREPL and the web workflow have no encryption, so treat their passwords as a
courtesy lock on your own network. mcuctl's
[Connect over Wi-Fi](https://github.com/PyDevices/mcuctl/blob/main/docs/guides/connect-over-wifi.md)
has the details.

## Slow replies: turn off power saving

By default an ESP32 saves power by letting its Wi-Fi radio sleep between the
access point's beacons. Anything sent to the board waits until the radio
next wakes. An app that asks and waits for each reply pays that delay on
every request: a picture, a REPL line, a ping. That includes
request-and-reply protocols like the camera examples and WebREPL.

A long TCP stream from the board pays too, because its acknowledgements come
back through the same radio. When they go missing, the board stops sending
for a second or two until TCP tries again. On a P4 with a C6 for Wi-Fi,
streaming camera video for 25 seconds at a time, 12 of 36 runs stopped like
that with power saving on, and none of 36 with it off.

On a P4 sending 27 KB camera pictures one request at a time, at -60 to
-65 dBm:

| Link | Median per picture | Slowest |
|---|---|---|
| Ethernet | 62 ms | 103 ms |
| Wi-Fi, power saving on (the default) | 300 to 690 ms | 7.9 s |
| Wi-Fi, power saving off | 110 to 210 ms | 2.4 s |

`wifi_manager.connect()` turns power saving off on a board with no
battery, and leaves it on for one with a battery fitted (its `battery` role
reads a voltage). Choose for yourself with `set_power_save()`, which
remembers the choice across boots along with the networks:

```python
import wifi_manager
wifi_manager.set_power_save(False)  # always awake: answers at once
wifi_manager.set_power_save(True)   # sleeps between beacons: saves battery
wifi_manager.set_power_save(None)   # back to the default
```

The same goes with Bluetooth on. ESP-IDF shares the radio between Wi-Fi and
Bluetooth in time slices, with power saving or without. On a classic ESP32
running as a Bluetooth speaker, with power saving on it lost 83% of pings,
and its page took up to 11 s to load or didn't load at all. With it off, it
lost no pings, the page loaded in under 2 s every time, and the music played
just as cleanly.

For a change that lasts only until the next join, set the radio directly,
on CircuitPython or on MicroPython with OmniPython's `wifi`:

```python
import wifi
wifi.radio.power_management = wifi.PowerManagement.NONE
```

Power saving also makes pings lie. An idle board in power saving answers
pings in 100 to 900 ms however good the signal is. To judge the link, read
the signal strength (`wifi.radio.ap_info.rssi`) instead, or measure with
power saving off.

## Setup mode

When setup mode starts, the board shows how to reach it, on its display when
it has one and always on the REPL:

1. Join the network named after the board, such as `omnipython-a1b2c3`
   ([the board's name](board-name.md)), with the password shown. A phone camera can join from the QR code.
2. The phone opens the setup page by itself. If it doesn't, browse to
   http://192.168.4.1.
3. Pick your network, type its password, press Join.

The board joins, remembers the network and carries on. If the password was
wrong, the page says so and you can try again. A hidden network goes in
"Other" on the page.

Setup mode started by `connect()` also looks for a known network every
minute, so a board that booted while the router was down joins by itself
once it's back. Setup mode started by `run()` doesn't: you asked for a new
network, so it waits for one.

The page is drawn in LVGL when the board has `lvgl` and `display_driver`,
otherwise with `pygraphics` on `board_config.display_drv`. With neither, the
REPL is the only screen. The QR code needs `lv.qrcode`, or `adafruit_miniqr`
for the `pygraphics` page.

## Which networks it knows

`connect()` knows the network in `secrets.py` (`WIFI_SSID` and
`WIFI_PASSWORD`), the one in CircuitPython's `settings.toml`
(`CIRCUITPY_WIFI_SSID` and `CIRCUITPY_WIFI_PASSWORD`), and every network it
has joined before. Once a board has joined, you can delete `secrets.py`.

When it knows one network, it joins it straight away. When it knows more, it
scans first and tries the known networks it saw, strongest first, then the
known networks it didn't see, because a scan misses a weak network about
half the time. A scan holds the board for a few seconds, which is why one
network goes without it. Then it goes round once more. Each attempt waits up to
`timeout` seconds (20 by default), but a missing network ends it after about
six seconds and a wrong password after about fourteen.

An access point can turn a board away for a few minutes after the board
resets, because it still holds the board's old connection. ESP32 boards report
that as a wrong password. So when a password that has joined a network before
is refused, `connect()` doesn't give up or start setup mode yet: it waits 10
seconds, then 20, then 40, and tries every known network again each time, for
up to two minutes (`REFUSED_RETRY_S`). A password that has never worked is
still reported as wrong after the two rounds.

A board with a fixed address (`ifconfig()` set before the join) counts as
connected only once the station has a link, so it joins at boot and rejoins
after a drop.

`wifi.connect_from_secrets()` is deprecated. It calls `connect()` with
`setup=False` and `ntp=True`, and only exists for boards whose `boot.py` still
calls it. Use `connect()` in new code.

Remembered networks live here, with their passwords in plain text, as in
`secrets.py`:

| Where | Store |
|---|---|
| MicroPython on ESP32 | NVS namespace `wifi_manager`: survives a filesystem wipe, not `esptool erase_flash` |
| Other MicroPython ports | `/wifi_networks.json` (`CACHE_FILE`) |
| CircuitPython | `microcontroller.nvm` from `NVM_OFFSET`, writable while CIRCUITPY is mounted |

It keeps 16 at most.

## Join from a picker

`wifinet` puts the networks in range under endpointkit's `net` kind, so a
picker, such as appkit's, lists them and joins one when you tap it:

```python
import endpointkit
import wifinet

wifinet.register()
endpointkit.refresh("net")   # ask for a scan
endpointkit.poll()           # the scan runs here, for a second or two
for ep in endpointkit.endpoints("net"):
    print(ep.label, ep.state)
endpointkit.pair("wifi:Cafe", "espresso")
```

The network the board is on is `connected`, and registering chooses it when
nothing else is chosen. A network the board knows (from `secrets.py`,
`settings.toml`, or a join before) is `available`, and choosing it joins it.
A new secured network `needs pairing`: `pair()` with its password joins it,
or raises `ValueError("Wrong password for Cafe. Back on Home")`. Joining
leaves the network the board was on, so when the new one fails it goes back
there, and the message says whether it got back. A board you reach over
Wi-Fi, through WebREPL or a browser display, then stays in reach to show you
the error. A network it joins is remembered with the others, so `connect()`
joins it at the next boot.

A scan only runs when something asks for one, because it holds the board.
Between scans, each `endpointkit.poll()` notices within three seconds when
the link drops or the board moves to another network. A join waits up to 20
seconds (`JOIN_TIMEOUT_S`) for the network.

### Move traffic to Ethernet and back

On a board with an Ethernet port as well, such as the ESP32-P4-WIFI6-DEV-KIT,
`ethnet` adds the port as `eth:0`. Choosing it moves the board's traffic onto
Ethernet while Wi-Fi stays joined, and choosing the Wi-Fi network moves it
back:

```python
import endpointkit
import ethnet
import wifinet

wifinet.register()
ethnet.register()                       # board_peripherals.ethernet()
endpointkit.select("net", "eth:0")      # traffic leaves by Ethernet
endpointkit.select("net", "wifi:Home")  # and by Wi-Fi again
```

This needs firmware whose `network` interfaces take `ipconfig(default=True)`,
which OmniPython's ESP32 builds have; elsewhere choosing `eth:0` is refused
with a message that says so. The DNS server stays as it was set; one out on
the internet is reached by whichever link is chosen, and `network.ipconfig(dns=...)`
sets another.

## Reference

| Call | Does |
|---|---|
| `connect(*, setup=True, hostname=None, display_drv=None, timeout=20, wait=True, ntp=False, module="secrets")` | Joins a known network and returns its IPv4 address. With none in range, runs setup mode, or returns `None` when `setup=False`. |
| `run(*, hostname=None, display_drv=None, timeout=20)` | Starts setup mode now and returns the address of the network joined, or `None` after `cancel()`. |
| `cancel()` | Ends a waiting setup mode without a network. Call it from a timer or another app. |
| `networks()` | The remembered SSIDs. |
| `forget(ssid=None)` | Forgets one remembered network, or all of them. A network still in `secrets.py` comes back the next time it's joined. |
| `power_save()` | Whether the radio may sleep between beacons: the remembered choice, or `True` on a board with a battery fitted. |
| `set_power_save(on)` | Remembers power saving on (`True`), off (`False`) or back to the default (`None`), and applies it now. |

`display_drv` defaults to `board_config.display_drv` when there is one.
`hostname` is set before the join so DHCP and mDNS see it, and defaults to
[the board's name](board-name.md).
`ntp=True` sets the clock once a network is joined. `wait=False` starts
joining the first known network and returns `None` at once, for an app that
can't stall: poll `wifi.radio.connected`, or call it again after a drop (on
CircuitPython a join can't run in the background, so it waits). `module` names
the module that holds `WIFI_SSID` and `WIFI_PASSWORD` when it isn't `secrets`.

| Setting | Default | Meaning |
|---|---|---|
| `AP_NAME` | `None` | The setup access point's name; `None` is the board's name |
| `JOIN_TIMEOUT_S` | `20` | Seconds to wait for one network |
| `RESCAN_S` | `60` | Seconds between looks for a known network while `connect()`'s setup mode waits |
| `REFUSED_RETRY_S` | `120` | Seconds to keep trying when a network refuses a password that has joined it before; `0` gives up after two rounds |
| `NVM_OFFSET` | `0` | CircuitPython: where the record starts in `microcontroller.nvm` |
| `CACHE_FILE` | `"/wifi_networks.json"` | MicroPython ports without `esp32.NVS` |
