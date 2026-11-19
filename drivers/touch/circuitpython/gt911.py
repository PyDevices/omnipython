# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Read a GT911 capacitive touch controller on CircuitPython.

The MicroPython driver is ``drivers/touch/gt911.py``; this one takes a
``busio.I2C`` and, optionally, the reset line. It polls the point registers,
so it needs no interrupt pin.

The GT911 picks its address (0x5D or 0x14) from its interrupt line at reset.
When the board doesn't drive that line, either can come up, so the driver
uses ``i2c_address`` if it answers and the other one if not.

Example:
    ::

        touch = GT911(busio.I2C(board.IO8, board.IO7), rst_pin=board.IO23)
        touch.read_points()   # () when up, else ((x, y, size, id), ...)
"""

import time

import digitalio
from micropython import const

_ADDRESSES = (0x5D, 0x14)
_PRODUCT_ID = const(0x8140)
_STATUS = const(0x814E)
_POINTS = const(0x814F)
_MAX_POINTS = const(5)


class GT911:
    """A GT911 on an I2C bus.

    Args:
        i2c: the ``busio.I2C`` the controller is on.
        i2c_address: the address to try first, 0x5D or 0x14.
        rst_pin: the reset line, as a ``digitalio.DigitalInOut`` or a
            ``board`` pin, or None to leave the controller as it is.

    Raises:
        RuntimeError: the controller answers at neither address.
    """

    def __init__(self, i2c, i2c_address=0x5D, rst_pin=None):
        self._i2c = i2c
        self._reg = bytearray(2)
        self._one = bytearray(1)
        self._buf = bytearray(8 * _MAX_POINTS)
        self._rst = None
        if rst_pin is not None:
            if isinstance(rst_pin, digitalio.DigitalInOut):
                self._rst = rst_pin
            else:
                self._rst = digitalio.DigitalInOut(rst_pin)
            self._rst.switch_to_output(value=True)
            self.reset()
        found = self._scan()
        order = (i2c_address,) + tuple(a for a in _ADDRESSES if a != i2c_address)
        for address in order:
            if address in found:
                self.address = address
                break
        else:
            raise RuntimeError("GT911 not found at 0x%02X or 0x%02X" % _ADDRESSES)

    def reset(self):
        """Pulse the reset line, then wait for the controller to start."""
        if self._rst is None:
            return
        self._rst.value = False
        time.sleep(0.01)
        self._rst.value = True
        time.sleep(0.1)

    def _scan(self):
        while not self._i2c.try_lock():
            pass
        try:
            return self._i2c.scan()
        finally:
            self._i2c.unlock()

    def _read(self, reg, buf):
        self._reg[0] = reg >> 8
        self._reg[1] = reg & 0xFF
        self._i2c.writeto_then_readfrom(self.address, self._reg, buf)

    def product_id(self):
        """Read the controller's product id.

        Returns:
            The id as a string, ``"911"`` on a GT911.
        """
        buf = bytearray(4)
        while not self._i2c.try_lock():
            pass
        try:
            self._read(_PRODUCT_ID, buf)
        finally:
            self._i2c.unlock()
        return bytes(b for b in buf if b).decode()

    def read_points(self):
        """Read the contacts.

        The count is only trusted once the controller sets its buffer-ready
        bit, and the bit is cleared after every read, so a stale count never
        repeats an old point.

        Returns:
            ``((x, y, size, id), ...)``, or ``()`` when nothing touches.
        """
        while not self._i2c.try_lock():
            pass
        try:
            self._read(_STATUS, self._one)
            status = self._one[0]
            if not status & 0x80:
                return ()
            n = status & 0x0F
            points = ()
            if 0 < n <= _MAX_POINTS:
                view = memoryview(self._buf)[: 8 * n]
                self._read(_POINTS, view)
                b = self._buf
                points = tuple(
                    (b[i + 1] | b[i + 2] << 8, b[i + 3] | b[i + 4] << 8, b[i + 5] | b[i + 6] << 8, b[i])
                    for i in range(0, 8 * n, 8)
                )
            self._i2c.writeto(self.address, bytes((_STATUS >> 8, _STATUS & 0xFF, 0)))
            return points
        finally:
            self._i2c.unlock()

    @property
    def touches(self):
        """The contacts as a list of ``(x, y, size, id)``, empty when up."""
        return list(self.read_points())
