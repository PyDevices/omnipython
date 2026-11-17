# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Show an LT8912B bridge's own colour bars, with no DSI video.

Finds the bridge on I2C, checks a monitor is connected, sets the bridge up
for 720p and turns on its built-in test pattern. The bridge makes the
picture itself, so this needs no DSI video: it proves the wiring, the bridge
and the monitor. Success is colour bars on the monitor; the status line
then shows ``"hpd": True``.

Needs: an ESP32-P4 board with its DSI connector cabled to an LT8912B board
(Adafruit's, for example), a monitor on the HDMI port, and the lt8912b
driver (``omip.install("lt8912b")``). Any firmware with ``machine.I2C``
will do.

Run it:

    mpremote run lt8912b_test_pattern.py

Tested on: not yet run on a board.
"""

from machine import I2C, Pin

from lt8912b import MODES, Bridge, fit

# Change these to match your setup.
I2C_SCL = 8  # the DSI connector's I2C on Waveshare's ESP32-P4 boards
I2C_SDA = 7
MODE = "1280x720p60"

# Find the bridge: three I2C addresses and the chip ID 12 B2.
i2c = I2C(1, scl=Pin(I2C_SCL), sda=Pin(I2C_SDA), freq=100_000)
bridge = Bridge(i2c)
print("chip ID:", bridge.detect().hex())
print("monitor connected:", bridge.hot_plug_detected)

# Set the bridge up for the mode, then let it make its own picture.
mode = fit(MODES[MODE])
bridge.start(mode)
bridge.test_pattern()
print("showing", mode)

# Read back what the bridge measures.
print("status:", bridge.status())
