# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""Waveshare ESP32-S31-Touch-LCD-4.3C: 800x480 RGB565 panel and a GT911.

Pins from Waveshare's schematic. The panel's data, clock and sync lines go
straight to the ESP32-S31. GPIO47 drives the backlight converter's feedback
pin, so low is full brightness and high dims it nearly off. The touch
controller's reset and interrupt are GPIO46 and GPIO2, on the board's I2C
bus (SDA 0, SCL 1). The panel's own reset line is not connected to the chip.
The rest of the board is in board_peripherals.
"""

from gt911 import GT911
from machine import I2C, Pin

from displaydev.fbdisplay import FBDisplay

try:
    import dotclockframebuffer
except ImportError as exc:
    raise NotImplementedError(
        "Parallel RGB scanout requires dotclockframebuffer.DotClockFramebuffer (esp32 port)"
    ) from exc

_TP_RST = 46
_TP_INT = 2
_LCD_BL = 47

i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=400_000)

# Low is full brightness: GPIO47 feeds the converter's feedback, not an enable.
backlight = Pin(_LCD_BL, Pin.OUT, value=0)

tft_pins = {
    "de": 43,
    "vsync": 45,
    "hsync": 44,
    "dclk": 40,
    # RGB565 wire order B0..B4, G0..G5, R0..R4 (the panel's B3-B7, G2-G7, R3-R7)
    "blue": (8, 9, 10, 11, 12),
    "green": (13, 14, 15, 16, 17, 18),
    "red": (19, 33, 34, 35, 36),
}

# The ESP32-S3-Touch-LCD-4.3's panel timings, at its 14 MHz pixel clock: a
# slower clock leaves PSRAM bandwidth for Wi-Fi beside the scanout.
tft_timings = {
    "frequency": 14_000_000,
    "width": 800,
    "height": 480,
    "hsync_pulse_width": 4,
    "hsync_front_porch": 8,
    "hsync_back_porch": 8,
    "vsync_pulse_width": 4,
    "vsync_front_porch": 8,
    "vsync_back_porch": 8,
    "hsync_idle_low": False,
    "vsync_idle_low": False,
    "de_idle_high": False,
    "pclk_active_high": False,
    "pclk_idle_high": False,
}

# Two bounce buffers of this many rows each, refilled from the PSRAM frame
# buffer while the panel scans, out of internal DMA RAM.
BOUNCE_ROWS = 10

try:
    fb = dotclockframebuffer.DotClockFramebuffer(
        **tft_pins, **tft_timings, bounce_rows=BOUNCE_ROWS
    )
except TypeError:
    fb = dotclockframebuffer.DotClockFramebuffer(**tft_pins, **tft_timings)
display_drv = FBDisplay(fb)

# GT911: holding INT low through reset selects address 0x5D.
touch = GT911(
    i2c,
    reset_pin=Pin(_TP_RST, Pin.OUT, value=1),
    irq_pin=_TP_INT,
    address=0x5D,
    width=800,
    height=480,
    touch_points=5,
    reverse_axis=False,
)

touch_read = touch.read_points
touch_rotation_table = (0, 0, 0, 0)

from board_peripherals import PERIPHERALS, load_peripherals

load_peripherals(globals())
