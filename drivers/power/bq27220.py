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
programmed into it, 3,000 mAh unless something has set another.

The gauge says a battery is there while its BIN pin is low. Some boards tie
that pin low for good, so the gauge reports a battery, usually a full one,
with none fitted: the charger holds the battery terminal at its charge
voltage and nothing flows. Pass ``bin_tied_low=True`` on such a board, and
the driver counts a battery as present only while current flows through it.
A battery on a powered board always carries some: its charge, or once the
charger rests, whatever the board draws from it.
"""

import struct

_ADDR = 0x55
_TEMPERATURE = 0x06  # 0.1 K
_VOLTAGE = 0x08  # mV
_BATTERY_STATUS = 0x0A
_CURRENT = 0x0C  # mA, signed, positive while charging
_REMAINING = 0x10  # mAh
_AVG_CURRENT = 0x14  # mA, signed
_FULL_CHARGE = 0x12  # mAh
_SOC = 0x2C  # %
_SOH = 0x2E  # %

_DSG = 0x0001
_BATTPRES = 0x0008

# Below the gauge's own 10 mA sleep threshold, above its noise with no cell.
_FLOW_MA = 5


class BQ27220:
    """BQ27220 fuel gauge on an I2C bus.

    Args:
        i2c: a ``machine.I2C`` or ``busio.I2C``.
        address: the gauge's I2C address.
        bin_tied_low: True on a board that ties the gauge's BIN pin low, so
            that its battery-present flag is always set. The driver then
            counts a battery as present only while current flows through it.
    """

    def __init__(self, i2c, address=_ADDR, bin_tied_low=False):
        self._i2c = i2c
        self._addr = address
        self._bin_tied_low = bin_tied_low
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

    def _signed(self, cmd):
        return struct.unpack("<h", struct.pack("<H", self._word(cmd)))[0]

    @property
    def present(self):
        """True when a battery is connected."""
        if not self.status & _BATTPRES:
            return False
        if not self._bin_tied_low:
            return True
        # The flag can't see the battery here. A battery takes or gives some
        # current while the board runs; the charger's output with no battery
        # gives the gauge none.
        return (
            abs(self._signed(_CURRENT)) >= _FLOW_MA
            or abs(self._signed(_AVG_CURRENT)) >= _FLOW_MA
        )

    @property
    def voltage(self):
        """Battery voltage in volts, or None with no battery."""
        if not self.present:
            return None
        return self._word(_VOLTAGE) / 1000

    @property
    def current(self):
        """Current in mA: positive while charging, negative while discharging."""
        return self._signed(_CURRENT)

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

        A battery that isn't charging and that the gauge doesn't flag as
        discharging reads "full": the charger has stopped on a full cell and
        the board runs from USB.
        """
        if not self.present:
            return "missing"
        status = self.status
        if status & _DSG:
            return "discharging"
        if self.current > 0:
            return "charging"
        return "full"
