# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""Lazy constructors for the Waveshare ESP32-S31-Touch-LCD-4.3C. PERIPHERALS = lazy roles only.

Pins are from Waveshare's schematic. Everything on I2C shares the board bus
(SDA 0, SCL 1), which the 16-pin header also brings out through a level
shifter, at 3.3 V or 5 V by the header's jumper:

    GT911 touch       0x5D    ES8389 codec        0x10
    PCF85063A clock   0x51    QMI8658 IMU         0x6B
    BQ27220 gauge     0x55

    ES8389 I2S        BCLK 37, LRCK 38, DSDIN 39 (to the codec), ASDOUT 42
                      (from it); no MCLK, the codec clocks from BCLK
    NS4150B amplifier PA_CTRL 57, high to play; it drives the speaker
                      connector from the codec's left output
    microSD (SDIO)    CLK 24, CMD 25, D0-D3 20-23; power switch 56, low on
    CAN (MCP2562FD)   TX 4, RX 5
    RS485 (SP3485)    TX 6, RX 7, driver enable 61 (also the BOOT button)
    status LED        55, low to light
    header GPIOs      48-53
    interrupts        touch 2, clock 3, IMU 54 and 60
    USB host (J3)     4-pin header: GND, USB20_P (D+), USB20_N (D-) and the
                      board's 5 V, through 2.2 ohm resistors; the chip's
                      high-speed USB OTG port
    USB-C             a CH343 serial bridge to UART0, the REPL; not USB

The speaker and the microphones share one I2S port. With the audio pump in
the firmware, ``pcm_in`` reads the receive half of the pump's own channel, so
it records while ``audio_out`` plays, as a speakerphone needs; both run
16-bit slots, at the output's rate when it's open. Without the pump,
``machine.I2S`` takes one direction per port, so ``pcm_in`` and the speaker
refuse each other: opening one while the other is open raises OSError.

