# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""Waveshare ESP32-P4-WIFI6-DEV-KIT with an LT8912B DSI to HDMI board - MicroPython

Made for Adafruit's LT8912B board (product 6539), and untested on hardware.
The DEV-KIT's DSI connector has 15 pins and Adafruit's board has 22, so they
need a 15-to-22-pin DSI cable, such as the one Raspberry Pi 5 displays use.
The cable carries two data lanes, the clock, 3.3 V and the I2C pair; it has
no reset or hot-plug line. Everything that depends on wiring is in the block
below.

The DSI host divides a 240 MHz clock by a whole number, so 720p runs at
80 MHz with a wider front porch: 1778 pixels a line instead of 1650, the
same 45 kHz and 60 Hz a monitor expects. Each lane then runs at 960 Mbps.

The bridge needs RGB888 video with the lanes held in high speed through
blanking. When this firmware's ``mipidsi`` can't send that, this config
shows the bridge's own test pattern and raises NotImplementedError: the
pattern proves the bridge and the monitor, and the error says what's missing.
"""

from machine import I2C, Pin

from displaydev.fbdisplay import FBDisplay
from lt8912b import LT8912B, MODES, best_mode, check, fit, parse_edid

try:
    from mipidsi import Bus, Display
except ImportError as exc:
    raise NotImplementedError("MIPI DSI requires displayif mipidsi cmod (esp32p4 port)") from exc

# -- Wiring -------------------------------------------------------------------
# The DSI connector's I2C is GPIO 7 (SDA) and 8 (SCL), the bus the board's
# codec and 4-pin I2C header share; a KeDei DSI panel was driven over it.
I2C_SCL = 8
I2C_SDA = 7
LANES = 2
# Not on the cable. To use them, wire Adafruit's RST and HPD pads to free
# GPIOs of your choosing and put the numbers here. RST is pulled up on the
# board, so leaving it unwired is safe; HPD is low while a monitor is
# connected. None reads hot-plug from the bridge.
BRIDGE_RST = None
BRIDGE_HPD = None
# I2S for HDMI audio, to the board's BCK, LRC and DIN pads: your choice of
# free header pins. The board's codec holds I2S port 0 on GPIO 9 to 13, so
# use other pins and the other port. Used only when AUDIO is set.
I2S_SCK = None
I2S_WS = None
I2S_SD = None

# -- Video ------------------------------------------------------------------
# A name from lt8912b.MODES, or "edid" for the best mode the monitor offers
# that two lanes carry (needs the board's DDC switch on).
MODE = "1280x720p60"
HDMI = None  # None: DVI, or HDMI when AUDIO is set. True forces HDMI.
AUDIO = None  # experimental: lt8912b.Audio(48000, 16) with I2S on the pins above
# What mipidsi must do for this bridge: RGB888 on the wire (the framebuffer
# stays RGB565 and the P4 converts it), and no drop to low power between lines. If the picture won't hold, add "non_burst": True and
# "continuous_clock": True, which the bridge's datasheet asks for.
DSI_OPTIONS = {"color_depth": 16, "output_color_depth": 24, "low_power_blanking": False}

i2c = I2C(1, scl=Pin(I2C_SCL), sda=Pin(I2C_SDA), freq=100_000)
bridge = LT8912B(
    i2c,
    lanes=LANES,
    reset=None if BRIDGE_RST is None else Pin(BRIDGE_RST, Pin.OUT, value=1),
    hpd=None if BRIDGE_HPD is None else Pin(BRIDGE_HPD, Pin.IN),
)
bridge.detect()

if MODE == "edid":
    mode = best_mode(parse_edid(bridge.read_edid()), LANES)
else:
    mode = fit(MODES[MODE])
lane_rate = check(mode, LANES)

# The bridge is set up first; it locks to the video once the video runs.
bridge.start(mode, lane_rate=lane_rate, hdmi=HDMI, audio=AUDIO)

display_bus = Bus(frequency=lane_rate, num_lanes=LANES, ldo_chan=3, ldo_voltage_mv=2500)
try:
    fb = Display(display_bus, b"", **mode.dsi_timing(), **DSI_OPTIONS)
except (TypeError, ValueError) as exc:
    bridge.test_pattern()
    raise NotImplementedError(
        "this firmware's mipidsi can't send the LT8912B's video (%s): it needs %s. "
        "The monitor shows the bridge's test pattern instead" % (exc, DSI_OPTIONS)
    ) from exc
bridge.sync()

display_drv = FBDisplay(fb)
