# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

# The seeed_gc9a01_on_xiao_esp32c5 board package: what mip.install("seeed_gc9a01_on_xiao_esp32c5") brings.
metadata(
    description="Seeed Studio Round Display for XIAO on a XIAO ESP32C5",
    version="0.1",
)

require("omnipython")
require("gc9a01")
require("chsc6x")
require("pcf8563")
require("battery_adc")
require("sdcard")  # micropython-lib's: frozen into OmniPython firmware, or mip.install("sdcard") first

module("board_config.py")
module("board_peripherals.py")
