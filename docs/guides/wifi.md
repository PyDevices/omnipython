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

Turn it off when your app talks back and forth, streams, or needs low latency:

```python
import wifi
wifi.radio.power_management = wifi.PowerManagement.NONE
```

On MicroPython without `wifi`, `network.WLAN(network.STA_IF).config(pm=network.WLAN.PM_NONE)`
does the same. It costs battery, so leave it on for a board that only
checks in now and then.

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

## Reference

| Call | Does |
|---|---|
| `connect(*, setup=True, hostname=None, display_drv=None, timeout=20, wait=True, ntp=False, module="secrets")` | Joins a known network and returns its IPv4 address. With none in range, runs setup mode, or returns `None` when `setup=False`. |
| `run(*, hostname=None, display_drv=None, timeout=20)` | Starts setup mode now and returns the address of the network joined, or `None` after `cancel()`. |
| `cancel()` | Ends a waiting setup mode without a network. Call it from a timer or another app. |
| `networks()` | The remembered SSIDs. |
| `forget(ssid=None)` | Forgets one remembered network, or all of them. A network still in `secrets.py` comes back the next time it's joined. |

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
| `NVM_OFFSET` | `0` | CircuitPython: where the record starts in `microcontroller.nvm` |
| `CACHE_FILE` | `"/wifi_networks.json"` | MicroPython ports without `esp32.NVS` |
