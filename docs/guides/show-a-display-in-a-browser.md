# Show a display in a browser

A board can show its screen in any browser on its network, and take clicks
and keys from there. This works two ways:

- A board with no screen gets one. `RemoteDisplay` is a display with no panel
  behind it, and every app runs on it unchanged, LVGL included.
- A board with a screen shows it in the browser too. `mirror` attaches to a
  display that keeps the whole frame in memory: the `FBDisplay` panels (MIPI
  DSI, RGB, DVI). What the browser shows is what the panel shows.

One browser at a time. A second one takes over, and the first page says so.

## A board with no screen

In the board's `board_config.py`:

```python
from displaydev.remotedisplay import RemoteDisplay

display_drv = RemoteDisplay(800, 480)
host_read = display_drv.get_events
```

When the board starts, it prints where to look:

```text
Display at http://192.168.1.150/
```

Open that address in a browser. The clicks, the wheel and the keys you use on
the page reach the app as the board's own input. The board needs Wi-Fi (or
another network) up before the display opens, and the frame takes
width x height x 2 bytes of RAM: 750 KB at 800x480.

## A board that has a screen

After the board makes its display, add:

```python
from displaydev.remotedisplay import mirror

host_read = mirror(display_drv).read
```

The browser's clicks and keys reach the app beside the panel's own touch.

## Watch it in VLC

Open `http://<the board's address>/stream.mjpg` in VLC (Media > Open Network
Stream), or in any player that takes Motion JPEG. The player only watches, and
counts as the one viewer.

The stream needs `jpegio` in the firmware. An ESP32-P4 encodes on its JPEG
engine, 17 ms for an 800x480 frame, so the player sees every change. Other
boards encode in software, about half a second a frame on an ESP32-S3. The
server leaves the app four times that between frames, so a player sees a new
picture every two seconds or so.

To cast to a TV instead, see [castdisplay](cast-to-a-tv.md).

## How fast it is

The server reads the frame from memory when it sends, not when the app draws.
A slow network or a closed browser never slows the app or the panel: updates
merge until the network takes them. Only the tiles that changed are sent, as
runs of equal pixels where that is smaller.

Measured with an 800x480 LVGL app and a 400x400 spinner turning:

| | ESP32-S3 RGB panel, mirrored |
|---|---|
| The panel, no browser | 24 frames a second |
| The panel, with a browser | 15 frames a second |
| The browser | 9.6 updates a second, 36 KB/s |

A clock face that changes once a second sends about one 6 to 13 KB update a
second. The whole frame is also compared every two seconds, so drawing the
display wasn't told about (a program writing `framebuffers()` directly) still
reaches the browser; `sweep_ms` sets how often.

## Options

`RemoteDisplay(width, height, port=80, period_ms=40, sweep_ms=2000)` and
`mirror(display, port=80, period_ms=40, sweep_ms=2000)` take the same server
options:

| Option | What it does |
|---|---|
| `port` | The TCP port for the page and the stream. |
| `period_ms` | How often the server looks for changes and sends them. |
| `sweep_ms` | How often it compares the whole frame. |

The server is `display_drv.server` (or what `mirror` returns). Its `url` says
where to look, `connected` says whether a viewer is attached, and `quality`
(70) sets the JPEG quality for a video player.

Anyone on the network can open the page and use the app. Run it on a network
you trust.