J3 is the board's only USB host port, for ``usb.core`` and the
``usb.host.*`` packages; wire it to a USB-A socket or a hub's upstream cable.
It runs at high speed. A full-speed device (a keyboard, a MIDI controller)
works plugged straight in or behind a high-speed hub, since the host sends
split transactions to the hub's transaction translator.
``usb.core.start(full_speed=True)`` still holds the whole port, hub
included, to full speed. Checked through a powered four-port hub on J3: at
full speed a flash drive read back a 1 MiB file with a matching SHA-256, a
USB MIDI keyboard's notes arrived, a webcam streamed 640x480 MJPEG and
another board's CDC console answered; at high speed the drive and the
webcam (640x480 and 1280x720 MJPEG) ran, and a full-speed board's MIDI,
keyboard and CDC console ran through the hub's transaction translator while
the webcam streamed. A USB sound card hasn't been run on it. The firmware has no USB device mode,
so there is no ``usb_device`` role.
"""

import boarddev
import sys

PERIPHERALS = frozenset(
    {
        "audio_out",
        "pcm_out",
        "pcm_in",
        "audio_power",
        "audio_in_power",
        "sdcard",
        "accelerometer",
        "gyroscope",
        "rtc",
        "battery",
        "i2c",
        "led",
        "boot_button",
        "can",
        "rs485",
        "wlan",
        "ble",
    }
)

# Audio roles are factories: first attribute access must not construct, so a
# caller can pass a format. See boarddev.bind_lazy.
FACTORY_ROLES = frozenset({"audio_out", "pcm_out", "pcm_in", "audio_power", "audio_in_power"})

from audiodev import (
    AudioCapability,
    AudioFactory,
    AudioFormat,
    AudioSession,
    I2SWire,
    adapt_channels,
    check_latency,
    negotiate,
    pace_output,
    queue_bytes,
)
from audiodev.i2s_audio import I2SPCMInput, I2SPCMOutput

_I2C_PORT = 0
_I2C_SDA = 0
_I2C_SCL = 1

_SCLK = 37
_LRCK = 38
_DSDIN = 39
_ASDOUT = 42
_PA_CTRL = 57
_SD_POWER = 56
_CAN_TX = 4
_CAN_RX = 5
_RS485_TX = 6
_RS485_RX = 7
_RS485_EN = 61
_LED = 55

# The rates the codec's BCLK clock tree has settings for.
_RATES = (8000, 16000, 44100, 48000)
_RATE = 48000
_DEFAULT_VOLUME = 85

AUDIO_OUT = AudioCapability(
    AudioFormat(_RATE, 2, 16),
    rates=_RATES,
    channels=(1, 2),
    native_channels=1,  # the amplifier takes the left output only
    bits=(16,),
    # sd_in is the codec's ADC output. Publishing it lets the audio pump open
    # the port as one TX/RX pair, so pcm_in records while the output plays.
    wire=I2SWire(0, sck=_SCLK, ws=_LRCK, sd=_DSDIN, sd_in=_ASDOUT),
)

# Two microphones, MIC1 on the left slot and MIC2 on the right. The wire runs
# 32-bit slots, and pcm_in hands back 16-bit samples.
AUDIO_IN = AudioCapability(
    AudioFormat(_RATE, 2, 16),
    rates=_RATES,
    channels=(1, 2),
    native_channels=2,
    bits=(16,),
)

_IBUF = 20000
_MIN_IBUF = 4096

_codec = None
_rate = _RATE
_pa = None
_i2c_own = None
_imu = None
_rtc = None
_gauge = None


def _get_codec():
    global _codec
    if _codec is None:
        from es8389 import ES8389

        _codec = ES8389(_i2c_bus(), rate=_rate)
        _codec.set_dac_volume(_DEFAULT_VOLUME)
    return _codec


_SESSION = AudioSession(codec_factory=_get_codec, duplex=False)
_INPUT_SESSION = AudioSession(codec_factory=_get_codec, duplex=False)


def load_peripherals(ns):
    boarddev.bind_lazy(ns, sys.modules[__name__])


def _i2c_bus():
    """The board bus, shared with board_config when it already opened it.

    Never ``import board_config`` from here: a non-graphics app importing
    this module must not start the display.
    """
    global _i2c_own

    bc = sys.modules.get("board_config")
    bus = getattr(bc, "i2c", None) if bc is not None else None
    if bus is not None:
        return bus
    if _i2c_own is None:
        from machine import I2C, Pin

        _i2c_own = I2C(_I2C_PORT, sda=Pin(_I2C_SDA), scl=Pin(_I2C_SCL), freq=400_000)
    return _i2c_own


def i2c():
    """The board I2C bus, also on the 16-pin header (SDA, SCL)."""
    return _i2c_bus()


# --- audio -------------------------------------------------------------------


def _refuse_if_held(session, wanted, holder):
    """Refuse to open I2S(0) while the other direction has it.

    machine.I2S takes one direction per port, and constructing I2S(0) while
    it is in use deinitialises the live instance without an error. The
    speaker and the microphones also need different slot widths here.
    """
    if session._owners:
        raise OSError(
            "I2S(0) is in use by the %s: this board's speaker and microphones "
            "share one I2S port, so close the %s before opening the %s"
            % (holder, holder, wanted)
        )


def _pa_pin():
    global _pa
    if _pa is None:
        from machine import Pin

        _pa = Pin(_PA_CTRL, Pin.OUT, value=0)
    return _pa


def _output_stream(ibuf, fmt):
    from machine import I2S, Pin

    _refuse_if_held(_INPUT_SESSION, "speaker", "microphones")
    return I2S(
        0,
        sck=Pin(_SCLK),
        ws=Pin(_LRCK),
        sd=Pin(_DSDIN),
        mode=I2S.TX,
        bits=16,
        format=I2S.STEREO if fmt.channels == 2 else I2S.MONO,
        rate=fmt.rate,
        ibuf=ibuf,
    )


def _output_power(enable):
    codec = _get_codec()
    if enable:
        codec.configure(_rate, 16)
        codec.enable_output(True)
        codec.dac_mute(False)
        _pa_pin().value(1)
    else:
        _pa_pin().value(0)
        codec.enable_output(False)


def _pcm_out(format=None, *, latency=None, queue_ms=None):
    """The speaker: a raw ``PCMOutput``, 48 kHz 16-bit stereo by default.

    The amplifier plays the left channel; stereo content opens two slots and
    nothing is mixed down. Ask ``pcm_out.capability`` what it takes.
    """
    global _rate

    check_latency(latency)
    wire, source = negotiate(AUDIO_OUT, format)
    _rate = wire.rate
    ibuf = queue_bytes(wire, None, queue_ms, default=_IBUF, minimum=_MIN_IBUF)
    device = I2SPCMOutput(
        lambda: _output_stream(ibuf, wire),
        wire,
        session=_SESSION,
        set_hardware_volume=lambda value: _get_codec().set_dac_volume(value),
        set_hardware_mute=lambda value: _get_codec().dac_mute(value),
        power=_output_power,
        # For the audio pump, which opens I2S itself in C on firmware that
        # carries it, and powers the codec through audio_power.
        wire=AUDIO_OUT.wire,
        audio_power=_audio_power,
    )
    device.set_volume(_DEFAULT_VOLUME)
    if source is not wire:
        from audiodev.accel import best_remix

        device = adapt_channels(device, source, remix=best_remix())
    return pace_output(device, queue_ms=80)


def _audio_out(format=None, *, latency=None, queue_ms=None, **kwargs):
    """``AudioOut`` sample player on the speaker. Requires audiodsp; use
    ``pcm_out`` for raw PCM bytes, which has no DSP dependency."""
    from audiodev.sample_out import AudioOut

    pump = {}
    for key in ("chunk_ms", "lookahead_chunks", "max_catchup_chunks"):
        if key in kwargs:
            pump[key] = kwargs.pop(key)
    if latency == "low":
        pump.setdefault("chunk_ms", 10)
        pump.setdefault("lookahead_chunks", 4)
    return AudioOut(_pcm_out(format, latency=latency, queue_ms=queue_ms, **kwargs), **pump)


def _audio_power(enable=True, *, volume=None):
    """Bring the codec and amplifier up or down without opening a stream,
    for a consumer that drives I2S itself at 16-bit stereo, at the rate the
    last ``pcm_out`` asked for."""
    if enable:
        _output_power(True)
        if volume is not None:
            _get_codec().set_dac_volume(int(volume))
    else:
        _output_power(False)
    return enable


class _WideI2SPCMInput(I2SPCMInput):
    """Reads 32-bit I2S slots and hands back their top 16 bits.

    A 16-bit view of a 32-bit stream is every other half-word, which a
    two-pixel-wide RGB565 framebuffer blitted one pixel left picks out in C.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._wide = None

    def _narrow(self, buf, count):
        import framebuf

        frames = count // 4
        src = framebuf.FrameBuffer(self._wide, 2, frames, framebuf.RGB565)
        framebuf.FrameBuffer(buf, 1, frames, framebuf.RGB565).blit(src, -1, 0)
        return frames * 2

    def _scratch(self, buf):
        need = len(buf) * 2
        if self._wide is None or len(self._wide) < need:
            self._wide = bytearray(need)
        return memoryview(self._wide)[:need]

    def _readinto(self, buf):
        return self._narrow(buf, self._i2s.readinto(self._scratch(buf)))

    async def _areadinto(self, buf):
        wide = self._scratch(buf)
        return self._narrow(buf, await super()._areadinto(wide))


