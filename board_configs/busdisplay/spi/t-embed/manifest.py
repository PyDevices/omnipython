# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

# The t-embed board package: what mip.install("t-embed") brings.
metadata(
    description="LILYGO T-Embed ST7789 170x320 SPI + rotary (displayif native spibus)",
    version="0.5",
)

require("omnipython")
require("st7789")
require("dotstar")
require("es7210")
require("battery_adc")

module("board_config.py")
module("board_peripherals.py")
