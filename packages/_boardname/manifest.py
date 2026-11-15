# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

# The board's name with one plain error on older firmware, for the packages
# that name something after the board: usb-hid, midiports, castdisplay and
# hmilink require() it. It isn't for importing on its own.
metadata(
    description="The board's name, boarddev.name(), with one error for firmware older than it.",
    version="0.1.0",
    license="MIT",
)

module("_boardname.py")
