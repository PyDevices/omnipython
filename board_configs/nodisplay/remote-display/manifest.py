# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

# The remote-display board package: what mip.install("remote-display") brings.
# It has no board_peripherals: each board's own package brings that.
metadata(
    description="board_config for any board with no display: a RemoteDisplay in a web browser, on MicroPython",
    version="0.1.0",
)

require("omnipython")

module("board_config.py")
