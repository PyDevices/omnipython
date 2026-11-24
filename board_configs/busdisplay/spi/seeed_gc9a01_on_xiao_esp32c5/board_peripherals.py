# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""Lazy roles for the Seeed Round Display on a XIAO ESP32C5.

Nothing is constructed until it's asked for. None of these has run on a board
yet; the pins are from Seeed's pin tables:

    microSD           the display's slot, SPI on D8-D10, chip select D2 (GPIO25)
    PCF8563 clock     the board I2C, D4 SDA (GPIO23), D5 SCL (GPIO24)
    battery           the XIAO's own sense: GPIO6 through a 1:2 divider,
                      switched in by GPIO26
    user LED          GPIO27, yellow, low to light
    BOOT button       GPIO28, low when pressed
    antenna           Wi-Fi and Bluetooth through the XIAO's U.FL connector;
                      fit the antenna before using either

``sdcard`` is micropython-lib's ``sdcard.SDCard`` on the display's SPI bus. Mount
it yourself::

    os.mount(board_config.sdcard, "/sd")

``rtc`` is the PCF8563; ``rtc.datetime()`` reads and sets it like
``machine.RTC``. ``rtc.lost_power`` turns True when its supply dropped since it
was last set.
"""

import sys

import boarddev

PERIPHERALS = frozenset(
    {"sdcard", "rtc", "battery", "led", "boot_button", "i2c", "wlan", "ble"}
)

_D2 = 25  # microSD chip select
_BAT_ADC = 6  # battery divider tap
_BAT_EN = 26  # high connects the divider
_LED = 27
_BOOT = 28


def load_peripherals(ns):
    boarddev.bind_lazy(ns, sys.modules[__name__])


def sdcard():
    """microSD on the display's SPI bus, chip select D2."""
    import board_config as bc
    from machine import Pin

    from sdcard import SDCard

    # SDCard drives the SPI peripheral itself; the display's SPIBus re-applies
    # its own settings before every transfer, so the two take turns safely.
    return SDCard(bc.display_bus._spi, Pin(_D2, Pin.OUT, value=1))


def rtc():
    """PCF8563 on the board I2C."""
    import board_config as bc

    from pcf8563 import PCF8563

    return PCF8563(bc.i2c)


def battery():
    """LiPo voltage through the XIAO's 1:2 divider on GPIO6.

    GPIO26 connects the divider; it stays connected once this role is opened,
    which draws about 20 uA from the battery. Without a battery the reading is
    the charger's output.
    """
    from machine import Pin

    from battery_adc import BatteryADC

    Pin(_BAT_EN, Pin.OUT, value=1)
    return BatteryADC(_BAT_ADC, scale=2.0)


def led():
    """The yellow user LED as a ``machine.Signal``: ``on()`` lights it."""
    from machine import Pin, Signal

    return Signal(Pin(_LED, Pin.OUT, value=1), invert=True)


def boot_button():
    """The BOOT button (GPIO28, ``value()`` 0 when pressed)."""
    from machine import Pin

    return Pin(_BOOT, Pin.IN, Pin.PULL_UP)


def i2c():
    """The board I2C bus: touch, clock and the XIAO's D4 and D5."""
    import board_config as bc

    return bc.i2c


def wlan():
    import network

    return network.WLAN(network.STA_IF)


def ble():
    # A bledev adapter (docs/guides/bluetooth-le.md). It also answers every bluetooth.BLE
    # method, so code written for the raw radio keeps working. Without bledev
    # (or aioble) installed, the raw radio, as before.
    try:
        import bledev.mpble
    except ImportError:
        import bluetooth

        return bluetooth.BLE()
    return bledev.mpble.get()
