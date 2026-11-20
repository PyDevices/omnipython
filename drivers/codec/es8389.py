# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Drive the Everest ES8389 stereo codec: its DAC and two microphone ADCs.

The register sequence follows Espressif's esp_codec_dev ``es8389`` driver
(Apache-2.0). The codec runs as an I2S slave. On a board that doesn't wire
MCLK to the codec, it clocks itself from BCLK (``use_mclk=False``, the
default): its clock tree is then set per rate and slot width from a table, so
only the rates in `RATES` work, with stereo slots of 16 bits (BCLK at 32
times the rate) or 32 bits (64 times)::

    codec = ES8389(i2c, rate=48000)
    codec.enable_output(True)
    codec.dac_mute(False)
    codec.set_dac_volume(80)

Both ADC channels are differential microphone inputs: MIC1 is the left slot
and MIC2 the right. They record from 16- or 32-bit slots, the same width the
DAC plays, so one I2S channel can play and record at once. Clocked from BCLK,
the codec takes its setup only while BCLK runs: start I2S first, then
configure it, or the ADC sends nothing::

    # with I2S already clocking 16-bit slots at 16 kHz
    codec.configure(16000, bits=16)
    codec.enable_input(True)
"""

import time

try:
    from micropython import const
except ImportError:
    def const(x):
        return x

I2C_ADDR = const(0x10)
CHIP_ID = (0x83, 0x89)  # registers 0xFD and 0xFE

# Clock-manager values from Espressif's table, by slot width and rate: registers
# 0x04-0x0A, 0x0F (top two bits), 0x11, 0x21, 0x22, 0x26, 0x30 (top two bits),
# 0x41, 0x42, 0x43 (mask 0x81), 0xF0 (mask 0x73), 0xF1, 0x16, 0x18, 0x19.
_COEFF = {
    16: {  # BCLK at 32 fs
        8000: (0x00, 0x57, 0x84, 0xD0, 0x03, 0xC1, 0xB0, 0x00, 0x00, 0x1F, 0x7F, 0xBF,
               0xC0, 0xFF, 0x7F, 0x01, 0x12, 0x00, 0x09, 0x19, 0x07),
        16000: (0x00, 0x55, 0x84, 0xD0, 0x01, 0xC1, 0x90, 0x00, 0x00, 0x1F, 0x7F, 0xBF,
                0xC0, 0xFF, 0x7F, 0x00, 0x12, 0x00, 0x12, 0x31, 0x0E),
        44100: (0x00, 0x45, 0xA4, 0xD0, 0x10, 0xD1, 0x80, 0x00, 0x00, 0x1F, 0x7F, 0xBF,
                0xC0, 0x7F, 0x7F, 0x00, 0x12, 0x00, 0x35, 0x91, 0x28),
        48000: (0x00, 0x45, 0xA4, 0xD0, 0x10, 0xD1, 0x80, 0x00, 0x00, 0x1F, 0x7F, 0xBF,
                0xC0, 0x7F, 0x7F, 0x00, 0x12, 0x00, 0x35, 0x91, 0x28),
    },
    32: {  # BCLK at 64 fs
        8000: (0x00, 0x4D, 0x24, 0xC0, 0x03, 0xD1, 0xB0, 0x00, 0x00, 0x1F, 0x7F, 0xBF,
               0xC0, 0xFF, 0x7F, 0x01, 0x12, 0x00, 0x09, 0x19, 0x07),
        16000: (0x00, 0x45, 0x24, 0xC0, 0x01, 0xD1, 0x90, 0x00, 0x00, 0x1F, 0x7F, 0xBF,
                0xC0, 0xFF, 0x7F, 0x00, 0x12, 0x00, 0x12, 0x31, 0x0E),
        44100: (0x00, 0x51, 0x00, 0xC0, 0x10, 0xC1, 0x80, 0x00, 0x00, 0x1F, 0x7F, 0xBF,
                0xC0, 0x7F, 0x7F, 0x00, 0x12, 0x00, 0x35, 0x91, 0x28),
        48000: (0x00, 0x51, 0x04, 0xC0, 0x10, 0xC1, 0x80, 0x00, 0x00, 0x1F, 0x7F, 0xBF,
                0xC0, 0x7F, 0x7F, 0x00, 0x12, 0x00, 0x35, 0x91, 0x28),
    },
}
RATES = tuple(sorted(_COEFF[16]))

# DAC volume: 0x00 is -95.5 dB, then half a dB a step, 0xBF is 0 dB and 0xFF
# +32 dB. One percent a step up to 0 dB, as the ES8311 driver does.
_VOL_0DB = const(0xBF)

# Microphone preamp steps (low nibble of 0x72 and 0x73), 0 to 36.5 dB.
_MIC_STEPS = (0x0, 0x1, 0x2, 0x3, 0x6, 0x7, 0x8, 0x9, 0xA, 0xB, 0xC, 0xD, 0xE)
_ADC_INSEL_DIFF = const(0x10)  # MIC1P-MIC1N on the left, MIC2N-MIC2P on the right

_S16_I2S = const(0x60)  # 16-bit words, Philips I2S, in 0x20 (ADC) and 0x40 (DAC)
_WORD_BITS = {16: 0x60, 32: 0x80}  # word length field, bits 7-5 of 0x20 and 0x40

_INIT = (
    (0xF3, 0x00), (0x00, 0x7E), (0xF3, 0x38), (0x24, 0x64), (0x25, 0x04),
    (0x45, 0x03), (0x60, 0x2A), (0x61, 0xC9), (0x62, 0x4F), (0x63, 0x06),
    (0x6B, 0x00), (0x6D, 0x16), (0x6E, 0xAA), (0x6F, 0x66), (0x70, 0x99),
    (0x23, 0x00), (0x72, _ADC_INSEL_DIFF), (0x73, _ADC_INSEL_DIFF),
    (0x10, 0xC4), (0x01, 0x08), (0xF1, 0x00),
    (0x12, 0x01), (0x13, 0x01), (0x14, 0x01), (0x15, 0x01), (0x16, 0x35),
    (0x17, 0x09), (0x18, 0x91), (0x19, 0x28), (0x1A, 0x01), (0x1B, 0x01),
    (0x1C, 0x11), (0x2A, 0x00), (0x20, _S16_I2S), (0x40, _S16_I2S),
    (0xF0, 0x01), (0x02, 0x00), (0x04, 0x00), (0x05, 0x10), (0x06, 0x00),
    (0x07, 0xC0), (0x08, 0x00), (0x09, 0xC0), (0x0A, 0x80), (0x0B, 0x04),
    (0x0C, 0x01), (0x0D, 0x00), (0x0F, 0x10), (0x21, 0x1F), (0x22, 0x7F),
    (0x2F, 0xC0), (0x30, 0xF4), (0x31, 0x00), (0x44, 0x00), (0x41, 0x7F),
    (0x42, 0x7F), (0x43, 0x10), (0x49, 0x0F), (0x4C, 0xC0),
    (0x00, 0x00), (0x03, 0xC1), (0x00, 0x01), (0x4D, 0x00),
    (0x26, 0xBF), (0x27, 0xBF), (0x28, 0xBF), (0x46, 0xBF), (0x47, 0xBF),
    (0x48, 0xBE),
    # No DAC reference in the ADC stream, so the ADC sends two slots, not four.
    (0xF0, 0x12),
)

_BIAS_ON = (
    (0x4D, 0x00), (0x61, 0xD9), (0x64, 0x8F), (0x10, 0xE4), (0x00, 0x01),
    (0x03, 0xC3), (0x24, 0x6A), (0x25, 0x0A),
)


def _sleep_ms(milliseconds):
    if hasattr(time, "sleep_ms"):
        time.sleep_ms(milliseconds)
    else:
        time.sleep(milliseconds / 1000)


class ES8389:
    """ES8389 codec, set up for 16-bit I2S with the chip as slave.

    Args:
        i2c: a ``machine.I2C`` the codec answers on.
        address: the codec's I2C address, 0x10 with AD0 and AD1 low.
        rate: the sample rate to set up now, one of `RATES` unless
            ``use_mclk`` is True; `configure` changes it, and the slot width.
        use_mclk: True when the board drives the codec's MCLK pin; the clock
            tree is then left to the chip and any rate works.

    Raises:
        OSError: nothing at ``address`` reads back the ES8389's chip ID.
    """

    channels = 2

    def __init__(self, i2c, address=I2C_ADDR, *, rate=48000, use_mclk=False):
        self._i2c = i2c
        self._addr = address
        self._b = bytearray(1)
        self.use_mclk = use_mclk
        ident = (self._rd(0xFD), self._rd(0xFE))
        if ident != CHIP_ID:
            raise OSError("no ES8389 at 0x%02x (chip id %02x %02x)" % (address, ident[0], ident[1]))
        for reg, val in _INIT:
            self._wr(reg, val)
        # Clock source: the MCLK pin, or BCLK through the internal multiplier.
        self._update(0x02, 0xC0, 0x00 if use_mclk else 0x40)
        self.rate = None
        self.bits = 16
        self.dac_volume = 100
        self.gain = 0
        self.output_enabled = False
        self.input_enabled = False
        self.configure(rate)
        self.dac_mute(True)

    def _wr(self, reg, val):
        self._b[0] = val
        self._i2c.writeto_mem(self._addr, reg, self._b)

    def _rd(self, reg):
        self._i2c.readfrom_mem_into(self._addr, reg, self._b)
        return self._b[0]

    def _update(self, reg, mask, val):
        self._wr(reg, (self._rd(reg) & ~mask) | (val & mask))

    def configure(self, rate, bits=16):
        """Set the clock tree and word length for ``rate`` (Hz) and ``bits``
        per slot, 16 or 32.

        Raises:
            ValueError: the codec clocks from BCLK and ``rate`` isn't in
                `RATES`, or ``bits`` isn't 16 or 32.
        """
        rate = int(rate)
        if bits not in _WORD_BITS:
            raise ValueError("the ES8389 takes 16- or 32-bit slots, not %r" % (bits,))
        self._update(0x20, 0xE0, _WORD_BITS[bits])
        self._update(0x40, 0xE0, _WORD_BITS[bits])
        self.bits = bits
        if self.use_mclk:
            self.rate = rate
            return
        c = _COEFF[bits].get(rate)
        if c is None:
            raise ValueError("the ES8389 clocked from BCLK takes %s Hz, not %d" % (RATES, rate))
        for reg, val in zip((0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A), c[:7]):
            self._wr(reg, val)
        self._update(0x0F, 0xC0, c[7])
        self._wr(0x11, c[8])
        self._wr(0x21, c[9])
        self._wr(0x22, c[10])
        self._wr(0x26, c[11])
        self._update(0x30, 0xC0, c[12])
        self._wr(0x41, c[13])
        self._wr(0x42, c[14])
        self._update(0x43, 0x81, c[15])
        self._update(0xF0, 0x73, c[16])
        self._wr(0xF1, c[17])
        self._wr(0x16, c[18])
        self._wr(0x18, c[19])
        self._wr(0x19, c[20])
        self.rate = rate
        # The codec drops to standby when its clocks pause; bring the analog
        # path back if it was up.
        if self.output_enabled or self.input_enabled:
            self._bias(True)

    def _bias(self, on):
        if on:
            self._update(0x69, 0x20, 0x20)
            for reg, val in _BIAS_ON:
                self._wr(reg, val)
        else:
            self._update(0x40, 0x03, 0x03)
            self._wr(0x10, 0xD4)
            _sleep_ms(70)
            self._wr(0x61, 0x59)
            self._wr(0x64, 0x00)
            self._wr(0x03, 0x00)
            self._wr(0x00, 0x7E)

    def enable_output(self, enable=True):
        """Power the analog path up for playback, or down when the
        microphones aren't using it either."""
        enable = bool(enable)
        if enable or not self.input_enabled:
            self._bias(enable)
        if not enable:
            self.dac_mute(True)
        self.output_enabled = enable

    def enable_input(self, enable=True):
        """Power the analog path up for the microphones and unmute the ADC, or
        mute it and power down when playback isn't using the path."""
        enable = bool(enable)
        if enable or not self.output_enabled:
            self._bias(enable)
        self._update(0x20, 0x03, 0x00 if enable else 0x03)
        self.input_enabled = enable

    def dac_mute(self, mute=True):
        """Soft-mute both DAC channels, or unmute them."""
        self._update(0x40, 0x03, 0x03 if mute else 0x00)
        self.dac_muted = bool(mute)

    def set_dac_volume(self, percent):
        """Set the DAC volume from 0 (muted) to 100 (0 dB), half a dB a percent."""
        percent = max(0, min(100, int(percent)))
        reg = 0 if percent == 0 else _VOL_0DB - (100 - percent)
        self._wr(0x46, reg)
        self._wr(0x47, reg)
        self.dac_volume = percent
        return percent

    def set_gain(self, percent):
        """Set both microphone preamps from 0 (0 dB) to 100 (36.5 dB)."""
        percent = max(0, min(100, int(percent)))
        step = _MIC_STEPS[percent * (len(_MIC_STEPS) - 1) // 100]
        self._wr(0x72, _ADC_INSEL_DIFF | step)
        self._wr(0x73, _ADC_INSEL_DIFF | step)
        self.gain = percent
        return percent

    def close(self):
        """Mute and power down both paths."""
        self.input_enabled = False
        self.enable_output(False)
        self._update(0x20, 0x03, 0x03)

    deinit = close
