# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

metadata(
    description="CircuitPython's usb_hid on MicroPython, over usb-device-hid, for adafruit_hid.",
    version="0.2.0",
)

# The computer lists the device under the board's name, boarddev.name(), from
# pydevices, which a board with usb_hid already has.
require("usb-device-hid")
module("usb_hid.py")
