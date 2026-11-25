# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

# The pitft_hx8357_featherwing_on_feather_esp32_v2 board package: what mip.install("pitft_hx8357_featherwing_on_feather_esp32_v2") brings.
metadata(
    description="Adafruit 3.5\" TFT FeatherWing (HX8357D) + STMPE610 on an Adafruit ESP32 Feather V2",
    version="0.2",
)

require("omnipython")
require("adafruit_feather_esp32_v2")
require("ili9341")
require("stmpe610")

module("board_config.py")
