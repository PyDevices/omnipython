# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""Seeed Studio Round Display for XIAO on a XIAO ESP32C5.

For OmniPython's or stock MicroPython's ``SEEED_XIAO_ESP32C5`` build. The
GC9A01 240x240 panel is on the XIAO's SPI pins (D8 SCK, D10 MOSI, D9 MISO)
with chip select on D1, data/command on D3 and the backlight on D6. The
CHSC6X touch controller is on I2C (D4 SDA, D5 SCL) with its interrupt on D7,
sharing the bus with the display's PCF8563 clock.

The display's KE switch connects D6 to the backlight and A0 to the display's
battery divider. Leave it on, or the backlight stays dark.

Touch reaches x from about 30 to 225 only: the display's CHSC6X can't see
the outer 30 px or so at each side, and ``round_display_points`` corrects
its x scale.

``board_peripherals`` adds the microSD slot (``sdcard``), the clock (``rtc``),
the battery (``battery``), the XIAO's LED (``led``) and BOOT button
(``boot_button``), the I2C bus (``i2c``), Wi-Fi (``wlan``) and Bluetooth
(``ble``).

This config hasn't run on a board yet: the pins are Seeed's, from the XIAO
ESP32C5's and the Round Display's pin tables, and the panel settings are the
ones the same display uses on a XIAO nRF52840 and a QT Py ESP32-S3.
"""

from chsc6x import CHSC6X, round_display_points
from gc9a01 import GC9A01
from machine import I2C
from spibus import SPIBus

# XIAO header pin to ESP32-C5 GPIO.
_D1 = 0  # display chip select
_D3 = 7  # display data/command
_D4 = 23  # I2C SDA
_D5 = 24  # I2C SCL
_D6 = 11  # backlight
_D7 = 12  # touch interrupt
_SCK = 8  # D8
_MISO = 9  # D9
_MOSI = 10  # D10

# SPI(1) is the C5's one general-purpose SPI host. These pins reach it through
# the GPIO matrix, which carries a write-only clock of 40 MHz.
display_bus = SPIBus(
    id=1,
    baudrate=40_000_000,
    sck=_SCK,
    mosi=_MOSI,
    miso=_MISO,
    command=_D3,
    chip_select=_D1,
    swap_bytes=True,  # the bus swaps each colour as it copies it
)

display_drv = GC9A01(
    display_bus,
    width=240,
    height=240,
    colstart=0,
    rowstart=0,
    rotation=0,
    # The default table's rotation 0 sets MADCTL MX, which draws this panel
    # mirrored left to right against its touch controller; mirrored=True
    # clears it, so display and touch agree with no touch rotation.
    mirrored=True,
    color_depth=16,
    bgr=True,
    reverse_bytes_in_word=False,
    invert=True,
    brightness=1.0,
    backlight_pin=_D6,
    backlight_on_high=True,
)

i2c = I2C(0, scl=_D5, sda=_D4, freq=400_000)
touch = CHSC6X(i2c, irq_pin=_D7)
touch_rotation_table = (0, 5, 6, 3)


def touch_read():
    return round_display_points(touch.read_points())


from board_peripherals import PERIPHERALS, load_peripherals

load_peripherals(globals())
