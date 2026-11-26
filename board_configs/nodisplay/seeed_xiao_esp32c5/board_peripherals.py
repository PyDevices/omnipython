# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""Lazy roles for the Seeed Studio XIAO ESP32C5. PERIPHERALS = lazy roles only.

The XIAO ESP32C5 is an ESP32-C5 (dual-band Wi-Fi 6, Bluetooth LE) with 8 MB
of flash and 8 MB of PSRAM, a USB-C port on the chip's own USB Serial/JTAG,
and a LiPo charger. Pins are from Seeed's pin table and the firmware's:

    user LED          GPIO27, yellow, low to light
    BOOT button       GPIO28, low when pressed
    battery sense     GPIO6, through a 1:2 divider that GPIO26 connects
    I2C               D4 SDA (GPIO23), D5 SCL (GPIO24)
    antenna           Wi-Fi and Bluetooth through the U.FL connector; fit
                      the antenna before using either

It has no display and no audio. Install the ``remote-display`` board config
beside this package for a screen in a web browser, or a display's own board
config when one is fitted.

Checked on a board with nothing attached: every role opens, BOOT reads high
when not pressed, the battery role reads the charger's 4.0 V with no battery
fitted, Wi-Fi joins on 2.4 GHz and on 5 GHz, BLE starts, and the
``remote-display`` board config draws beside this package. Not checked, for
want of hands or hardware: the LED by eye, a press of BOOT, a real battery,
and anything on the I2C pins.
"""

import sys

import boarddev

PERIPHERALS = frozenset({"led", "boot_button", "battery", "i2c", "wlan", "ble"})

_LED = 27
_BOOT = 28
_BAT_ADC = 6  # battery divider tap
_BAT_EN = 26  # high connects the divider
_SDA = 23  # D4
_SCL = 24  # D5


def load_peripherals(ns):
    boarddev.bind_lazy(ns, sys.modules[__name__])


def led():
    """The yellow user LED as a ``machine.Signal``: ``on()`` lights it."""
    from machine import Pin, Signal

    return Signal(Pin(_LED, Pin.OUT, value=1), invert=True)


def boot_button():
    """The BOOT button (GPIO28, ``value()`` 0 when pressed)."""
    from machine import Pin

    return Pin(_BOOT, Pin.IN, Pin.PULL_UP)


def keypad():
    """The BOOT button as the Enter key, for a board config to give the app as ``keypad``."""
    import keys
    from keypad_gpio import GPIOButtons
    from machine import Pin

    return GPIOButtons({"boot": (Pin(_BOOT, Pin.IN, Pin.PULL_UP), keys.K_RETURN)})


def battery():
    """The LiPo's voltage through the 1:2 divider on GPIO6 (``voltage`` in volts).

    GPIO26 connects the divider; it stays connected once this role is opened,
    which draws about 20 uA from the battery. Without a battery the reading is
    the charger's output.
    """
    from battery_adc import BatteryADC
    from machine import Pin

    Pin(_BAT_EN, Pin.OUT, value=1)
    return BatteryADC(_BAT_ADC, scale=2.0)


def i2c():
    """The I2C bus on D4 and D5, at 400 kHz."""
    from machine import I2C, Pin

    return I2C(0, sda=Pin(_SDA), scl=Pin(_SCL), freq=400_000)


def wlan():
    import network

    return network.WLAN(network.STA_IF)


def ble():
    # A bledev adapter (docs/guides/bluetooth-le.md). It also answers every
    # bluetooth.BLE method, so code written for the raw radio keeps working.
    # Without bledev (or aioble) installed, the raw radio.
    try:
        import bledev.mpble
    except ImportError:
        import bluetooth

        return bluetooth.BLE()
    return bledev.mpble.get()