def _input_stream(ibuf, fmt):
    from machine import I2S, Pin

    _refuse_if_held(_SESSION, "microphones", "speaker")
    return I2S(
        0,
        sck=Pin(_SCLK),
        ws=Pin(_LRCK),
        sd=Pin(_ASDOUT),
        mode=I2S.RX,
        bits=32,
        format=I2S.STEREO,
        rate=fmt.rate,
        ibuf=ibuf,
    )


def _input_power(enable):
    codec = _get_codec()
    if enable:
        codec.configure(_rate, 32)
    codec.enable_input(enable)


def _duplex_pump():
    """``audiodev.pump`` when this firmware records while it plays, else None."""
    try:
        from audiodev import pump
    except ImportError:
        return None
    return pump if pump.duplex() else None


def _duplex_input_power(enable):
    # The pump's channel is clocking by now: the codec, which runs from BCLK,
    # has to be set up with BCLK on its pin. A playing output has already set
    # the same rate and width, and rewriting the clock tree under it clicks.
    codec = _get_codec()
    if enable and (codec.rate != _rate or codec.bits != 16):
        codec.configure(_rate, 16)
    codec.enable_input(enable)


def _pcm_in(format=None, *, latency=None, queue_ms=None):
    """The two microphones: a raw ``PCMInput`` with hardware gain,
    48 kHz 16-bit stereo by default (MIC1 left, MIC2 right).

    Asking for one channel mixes the two. With the audio pump in the
    firmware, it reads the receive half of the pump's channel, so it records
    while ``audio_out`` plays, at the output's rate. Without it, opening it
    while the speaker is open raises OSError, and so does the reverse.
    """
    global _rate

    check_latency(latency)
    wire, source = negotiate(AUDIO_IN, format)
    pump = _duplex_pump()
    if pump is not None:
        _rate = wire.rate
        return pump.PumpPCMInput(
            source,
            wire=AUDIO_OUT.wire,
            ring_bytes=queue_bytes(wire, latency, queue_ms, default=_IBUF, minimum=_MIN_IBUF),
            take="mix",
            session=_INPUT_SESSION,
            set_hardware_gain=lambda value: _get_codec().set_gain(value),
            power=_duplex_input_power,
        )
    if wire.channels != 2:
        # The wire takes two slots: open it in stereo and mix down.
        from audiodev import adapt_input_channels
        from audiodev.accel import best_remix

        stereo = AudioFormat(wire.rate, 2, 16)
        return adapt_input_channels(
            _pcm_in(stereo, latency=latency, queue_ms=queue_ms), wire, remix=best_remix()
        )
    _rate = wire.rate
    ibuf = queue_bytes(wire, latency, queue_ms, default=_IBUF, minimum=_MIN_IBUF) * 2
    return _WideI2SPCMInput(
        lambda: _input_stream(ibuf, wire),
        wire,
        session=_INPUT_SESSION,
        set_hardware_gain=lambda value: _get_codec().set_gain(value),
        power=_input_power,
    )


