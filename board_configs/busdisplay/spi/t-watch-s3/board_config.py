# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""LILYGO T-Watch S3: ST7789 240x240 SPI, FT6336 touch, AXP2101 power (MicroPython)

The display, its backlight and the touch controller are all powered by the
AXP2101, so the PMU comes up first: ALDO3 feeds the panel and touch, ALDO2
the backlight. Pins from LILYGO's TTGO_TWatch_Library (branch t-watch-s3,
src/utilities.h), matching CircuitPython's lilygo_twatch_s3 board:

    display  SCK 18, MOSI 13, CS 12, DC 38, backlight 45, no reset line
    touch    FT6336 on its own I2C, SDA 39, SCL 40, INT 16, no reset line
    I2C      SDA 10, SCL 11 (PMU, accelerometer, RTC, haptic driver)
    buttons  the crown is the AXP2101's power key; BOOT (GPIO0) is inside

The crown also powers the watch: a press of about 2 s turns it on and about
6 s turns it off, in the PMU itself, whatever the program is doing.

``display_drv.sleep_mode(True)`` puts the whole screen to sleep: the panel's
controller, its backlight's supply (ALDO2) and the touch controller, which
then scans slowly and still wakes on a touch. ``sleep_mode(False)`` brings
all three back with the picture the panel kept.

The watch's clock chip (the ``rtc`` role) keeps time while the watch is off,
so the system clock starts from it here, when it has a time it can trust.
"""

import time

import keys
from ft6x36 import FT6x36
from keypad_gpio import GPIOButtons
from machine import I2C, Pin
from spibus import SPIBus
from st7789 import ST7789

import board_peripherals

# Main I2C: the same bus object board_peripherals hands its drivers.
i2c = board_peripherals._i2c_bus()
_pmu = board_peripherals.pmu()
_pmu.set_rail("aldo3", 3300)  # display and touch
_pmu.set_rail("aldo2", 3300)  # backlight supply
time.sleep_ms(20)

display_bus = SPIBus(
    # ESP32-S3: SPI(2) + explicit pins (SPI(2) defaults hit Octal PSRAM pads).
    id=2,
    baudrate=40_000_000,
    sck=18,
    mosi=13,
    miso=-1,
    command=38,
    chip_select=12,
    reset=-1,
    swap_bytes=True,  # the bus swaps each colour as it copies it
)

display_drv = ST7789(
    display_bus,
    width=240,
    height=240,
    colstart=0,
    rowstart=80,
    # MADCTL MX|MY|BGR (0xC8), crown on the right and upright. The glass is
    # rows 80-319 of the controller's 320 with MY set, hence rowstart=80.
    # CircuitPython's board.c gets the same picture as MADCTL 0x68 plus a
    # 90-degree software rotation.
    rotation=180,
    mirrored=True,
    color_depth=16,
    bgr=True,
    reverse_bytes_in_word=False,
    invert=True,
    brightness=1.0,
    backlight_pin=45,
    backlight_on_high=True,
)

# FT6336 on its own bus (port 1). Its reset is not wired, so it must never
# hibernate (that would end touch until the next power cycle); its monitor
# mode, touch.power_mode = ft6x36.POWER_MONITOR, saves power and still wakes
# on a touch. The panel sleeps with display_drv.sleep_mode(True) (SLPIN),
# keeping its picture for sleep_mode(False).
touch_i2c = I2C(1, sda=Pin(39), scl=Pin(40), freq=400_000)
touch = FT6x36(touch_i2c)
# The FT6336 reports points already in the frame the panel shows at
# rotation=180, so that rotation needs no mapping; the others follow from it.
touch_rotation_table = (0b110, 0b011, 0b000, 0b101)
touch_read = touch.read_points

_panel_sleep = display_drv.sleep_mode
_woke_at = time.ticks_ms()


def _sleep_mode(value):
    """The panel, its backlight's supply and the touch controller, asleep
    (True) or awake (False) together."""
    global _woke_at
    if value:
        # The controller wants 120 ms after SLPOUT before SLPIN.
        wait = 120 - time.ticks_diff(time.ticks_ms(), _woke_at)
        if wait > 0:
            time.sleep_ms(wait)
        _panel_sleep(True)
        _pmu.set_rail("aldo2", enable=False)
        mode = 1  # ft6x36.POWER_MONITOR: never hibernate, its reset isn't wired
    else:
        _pmu.set_rail("aldo2", 3300)
        _panel_sleep(False)
        time.sleep_ms(5)
        _woke_at = time.ticks_ms()
        mode = 0  # ft6x36.POWER_ACTIVE, for a quick first touch
    try:
        touch.power_mode = mode
    except OSError:
        pass


display_drv.sleep_mode = _sleep_mode

# The crown is the PMU's power key, read from its latched press and release
# events. (The BOOT button inside the case is the boot_button role.)
from axp2101 import PowerKey

keypad = GPIOButtons({"crown": (PowerKey(_pmu), keys.K_RETURN)})
keypad_read = keypad.read

from board_peripherals import PERIPHERALS, load_peripherals

load_peripherals(globals())


def _clock_from_chip():
    # The system clock from the clock chip, unless it stopped or lost its
    # backup supply since it was last set. Nothing to do where it fails.
    try:
        chip = board_peripherals.rtc()
        if not chip.lost_power:
            from machine import RTC

            RTC().datetime(chip.datetime())
    except Exception as e:
        print("t-watch-s3: the clock chip didn't set the clock: %r" % (e,))


_clock_from_chip()
