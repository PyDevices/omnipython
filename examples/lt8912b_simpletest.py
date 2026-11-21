# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Show colour bars on an HDMI monitor through an LT8912B bridge.

Sets the bridge up for 800x480 at 60 Hz, starts DSI video from the board
and draws eight colour bars into the framebuffer. `LT8912B` takes the same
arguments as Adafruit's CircuitPython driver, plus the lane count and rate,
which this ``mipidsi.Bus`` doesn't report. Success is the bars on the
monitor and ``HDMI cable connected: True``.

Needs: an ESP32-P4 board with its DSI connector cabled to an LT8912B board
(Adafruit's, for example), firmware whose ``mipidsi.Display`` takes
``output_color_depth`` and ``low_power_blanking``, a monitor on the HDMI
port, and the lt8912b driver (``omip.install("lt8912b")``).

Run it:

    mpremote run lt8912b_simpletest.py

Tested on: not yet run on a board.
"""

from machine import I2C, Pin
from mipidsi import Bus

from lt8912b import LT8912B

# Change these to match your setup.
I2C_SCL = 8  # the DSI connector's I2C on Waveshare's ESP32-P4 boards
I2C_SDA = 7
RESET_PIN = 47  # the GPIO wired to the bridge's RST pad, or None
NUM_LANES = 2

# 800x480 at 60 Hz. The board divides 240 MHz, so this runs at 40 MHz
# (240 / 6) and puts the extra pixels in the horizontal back porch.
WIDTH = 800
HEIGHT = 480
HSYNC_PULSE_WIDTH = 48
HSYNC_BACK_PORCH = 310
HSYNC_FRONT_PORCH = 112
VSYNC_PULSE_WIDTH = 3
VSYNC_BACK_PORCH = 29
VSYNC_FRONT_PORCH = 13
PIXEL_CLOCK_FREQUENCY = 40_000_000

# RGB888 takes 24 bits a pixel, spread across the lanes.
LANE_RATE = PIXEL_CLOCK_FREQUENCY * 24 // NUM_LANES

i2c = I2C(1, scl=Pin(I2C_SCL), sda=Pin(I2C_SDA), freq=100_000)
bus = Bus(minimum_frequency=LANE_RATE, num_lanes=NUM_LANES)

# The bridge configures itself, then starts DSI video.
bridge = LT8912B(
    bus,
    i2c,
    reset=None if RESET_PIN is None else Pin(RESET_PIN),
    width=WIDTH,
    height=HEIGHT,
    hsync_pulse_width=HSYNC_PULSE_WIDTH,
    hsync_back_porch=HSYNC_BACK_PORCH,
    hsync_front_porch=HSYNC_FRONT_PORCH,
    vsync_pulse_width=VSYNC_PULSE_WIDTH,
    vsync_back_porch=VSYNC_BACK_PORCH,
    vsync_front_porch=VSYNC_FRONT_PORCH,
    pixel_clock_frequency=PIXEL_CLOCK_FREQUENCY,
)

# Draw eight vertical colour bars, in RGB565: white, yellow, cyan, green,
# magenta, red, blue and black.
COLORS = (0xFFFF, 0xFFE0, 0x07FF, 0x07E0, 0xF81F, 0xF800, 0x001F, 0x0000)
bar_width = bridge.width // len(COLORS)
for index, color in enumerate(COLORS):
    left = index * bar_width
    right = bridge.width if index == len(COLORS) - 1 else left + bar_width
    bridge.fill_rect(left, 0, right - left, bridge.height, color)

print("Colour bars displayed. HDMI cable connected:", bridge.hot_plug_detected)
