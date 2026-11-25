# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""Lazy roles for the Pimoroni Pico Plus 2 W. PERIPHERALS = lazy roles only.

The Pico Plus 2 W (PIM726) is an RP2350B with 16 MB of flash, 8 MB of PSRAM
and an RM2 radio (CYW43439: Wi-Fi and Bluetooth), on a Pico-sized board with
a USB-C port. Pins are from Pimoroni's pinout and the firmware's pin table:

    user LED          on the radio's GPIO 0 (``Pin("LED")``), high = on
    BOOT switch       GP45, pulled up on the board: low when pressed. It
                      starts the bootloader only when held through a reset
    Qw/ST connector   I2C0, SDA GP4, SCL GP5
    radio             GP23, GP24, GP25 and GP29: leave them to it
    PSRAM             chip select GP47
    VSYS monitor      GP43 (ADC), through a divider
    RESET button      the chip's RUN line; no GPIO

It has no display and no audio. Install the ``remote-display`` board config
beside this package for a screen in a web browser.

Checked on a board with nothing attached: the LED takes writes, GP45 reads
high with the internal pull-down on (so the board's resistor holds it up),
I2C0 opens on GP4 and GP5 with nothing on it, Wi-Fi joins, BLE starts, and
the ``remote-display`` board config draws beside this package.
Not checked, for want of hands or hardware: the LED by eye, a press of the
switch, and anything on the Qw/ST connector.
"""

import sys

import boarddev

PERIPHERALS = frozenset({"led", "i2c", "wlan", "ble"})

_BUTTON = 45
_SDA = 4
_SCL = 5


def load_peripherals(ns):
    boarddev.bind_lazy(ns, sys.modules[__name__])


def led():
    """The user LED on the radio's GPIO 0, a ``machine.Pin``: ``led(1)`` turns it on."""
    from machine import Pin

    return Pin("LED", Pin.OUT, value=0)


def i2c():
    """The Qw/ST connector's I2C (I2C0 on GP4 and GP5), at 400 kHz."""
    from machine import I2C, Pin

    return I2C(0, sda=Pin(_SDA), scl=Pin(_SCL), freq=400_000)


def keypad():
    """The BOOT switch as the Enter key, for a board config to give the app as ``keypad``."""
    import keys
    from keypad_gpio import GPIOButtons
    from machine import Pin

    # The board's own resistor holds GP45 high.
    return GPIOButtons({"boot": (Pin(_BUTTON, Pin.IN), keys.K_RETURN)})


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
