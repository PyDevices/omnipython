# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Read and set the NXP PCF85063A real-time clock.

Runs on MicroPython and CircuitPython: pass a ``machine.I2C`` or a
``busio.I2C``. The date and time read and write as the same 8-tuple
``machine.RTC.datetime()`` uses::

    rtc = PCF85063(i2c)
    rtc.datetime((2026, 11, 19, 3, 14, 30, 0, 0))  # Thursday 14:30:00
    year, month, day, weekday, hour, minute, second, _ = rtc.datetime()

``weekday`` is stored as given (MicroPython counts Monday as 0); the chip only
counts it. ``lost_power`` is True when the oscillator stopped since the clock
was last set, so the time it reads can't be trusted.

The chip's INT pin (open drain, low while a flag is set) can wake a sleeping
board. Two sources drive it, with the same calls as the `PCF8563` driver::

    rtc.alarm(hour=7, minute=30)    # daily at 07:30; minute only = hourly
    rtc.countdown(90)               # once, in 90 s (up to 255 s, then minutes)
    rtc.alarm_fired, rtc.countdown_fired
    rtc.clear_interrupts()          # releases INT; alarm and countdown stay set
    rtc.alarm(None); rtc.countdown(None)   # off
"""

_ADDR = 0x51
_CONTROL1 = 0x00  # STOP 0x20
_CONTROL2 = 0x01  # AIE 0x80, AF 0x40, TF 0x08
_SECONDS = 0x04
_ALARM = 0x0B  # second, minute, hour, day, weekday; bit 7 set = ignore that field
_TIMER = 0x10
_TIMER_MODE = 0x11  # clock 0x18, TE 0x04, TIE 0x02
_OS = 0x80  # seconds bit 7: the oscillator stopped


def _bcd2bin(value):
    return (value >> 4) * 10 + (value & 0x0F)


def _bin2bcd(value):
    return ((value // 10) << 4) | (value % 10)


class PCF85063:
    """PCF85063A clock on an I2C bus.

    Args:
        i2c: a ``machine.I2C`` or ``busio.I2C``.
        address: the chip's I2C address.
    """

    def __init__(self, i2c, address=_ADDR):
        self._i2c = i2c
        self._addr = address
        self._busio = hasattr(i2c, "try_lock")
        self._reg = bytearray(1)
        self._buf = bytearray(7)
        # Make sure the oscillator runs (STOP clear, 24-hour mode, 7 pF load).
        self._write(_CONTROL1, bytes(1))

    def _read(self, reg, buf):
        if self._busio:
            self._reg[0] = reg
            while not self._i2c.try_lock():
                pass
            try:
                self._i2c.writeto_then_readfrom(self._addr, self._reg, buf)
            finally:
                self._i2c.unlock()
        else:
            self._i2c.readfrom_mem_into(self._addr, reg, buf)

    def _write(self, reg, data):
        if self._busio:
            while not self._i2c.try_lock():
                pass
            try:
                self._i2c.writeto(self._addr, bytes([reg]) + bytes(data))
            finally:
                self._i2c.unlock()
        else:
            self._i2c.writeto_mem(self._addr, reg, data)

    def datetime(self, datetime=None):
        """Read the clock, or set it from ``(year, month, day, weekday, hour,
        minute, second[, subsecond])``; the subsecond is ignored. Years run
        2000 to 2099."""
        if datetime is None:
            b = self._buf
            self._read(_SECONDS, b)
            return (
                _bcd2bin(b[6]) + 2000,
                _bcd2bin(b[5] & 0x1F),
                _bcd2bin(b[3] & 0x3F),
                b[4] & 0x07,
                _bcd2bin(b[2] & 0x3F),
                _bcd2bin(b[1] & 0x7F),
                _bcd2bin(b[0] & 0x7F),
                0,
            )
        year, month, day, weekday, hour, minute, second = datetime[:7]
        self._write(
            _SECONDS,
            bytes(
                (
                    _bin2bcd(second),  # writing the seconds clears OS
                    _bin2bcd(minute),
                    _bin2bcd(hour),
                    _bin2bcd(day),
                    weekday & 0x07,
                    _bin2bcd(month),
                    _bin2bcd(year % 100),
                )
            ),
        )
        return None

    # -- alarm and countdown ---------------------------------------------

    def _control2(self, mask, value):
        b = memoryview(self._buf)[:1]
        self._read(_CONTROL2, b)
        # AF and TF clear on writing 0; write 1 to leave a flag alone
        v = (b[0] & 0xB7) | 0x48
        self._write(_CONTROL2, bytes(((v & ~mask) | (value & mask),)))

    def alarm(self, minute=None, hour=None, day=None, weekday=None):
        """Raise INT when every given field matches (fields left as ``None``
        match anything). ``alarm(None)`` with nothing else switches it off."""
        if minute is None and hour is None and day is None and weekday is None:
            self._write(_ALARM, b"\x80\x80\x80\x80\x80")
            self._control2(0xC0, 0x00)  # AIE off, AF cleared
            return
        fields = [0x80]  # seconds never match on their own
        fields.extend(0x80 if v is None else _bin2bcd(v) for v in (minute, hour, day))
        fields.append(0x80 if weekday is None else weekday & 0x07)
        self._write(_ALARM, bytes(fields))
        self._control2(0xC0, 0x80)  # AF cleared, AIE on

    def countdown(self, seconds):
        """Raise INT once, ``seconds`` from now: 1-255 s counts in seconds,
        longer counts in whole minutes (up to 255). ``None`` stops it."""
        if seconds is None:
            self._write(_TIMER_MODE, b"\x18")  # disabled, 1/60 Hz
            self._control2(0x08, 0x00)
            return
        if seconds <= 255:
            clock, count = 0x10, max(1, int(seconds))  # 1 Hz
        else:
            clock, count = 0x18, min(255, (int(seconds) + 59) // 60)  # 1/60 Hz
        self._write(_TIMER_MODE, bytes((clock,)))  # stop while loading
        self._write(_TIMER, bytes((count,)))
        self._control2(0x08, 0x00)  # TF cleared
        self._write(_TIMER_MODE, bytes((clock | 0x06,)))  # TE, TIE, INT level

    def _flags(self):
        b = memoryview(self._buf)[:1]
        self._read(_CONTROL2, b)
        return b[0]

    @property
    def alarm_fired(self):
        return bool(self._flags() & 0x40)

    @property
    def countdown_fired(self):
        return bool(self._flags() & 0x08)

    def clear_interrupts(self):
        """Clear both flags, which releases INT."""
        self._control2(0x48, 0x00)

    @property
    def lost_power(self):
        """True when the time can't be trusted until it is set again."""
        b = memoryview(self._buf)[:1]
        self._read(_SECONDS, b)
        return bool(b[0] & _OS)
