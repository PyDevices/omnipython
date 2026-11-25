# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""Lazy roles for the Adafruit ESP32 Feather V2. PERIPHERALS = lazy roles only.

The Feather V2 is a classic ESP32 (ESP32-PICO-MINI-02) with 8 MB of flash,
2 MB of PSRAM, a USB-C port through a CH9102, and a LiPo charger. Pins are
from Adafruit's pinout:

    NeoPixel          GPIO0, powered through GPIO2
    STEMMA QT / I2C   SDA GPIO22, SCL GPIO20, powered through GPIO2
    red LED           GPIO13, high = on
    button SW38       GPIO38, input only, pulled up on the board: low
                      when pressed
    battery monitor   GPIO35, through a divider of two 200K resistors
    reset button      the chip's enable line; no GPIO

GPIO2 (``NEOPIXEL_I2C_POWER``) switches the regulator for both the
NeoPixel and the STEMMA QT connector's 3V3, so ``pixels`` and ``i2c`` each
drive it high. GPIO12 is a boot strap that must be low at reset.

It has no display. Install the ``remote-display`` board config beside this
package for a screen in a web browser, or a display's own board config
when one is fitted: the 3.5" TFT FeatherWing has
``pitft_hx8357_featherwing_on_feather_esp32_v2``, which brings this
package too.

It has no audio output of its own, so there is no ``audio_out`` or ``bt``
receiver role: an I2S amplifier on its pins brings its own.

Checked on a board: a ``RemoteDisplay`` at 480x320 as its board config.
Not checked yet: each role below on the board, the button and LED by hand,
and the battery reading against a meter.
"""

import sys

import boarddev

PERIPHERALS = frozenset({"pixels", "led", "i2c", "battery", "wlan", "ble"})

_PIXEL = 0
_POWER = 2  # NEOPIXEL_I2C_POWER
_LED = 13
_BUTTON = 38
_BATTERY = 35
_SDA = 22
_SCL = 20


def load_peripherals(ns):
    boarddev.bind_lazy(ns, sys.modules[__name__])


def _power_on():
    from machine import Pin

    Pin(_POWER, Pin.OUT, value=1)


def pixels():
    """The NeoPixel, as a one-pixel ``neopixel.NeoPixel``."""
    from machine import Pin
    from neopixel import NeoPixel

    _power_on()
    return NeoPixel(Pin(_PIXEL, Pin.OUT), 1)


def led():
    """The red LED on GPIO13, a ``machine.Pin``: ``led(1)`` turns it on."""
    from machine import Pin

    return Pin(_LED, Pin.OUT, value=0)


def i2c():
    """The STEMMA QT connector's I2C, at 400 kHz, with its power switched on."""
    from machine import I2C, Pin

    _power_on()
    return I2C(0, sda=Pin(_SDA), scl=Pin(_SCL), freq=400_000)


def battery():
    """The LiPo's voltage, through the divider on GPIO35 (``voltage`` in volts)."""
    from battery_adc import BatteryADC

    return BatteryADC(_BATTERY, scale=2.0)


def keypad():
    """SW38 as the Enter key, for a board config to give the app as ``keypad``."""
    import keys
    from keypad_gpio import GPIOButtons
    from machine import Pin

    # GPIO38 has no internal pull-up; the board's own resistor holds it high.
    return GPIOButtons({"sw38": (Pin(_BUTTON, Pin.IN), keys.K_RETURN)})


def wlan():
    import network

    return network.WLAN(network.STA_IF)


def ble():
    # A bledev adapter (docs/guides/bluetooth-le.md). It also answers every
    # bluetooth.BLE method, so code written for the raw radio keeps working.
    # Firmware built with btclassic has no BLE: one Bluetooth host at a time.
    try:
        import bledev.mpble
    except ImportError:
        import bluetooth

        return bluetooth.BLE()
    return bledev.mpble.get()
