# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

# The esp32-p4-wifi6-dev-kit_lt8912b-hdmi board package: what mip.install("esp32-p4-wifi6-dev-kit_lt8912b-hdmi") brings.
metadata(
    description="Waveshare ESP32-P4-WIFI6-DEV-KIT with an LT8912B DSI to HDMI board, 720p60 - MicroPython",
    version="0.1.0",
)

require("omnipython")
require("esp32-p4-wifi6-dev-kit")
require("lt8912b")

module("board_config.py")
