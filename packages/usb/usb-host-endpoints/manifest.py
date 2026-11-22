# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

metadata(
    description="What's plugged into this board's USB host port, as endpointkit endpoints: keyboards, mice, gamepads, MIDI, audio, cameras, drives, serial and network adapters, found as they come and go.",
    version="0.1.0",
)

require("usb-core")
require("endpointkit")
package("usb")