def _audio_in_power(enable=True, *, rate=None, gain=None):
    """Bring the microphones' ADC up or down without opening a stream, for a
    recorder that drives I2S itself. It must clock 32-bit stereo slots at
    ``rate`` (default 48 kHz)."""
    global _rate
    codec = _get_codec()
    if not enable:
        codec.enable_input(False)
        return False
    if rate is not None:
        _rate = int(rate)
    codec.configure(_rate, 32)
    codec.enable_input(True)
    if gain is not None:
        codec.set_gain(gain)
    return True


pcm_out = AudioFactory(_pcm_out, AUDIO_OUT)
pcm_in = AudioFactory(_pcm_in, AUDIO_IN)
audio_out = AudioFactory(_audio_out, AUDIO_OUT)
audio_power = _audio_power
audio_in_power = _audio_in_power


# --- storage, sensors, power -------------------------------------------------


def sdcard():
    """The microSD slot over 4-bit SDIO (``machine.SDCard`` slot 0).

    The card's power switch is switched on first. Mount it yourself::

        os.mount(board_config.sdcard, "/sd")
    """
    from machine import Pin, SDCard

    Pin(_SD_POWER, Pin.OUT, value=0)
    return SDCard(slot=0, width=4)


def _qmi8658():
    global _imu
    if _imu is None:
        from qmi8658 import QMI8658

        _imu = QMI8658(_i2c_bus(), address=0x6B)
    return _imu


def accelerometer():
    """QMI8658 accelerometer, ``acceleration`` in g (same instance as gyroscope)."""
    return _qmi8658()


def gyroscope():
    """QMI8658 gyroscope, ``gyro`` in degrees a second (same instance as accelerometer)."""
    return _qmi8658()


def rtc():
    """PCF85063A clock, kept by the battery: ``datetime()`` and
    ``datetime(t)`` as ``machine.RTC``, ``lost_power``, alarm and countdown."""
    global _rtc
    if _rtc is None:
        from pcf85063 import PCF85063

        _rtc = PCF85063(_i2c_bus())
    return _rtc


def battery():
    """BQ27220 fuel gauge: ``voltage`` (volts, None with no battery),
    ``percent``, ``current`` (mA, positive while charging), ``charging``,
    ``battery_status``."""
    global _gauge
    if _gauge is None:
        from bq27220 import BQ27220

        _gauge = BQ27220(_i2c_bus())
    return _gauge


# --- pins, buses, radios -------------------------------------------------------


def led():
    """The red status LED as a ``machine.Signal``: ``on()`` lights it."""
    from machine import Pin, Signal

    return Signal(Pin(_LED, Pin.OUT, value=1), invert=True)


def boot_button():
    """The BOOT button (GPIO61, ``value()`` 0 when pressed).

    GPIO61 is also the RS485 transceiver's driver enable, so don't use the
    button and ``rs485`` together.
    """
    from machine import Pin

    return Pin(_RS485_EN, Pin.IN, Pin.PULL_UP)


def can():
    """The MCP2562FD CAN transceiver on GPIO4 (TX) and GPIO5 (RX), at 500 kbit/s.

    Raises NotImplementedError on firmware without ``machine.CAN``.
    """
    import canbus

    return canbus.open(_CAN_TX, _CAN_RX, baudrate=500_000)


def rs485():
    """The SP3485 RS485 transceiver on UART1: TX 6, RX 7, driver enable 61.

    The transceiver's receiver is off while it transmits, so it never hears
    its own bytes.
    """
    from rs485 import RS485

    return RS485(1, tx=_RS485_TX, rx=_RS485_RX, de=_RS485_EN, baudrate=115200)


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
