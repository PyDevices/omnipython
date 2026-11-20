# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Read a battery through the TI BQ27220 fuel gauge.

Runs on MicroPython and CircuitPython: pass a ``machine.I2C`` or a
``busio.I2C``::

    gauge = BQ27220(i2c)
    gauge.voltage, gauge.percent, gauge.current, gauge.battery_status

The gauge learns the cell as it charges and discharges, so ``percent`` is a
rough guide until it has seen a full cycle. It assumes the design capacity
programmed into it, 1,000 mAh unless something has set another.
"""

import struct

_ADDR = 0x55
_TEMPERATURE = 0x06  # 0.1 K
_VOLTAGE = 0x08  # mV
_BATTERY_STATUS = 0x0A
_CURRENT = 0x0C  # mA, signed, positive while charging
_REMAINING = 0x10  # mAh
_FULL_CHARGE = 0x12  # mAh
_SOC = 0x2C  # %
_SOH = 0x2E  # %

_DSG = 0x0001
_BATTPRES = 0x0008


class BQ27220:
    """BQ27220 fuel gauge on an I2C bus.

    Args:
        i2c: a ``machine.I2C`` or ``busio.I2C``.
        address: the gauge's I2C address.
    """

    def __init__(self, i2c, address=_ADDR):
        self._i2c = i2c
        self._addr = address
        self._busio = hasattr(i2c, "try_lock")
        self._reg = bytearray(1)
        self._buf = bytearray(2)

    def _word(self, cmd):
        if self._busio:
            self._reg[0] = cmd
            while not self._i2c.try_lock():
                pass
            try:
                self._i2c.writeto_then_readfrom(self._addr, self._reg, self._buf)
            finally:
                self._i2c.unlock()
        else:
            self._i2c.readfrom_mem_into(self._addr, cmd, self._buf)
        return self._buf[0] | (self._buf[1] << 8)

    @property
    def status(self):
        """The raw BatteryStatus word."""
        return self._word(_BATTERY_STATUS)

    @property
    def present(self):
        """True when a battery is connected."""
        return bool(self.status & _BATTPRES)

    @property
    def voltage(self):
        """Battery voltage in volts, or None with no battery."""
        if not self.present:
            return None
        return self._word(_VOLTAGE) / 1000

    @property
    def current(self):
        """Current in mA: positive while charging, negative while discharging."""
        return struct.unpack("<h", struct.pack("<H", self._word(_CURRENT)))[0]

    @property
    def percent(self):
        """State of charge from 0 to 100, or None with no battery."""
        if not self.present:
            return None
        return self._word(_SOC)

    @property
    def remaining_capacity(self):
        """Charge left, in mAh."""
        return self._word(_REMAINING)

    @property
    def full_charge_capacity(self):
        """What the gauge expects a full charge to hold, in mAh."""
        return self._word(_FULL_CHARGE)

    @property
    def health(self):
        """State of health from 0 to 100."""
        return self._word(_SOH)

    @property
    def temperature(self):
        """The gauge's temperature in degrees Celsius."""
        return self._word(_TEMPERATURE) / 10 - 273.15

    @property
    def charging(self):
        """True while charge current flows into the battery."""
        return self.present and self.current > 0

    @property
    def battery_status(self):
        """One of "missing", "full", "charging" or "discharging".

        A battery that neither charges nor discharges reads "full": the
        charger has stopped on a full cell and the board runs from USB.
        """
        status = self.status
        if not status & _BATTPRES:
            return "missing"
        if status & _DSG:
            return "discharging"
        if self.current > 0:
            return "charging"
        return "full"
