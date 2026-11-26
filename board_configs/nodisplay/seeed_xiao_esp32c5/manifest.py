# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

# The seeed_xiao_esp32c5 board package: what mip.install("seeed_xiao_esp32c5") brings.
metadata(
    description="board_peripherals for the Seeed Studio XIAO ESP32C5, on MicroPython",
    version="0.1.0",
)

require("omnipython")
require("battery_adc")
require("keypad_gpio")

module("board_peripherals.py")
