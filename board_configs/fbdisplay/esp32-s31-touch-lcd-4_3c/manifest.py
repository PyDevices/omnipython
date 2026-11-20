# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

# The esp32-s31-touch-lcd-4_3c board package: what mip.install("esp32-s31-touch-lcd-4_3c") brings.
metadata(
    description="Waveshare ESP32-S31-Touch-LCD-4.3C — 800x480 RGB565 + GT911, ES8389 audio",
    version="0.1",
)

require("omnipython")
require("gt911")
require("es8389")
require("qmi8658")
require("pcf85063")
require("bq27220")
require("rs485")
require("canbus")

module("board_config.py")
module("board_peripherals.py")
