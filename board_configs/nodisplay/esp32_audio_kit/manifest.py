# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

# The esp32_audio_kit board package: what mip.install("esp32_audio_kit") brings.
metadata(
    description="board_peripherals for the Ai-Thinker ESP32-Audio-Kit V2.2 (ESP32-A1S, ES8388), on MicroPython",
    version="0.1.0",
)

require("omnipython")
require("es8388")
require("keypad_gpio")

module("board_peripherals.py")
