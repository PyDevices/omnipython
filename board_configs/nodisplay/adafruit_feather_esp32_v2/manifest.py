# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

# The adafruit_feather_esp32_v2 board package: what mip.install("adafruit_feather_esp32_v2") brings.
metadata(
    description="board_peripherals for the Adafruit ESP32 Feather V2, on MicroPython",
    version="0.1.0",
)

require("omnipython")
require("battery_adc")
require("keypad_gpio")

module("board_peripherals.py")
