# Show a P4 board on an HDMI monitor with an LT8912B

The Lontium LT8912B turns MIPI DSI video into HDMI or DVI. Adafruit sells it
on a small board (product 6539) with a 22-pin DSI connector, an HDMI port and
pads for reset, hot-plug and I2S audio; Olimex and M5Stack make others. The
`lt8912b` driver sets the bridge up over I2C; the video itself comes from
`mipidsi` on an ESP32-P4.

The driver hasn't run on hardware yet. Its register writes match those of
Espressif's and Adafruit's drivers for the chip, checked on a fake I2C bus,
and [What isn't proven](#what-isnt-proven) lists the rest.

## Wire it

On Waveshare's ESP32-P4-WIFI6, a 22-pin DSI cable runs straight from the
board's DSI connector to Adafruit's. It carries two data lanes, the clock,
3.3 V and I2C on GPIO 7 (SDA) and 8 (SCL). The ESP32-P4-WIFI6-DEV-KIT's
connector has 15 pins, so it needs a 15-to-22-pin cable, the kind Raspberry
Pi 5 displays use.

The cable has no reset or hot-plug line. Both are optional: the board pulls
reset up, and the driver reads hot-plug from the bridge. To wire them
anyway, run the board's RST and HPD pads to free GPIOs and name them in the
board config.

Adafruit's board has a DDC switch that joins the monitor's DDC lines to the
cable's I2C. Leave it off unless you want the monitor's EDID: with it on, a
monitor that answers at 0x48 to 0x4A takes the bridge's writes.

## See a picture first

The bridge can draw colour bars by itself, with no DSI video, which proves
the wiring, the bridge and the monitor before anything else:

```python
import omip
omip.install("lt8912b")
```

then run [`lt8912b_simpletest.py`](https://github.com/PyDevices/omnipython/blob/main/examples/lt8912b_simpletest.py).
An I2C scan should show 0x48, 0x49 and 0x4A, and the chip ID reads `12b2`.
[Bring up a board](bring-up-a-board.md) shows how to put `omip` on the board.

## Install the board config

```python
import omip
omip.install("github:PyDevices/omnipython/board_configs/fbdisplay/esp32-p4-wifi6_lt8912b-hdmi")
```

or `esp32-p4-wifi6-dev-kit_lt8912b-hdmi` for the DEV-KIT. Pins, mode and
audio are constants at the top of its `board_config.py`.

The bridge takes RGB888 video and needs the DSI lanes kept in high speed
through blanking. The board config asks `mipidsi` for both
(`output_color_depth=24` and `low_power_blanking=False`); the framebuffer stays
RGB565 and the P4 converts it on the way out. On firmware whose `mipidsi` lacks
those options, the board config shows the test pattern and raises
`NotImplementedError` saying what's missing.

## Pick a mode

The ESP32-P4 makes its pixel clock by dividing 240 MHz by a whole number, so
most standard clocks aren't available. `fit()` takes the next clock up and
widens the horizontal front porch so the line and frame rates stay what the
monitor expects. Each of the P4's two lanes carries at most 1.5 Gbps, and
RGB888 needs 24 bits a pixel:

| Mode | Pixel clock sent | Line, pixels | Refresh | Per lane, two lanes |
|---|---|---|---|---|
| `640x480p60` | 26.67 MHz (240 / 9) | 847 | 59.97 Hz | 320 Mbps |
| `800x600p60` | 40 MHz (exact) | 1056 | 60.32 Hz | 480 Mbps |
| `1024x768p60` | 80 MHz (240 / 3) | 1654 | 60.01 Hz | 960 Mbps |
| `1280x720p60` | 80 MHz (240 / 3) | 1778 | 59.99 Hz | 960 Mbps |
| `1920x1080p30` | 80 MHz (240 / 3) | 2370 | 30.00 Hz | 960 Mbps |
| `1920x1080p60` | refused | | | 1782 Mbps needed |

`check()` refuses a mode the lanes can't carry and says by how much.
A padded mode announces video code 0, meaning no standard code, because its
timing isn't the CEA one. If a monitor or TV handles it badly, set `VIC` in
the board config to the standard code (4 for 720p60), or pass `vic=` to
`fit()`.

Set `MODE = "edid"` in the board config to pick the largest mode the
monitor lists that fits; that needs the DDC switch on. Your own timing is a
`Mode(...)`, and goes through `fit()` and `check()` like the rest.

A fitted mode isn't a CEA mode any more, so the bridge announces no video
code. Monitors take it on the line and frame rates; some TVs want the code.

## HDMI, DVI and audio

The bridge sends DVI unless you ask for HDMI (`hdmi=True`) or audio. Audio
comes in as I2S, with no master clock, on the board's BCK, LRC and DIN pads,
and goes out in the HDMI stream. It's experimental: no public document
covers this chip's audio registers, so `Audio(rate, bits, recipe)` offers
three register sets, `"a"` first. The driver's `Audio` docstring says where
each came from.

## What isn't proven

Nothing here has run on a board yet. In particular:

- that the bridge locks to the ESP32-P4's RGB888 video at 80 MHz with the
  widened porches;
- whether burst mode, which Espressif and Adafruit use, holds, or the
  datasheet's non-burst mode is needed (`non_burst=True`);
- the DEV-KIT cable's orientation;
- every audio recipe;
- `MODE = "edid"` with a monitor and the bridge on one bus.
