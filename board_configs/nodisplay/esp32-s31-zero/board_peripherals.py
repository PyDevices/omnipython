# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""Lazy constructors for the Waveshare ESP32-S31-Zero. PERIPHERALS = lazy roles only.

The Zero is an ESP32-S31 with 32 MB of flash and 16 MB of PSRAM, a USB-C
port, two buttons, an RGB LED, 18 edge pads and a 40-pin FPC connector.
Pins are from Waveshare's schematic. It has no display of its own, so there
is no ``board_config.py``: import this module.

    RGB LED           WS2812B on GPIO60, through a level shifter to 5 V
    BOOT button       GPIO61, low while pressed (a boot strap at reset)
    RESET button      the chip's enable line; no GPIO
    USB-C             USB Serial/JTAG (GPIO33, GPIO34): the REPL
    USB host pads     DM and DP on the back: the chip's USB 2.0 high-speed
                      OTG port, wired to nothing else
    edge pads         ``EDGE_PINS``: 5V, GND, 3V3, GPIO0-6, GPIO46-51 and
                      UART0's TX (GPIO58) and RX (GPIO59)
    FPC connector     ``LCD_PINS``: a 16-bit RGB panel, its touch I2C and a
                      microSD slot or resistive-touch SPI on a carrier board
    antenna           the chip antenna, or the u.FL socket by moving R8

There is no battery or charger: the board runs from USB-C or the 5V pad.

The edge pads' analog channels come in pairs, ADC1_2 on GPIO46 (N) and 47
(P), ADC1_3 on 48 and 49, ADC2_0 on 50 and 51. GPIO0-6 are the low-power
GPIOs (LP_GPIO on the schematic) and have no ADC.

Pins to leave alone: GPIO33 and GPIO34 are the USB-C data lines, so the
FPC connector's R4 and R5 take the REPL away when a panel drives them.
GPIO36 (flash voltage, pulled up), GPIO37 (JTAG source), GPIO60 and GPIO61
(boot mode) are boot straps, sampled at reset.

Checked on a board with nothing attached: every role in ``PERIPHERALS``
answers, Wi-Fi scans, BLE starts, the LED takes red, green and blue writes,
and the BOOT button reads released. Every GPIO in ``EDGE_PINS`` and
``LCD_PINS`` except 33 and 34 drives high and low and reads its own level
back, a UART opens on TX and RX, and an I2C bus opens on the touch pins.
Not checked, for want of hands or hardware: the LED's colour by eye, a
BOOT press, anything on the far side of a pad or the FPC connector, and
the USB host pads, which need firmware built with USB host support. The
ADC on GPIO46-51 answers, but reads each pair differentially.
"""

import sys

import boarddev

PERIPHERALS = frozenset({"pixels", "boot_button", "wlan", "ble"})

_LED = 60
_BOOT = 61

# The edge pads, by the label printed beside each one. Data, not a role:
# pass a number to machine.Pin.
EDGE_PINS = {
    "0": 0,
    "1": 1,
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "46": 46,
    "47": 47,
    "48": 48,
    "49": 49,
    "50": 50,
    "51": 51,
    "TX": 58,
    "RX": 59,
}

# The 40-pin FPC connector, by the signal the schematic gives each pin. The
# RGB data lines follow the panel's bits: B3-B7, G2-G7 and R3-R7 make RGB565.
# The microSD lines share pins with a resistive-touch controller's SPI
# (MISO on SD_D0, CLK on SD_CLK, MOSI on SD_CMD).
LCD_PINS = {
    "pclk": 40,
    "de": 43,
    "hsync": 44,
    "vsync": 45,
    "reset": 37,
    "power": 39,
    "backlight": 42,
    "b": (8, 9, 10, 11, 12),
    "g": (13, 14, 15, 16, 17, 18),
    "r": (19, 33, 34, 35, 36),
    "touch_sda": 52,
    "touch_scl": 53,
    "touch_int": 7,
    "touch_reset": 38,
    "sd_clk": 24,
    "sd_cmd": 25,
    "sd_data": (20, 21, 22, 23),
    "spare": 54,
}


def load_peripherals(ns):
    boarddev.bind_lazy(ns, sys.modules[__name__])


def pixels():
    """The RGB LED, one WS2812B, as a ``neopixel.NeoPixel``.

    Example:
        ``pixels[0] = (0, 32, 0); pixels.write()`` lights it green.
    """
    from machine import Pin
    from neopixel import NeoPixel

    return NeoPixel(Pin(_LED, Pin.OUT), 1)


def boot_button():
    """The BOOT button (GPIO61, ``value()`` 0 when pressed).

    Holding it through a reset starts the ROM bootloader, so a program reads
    it only after boot.
    """
    from machine import Pin

    return Pin(_BOOT, Pin.IN, Pin.PULL_UP)


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
