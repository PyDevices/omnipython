# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

# The esp32-p4-wifi6_lt8912b-hdmi board package: what mip.install("esp32-p4-wifi6_lt8912b-hdmi") brings.
metadata(
    description="Waveshare ESP32-P4-WIFI6 with an LT8912B DSI to HDMI board, 720p60 - MicroPython",
    version="0.1.0",
)

require("omnipython")
require("lt8912b")

module("board_config.py")
