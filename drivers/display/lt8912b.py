# SPDX-FileCopyrightText: 2026 Brad Barnett
# SPDX-FileCopyrightText: 2023-2026 Espressif Systems (Shanghai) CO LTD
# SPDX-FileCopyrightText: 2026 Adafruit Industries
#
# SPDX-License-Identifier: Apache-2.0

"""Send a MIPI DSI display out over HDMI or DVI through a Lontium LT8912B bridge.

`LT8912B` is a ``mipidsi.Display`` that also sets the bridge up over I2C,
with the same constructor and properties as Adafruit's CircuitPython
``adafruit_lt8912b.LT8912B``, so a program written for that runs here. It
configures the bridge first, then starts DSI video, then locks the bridge
to it, because the bridge only locks its pixel clock to a stream that is
already there.

`Bridge` is the I2C side alone. It needs no DSI video, so it can show the
bridge's own test pattern and read its status before anything else works.

The bridge takes RGB888 on the wire with the lanes kept in high speed
through blanking, on one to four data lanes at up to 1.5 Gbps each. An
ESP32-P4 has two lanes and divides a fixed clock by a whole number, so
`fit` turns a standard mode into one the host can make, and `check`
refuses a mode the lanes can't carry.

The register values come from Espressif's ``esp_lcd_lt8912b`` component and
Adafruit's drivers for their LT8912B board, both Apache-2.0, and so is this
file. HDMI audio over I2S is experimental: no public source documents it,
and `Audio` says where each value came from.

Example:
    mode = fit(MODES["1280x720p60"])
    lane_rate = check(mode, 2)
    bus = mipidsi.Bus(minimum_frequency=lane_rate, num_lanes=2)
    display = LT8912B(bus, i2c, **mode.timing())
"""

import time

try:
    from mipidsi import Display as _Display
except ImportError:
    _Display = None

MAIN = 0x48  # main page: clocks, analog, sync polarity, HDMI mode, status
DSI = 0x49  # CEC and DSI page: receiver, timing, the pixel clock (DDS)
AVI = 0x4A  # HDMI page: infoframes and audio
EDID = 0x50  # the monitor's EDID, on the DDC lines

CHIP_ID = b"\x12\xb2"  # main page 0x00 and 0x01

MAX_LANE_RATE = 1_500_000_000  # the bridge's and the ESP32-P4's limit
MIN_LANE_RATE = 80_000_000
MAX_PIXEL_CLOCK = 150_000_000
P4_HOST_CLOCK = 240_000_000  # the ESP32-P4 DPI clock source mipidsi uses

_BITS_PER_PIXEL = 24  # RGB888

# Main page: digital clocks on, TX analog, CBUS analog, HDMI PLL analog.
_MAIN_INIT = (
    (0x02, 0xF7), (0x08, 0xFF), (0x09, 0xFF), (0x0A, 0xFF), (0x0B, 0x7C), (0x0C, 0xFF),
    (0x31, 0xE1), (0x32, 0xE1), (0x33, 0x0C), (0x37, 0x00), (0x38, 0x22), (0x60, 0x82),
    (0x39, 0x45), (0x3A, 0x00), (0x3B, 0x00),
    (0x44, 0x31), (0x55, 0x44), (0x57, 0x01), (0x5A, 0x02),
)

# DSI page: the pixel clock generator (DDS). Its frequency word, FIFO full
# and empty thresholds, then timer and trend coefficients. 0x51 = 0x80 holds
# the DDS while it is written and 0x00 releases it.
_DDS_INIT = (
    (0x4E, 0x93), (0x4F, 0x3E), (0x50, 0x29), (0x51, 0x80), (0x1E, 0x4F),
    (0x1F, 0x5E), (0x20, 0x01), (0x21, 0x2C), (0x22, 0x01), (0x23, 0xFA),
    (0x24, 0x00), (0x25, 0xC8), (0x26, 0x00), (0x27, 0x5E), (0x28, 0x01),
    (0x29, 0x2C), (0x2A, 0x01), (0x2B, 0xFA), (0x2C, 0x00), (0x2D, 0xC8),
    (0x2E, 0x00), (0x42, 0x64), (0x43, 0x00), (0x44, 0x04), (0x45, 0x00),
    (0x46, 0x59), (0x47, 0x00), (0x48, 0xF2), (0x49, 0x06), (0x4A, 0x00),
    (0x4B, 0x72), (0x4C, 0x45), (0x4D, 0x00), (0x52, 0x08), (0x53, 0x00),
    (0x54, 0xB2), (0x55, 0x00), (0x56, 0xE4), (0x57, 0x0D), (0x58, 0x00),
    (0x59, 0xE4), (0x5A, 0x8A), (0x5B, 0x00), (0x5C, 0x34), (0x51, 0x00),
    (0x70, 0x00),  # the internal test pattern off
)

# The DDS frequency word per MHz of pixel clock, with the 25 MHz crystal.
_DDS_PER_MHZ = 0x16C16

# Main page: the LVDS PLL set to follow the pixel clock, the scaler off,
# then the LVDS output off so only HDMI/DVI is driven.
_LVDS_OFF = (
    (0x44, 0x30), (0x51, 0x05), (0x50, 0x24), (0x51, 0x2D), (0x52, 0x04),
    (0x69, 0x0E), (0x69, 0x8E), (0x6A, 0x00), (0x6C, 0xB8), (0x6B, 0x51),
    (0x04, 0xFB), (0x04, 0xFF), (0x7F, 0x00), (0xA8, 0x13), (0x44, 0x31),
)

# HDMI page: audio capture, clock regeneration, I2S input and audio packets off.
_AUDIO_OFF = ((0x06, 0x00), (0x07, 0x00), (0x34, 0x52), (0x3C, 0x40))

# Main page: every clock gate and block reset off, then on. Used when no
# reset pin is wired, to start from a known state.
_CLOCKS_OFF = ((0x02, 0x00), (0x08, 0x00), (0x09, 0x00), (0x0A, 0x00), (0x0B, 0x00), (0x0C, 0x00), (0x03, 0x00), (0x05, 0x00))
_CLOCKS_ON = ((0x02, 0xF7), (0x08, 0xFF), (0x09, 0xFF), (0x0A, 0xFF), (0x0B, 0x7C), (0x0C, 0xFF), (0x03, 0xFF), (0x05, 0xFF))

_TX_OFF = 0x0C
_TX_ON = 0x0E


class Mode:
    """One video timing: what the DSI host sends and the bridge regenerates.

    Args:
        name (str): A label, such as ``"1280x720p60"``.
        pixel_clock (int): Hz.
        width (int): Active pixels per line.
        hfp (int): Horizontal front porch, pixels.
        hsync (int): Horizontal sync width, 1 to 255 pixels.
        hbp (int): Horizontal back porch, pixels.
        height (int): Active lines.
        vfp (int): Vertical front porch, lines.
        vsync (int): Vertical sync width, 1 to 255 lines.
        vbp (int): Vertical back porch, lines.
        hsync_positive (bool): Sync polarity on the HDMI side.
        vsync_positive (bool): Sync polarity on the HDMI side.
        vic (int): The CEA-861 video code to announce, 0 for none.
        aspect_ratio (int): Picture aspect in the AVI infoframe: 0 none,
            1 4:3, 2 16:9.
    """

    def __init__(self, name, pixel_clock, width, hfp, hsync, hbp, height, vfp, vsync, vbp,
                 hsync_positive, vsync_positive, vic=0, aspect_ratio=0):
        self.name = name
        self.pixel_clock = pixel_clock
        self.width = width
        self.hfp = hfp
        self.hsync = hsync
        self.hbp = hbp
        self.height = height
        self.vfp = vfp
        self.vsync = vsync
        self.vbp = vbp
        self.hsync_positive = hsync_positive
        self.vsync_positive = vsync_positive
        self.vic = vic
        self.aspect_ratio = aspect_ratio

    @property
    def htotal(self):
        return self.width + self.hfp + self.hsync + self.hbp

    @property
    def vtotal(self):
        return self.height + self.vfp + self.vsync + self.vbp

    @property
    def refresh(self):
        """Frames per second."""
        return self.pixel_clock / (self.htotal * self.vtotal)

    def lane_rate(self, lanes):
        """The bit rate each DSI lane needs for this mode in RGB888, in Hz,
        rounded up to a whole Mbps, because ``mipidsi.Bus`` takes whole Mbps."""
        bits = self.pixel_clock * _BITS_PER_PIXEL
        rate = (bits + lanes - 1) // lanes
        return (rate + 999_999) // 1_000_000 * 1_000_000

    def timing(self):
        """The timing keyword arguments `LT8912B` takes, for ``LT8912B(bus, i2c, **mode.timing())``."""
        return {
            "width": self.width,
            "height": self.height,
            "hsync_pulse_width": self.hsync,
            "hsync_back_porch": self.hbp,
            "hsync_front_porch": self.hfp,
            "vsync_pulse_width": self.vsync,
            "vsync_back_porch": self.vbp,
            "vsync_front_porch": self.vfp,
            "pixel_clock_frequency": self.pixel_clock,
            "hsync_positive": self.hsync_positive,
            "vsync_positive": self.vsync_positive,
            "vic": self.vic,
            "aspect_ratio": self.aspect_ratio,
        }

    def __repr__(self):
        return "<Mode %s %dx%d %.3f MHz %.2f Hz>" % (
            self.name, self.width, self.height, self.pixel_clock / 1e6, self.refresh)


# The standard modes, as CEA-861 and VESA DMT define them. An ESP32-P4 can't
# make most of these pixel clocks: pass a mode through `fit` first.
MODES = {
    "640x480p60": Mode("640x480p60", 25_175_000, 640, 16, 96, 48, 480, 10, 2, 33, False, False, vic=1, aspect_ratio=1),
    "800x600p60": Mode("800x600p60", 40_000_000, 800, 40, 128, 88, 600, 1, 4, 23, True, True, aspect_ratio=1),
    "1024x768p60": Mode("1024x768p60", 65_000_000, 1024, 24, 136, 160, 768, 3, 6, 29, False, False, aspect_ratio=1),
    "1280x720p60": Mode("1280x720p60", 74_250_000, 1280, 110, 40, 220, 720, 5, 5, 20, True, True, vic=4, aspect_ratio=2),
    "1920x1080p30": Mode("1920x1080p30", 74_250_000, 1920, 88, 44, 148, 1080, 4, 5, 36, True, True, vic=34, aspect_ratio=2),
    "1920x1080p60": Mode("1920x1080p60", 148_500_000, 1920, 88, 44, 148, 1080, 4, 5, 36, True, True, vic=16, aspect_ratio=2),
}


def fit(mode, host_clock=P4_HOST_CLOCK, vic=0):
    """Return the nearest mode a host that divides ``host_clock`` can send.

    The host's pixel clock is ``host_clock`` divided by a whole number. This
    takes the largest divider whose clock is at least the mode's, then
    widens the horizontal front porch so the line and frame rates stay as
    close to the standard as whole pixels allow. A monitor measures those
    rates, not the pixel clock, so it sees the mode it expects. When the
    timing changes, the video code becomes ``vic``: 0 by default, because
    the mode is no longer the CEA one. Some sinks handle a padded mode
    better when it announces the standard code; pass that code to try it.

    Args:
        mode (Mode): The mode wanted.
        host_clock (int): The host's DPI clock source in Hz, or None when the
            host can make any pixel clock.
        vic (int): The video code a padded mode announces. A mode the host
            makes exactly keeps its own.

    Returns:
        Mode: The mode to send, with the pixel clock the host really makes.

    Raises:
        ValueError: If the host can't make a clock that fast, or can't ask
            for the clock it would use.
    """
    if host_clock is None:
        return mode
    divider = host_clock // mode.pixel_clock
    if divider < 1:
        raise ValueError("%s needs %d Hz, more than the host's %d Hz source" % (
            mode.name, mode.pixel_clock, host_clock))
    real = host_clock // divider
    if real == mode.pixel_clock:
        return mode
    if real > MAX_PIXEL_CLOCK:
        raise ValueError("%s at %.2f MHz: the host's nearest clock at or above it is %.2f MHz "
                         "(%d MHz / %d), over the bridge's %d MHz" % (
                             mode.name, mode.pixel_clock / 1e6, real / 1e6, host_clock // 1_000_000,
                             divider, MAX_PIXEL_CLOCK // 1_000_000))
    # mipidsi passes the pixel clock to ESP-IDF in whole MHz, and ESP-IDF
    # rounds the divider: check that lands on the same divider.
    requested = real // 1_000_000 * 1_000_000
    if requested == 0 or (host_clock + requested // 2) // requested != divider:
        raise ValueError("%s: the host can't ask for %d Hz in whole MHz" % (mode.name, real))
    htotal = (real * mode.htotal + mode.pixel_clock // 2) // mode.pixel_clock
    extra = htotal - mode.htotal
    return Mode(mode.name, real, mode.width, mode.hfp + extra, mode.hsync, mode.hbp,
                mode.height, mode.vfp, mode.vsync, mode.vbp,
                mode.hsync_positive, mode.vsync_positive, vic=vic, aspect_ratio=mode.aspect_ratio)


def check(mode, lanes, lane_rate=None, max_lane_rate=MAX_LANE_RATE):
    """Raise ValueError, with the numbers, if the bridge can't take ``mode``.

    Args:
        mode (Mode): The timing to send.
        lanes (int): DSI data lanes, 1 to 4.
        lane_rate (int): The bit rate per lane the host runs at, in Hz, or
            None to use the least the mode needs.
        max_lane_rate (int): The host's limit per lane, in Hz.

    Returns:
        int: The lane rate to run at, in Hz.

    Raises:
        ValueError: If the mode or the lane rate is out of range.
    """
    if lanes not in (1, 2, 3, 4):
        raise ValueError("lanes must be 1 to 4, not %r" % (lanes,))
    if not 1 <= mode.hsync <= 255 or not 1 <= mode.vsync <= 255:
        raise ValueError("%s: sync widths must be 1 to 255, not %d and %d" % (
            mode.name, mode.hsync, mode.vsync))
    if mode.htotal > 0xFFFF or mode.vtotal > 0xFFFF:
        raise ValueError("%s: totals %dx%d don't fit 16 bits" % (mode.name, mode.htotal, mode.vtotal))
    if mode.pixel_clock > MAX_PIXEL_CLOCK:
        raise ValueError("%s: pixel clock %.2f MHz is over the bridge's %d MHz" % (
            mode.name, mode.pixel_clock / 1e6, MAX_PIXEL_CLOCK // 1_000_000))
    needed = mode.lane_rate(lanes)
    limit = min(max_lane_rate, MAX_LANE_RATE)
    if needed > limit:
        raise ValueError("%s needs %d Mbps a lane on %d lanes (%.3f MHz x 24 bits / %d), over the %d Mbps limit" % (
            mode.name, needed // 1_000_000, lanes, mode.pixel_clock / 1e6, lanes, limit // 1_000_000))
    if lane_rate is None:
        return max(needed, MIN_LANE_RATE)
    if lane_rate < needed:
        raise ValueError("%s needs %d Mbps a lane on %d lanes, and the bus runs at %d" % (
            mode.name, needed // 1_000_000, lanes, lane_rate // 1_000_000))
    if not MIN_LANE_RATE <= lane_rate <= limit:
        raise ValueError("lane rate %d Mbps is outside %d to %d" % (
            lane_rate // 1_000_000, MIN_LANE_RATE // 1_000_000, limit // 1_000_000))
    return lane_rate


def parse_edid(data):
    """Read the modes a monitor's EDID offers.

    Takes the base block and, if present, a CEA extension block. Returns the
    detailed timings in the order the EDID lists them (the first is the
    monitor's preferred mode), then the `MODES` entries it names by
    established timing or CEA video code.

    Args:
        data (bytes): 128 or 256 bytes read from address 0x50.

    Returns:
        list: `Mode` objects, preferred first.

    Raises:
        ValueError: If the header or a checksum is wrong.
    """
    if len(data) < 128 or bytes(data[:8]) != b"\x00\xff\xff\xff\xff\xff\xff\x00":
        raise ValueError("not an EDID: the header is wrong")
    if sum(data[:128]) & 0xFF:
        raise ValueError("EDID base block checksum is wrong")
    modes = []
    for offset in (54, 72, 90, 108):
        mode = _detailed_timing(data, offset)
        if mode is not None:
            modes.append(mode)
    named = []
    # Established timings: byte 35 bit 5 is 640x480@60, bit 0 is 800x600@60;
    # byte 36 bit 3 is 1024x768@60.
    if data[35] & 0x20:
        named.append("640x480p60")
    if data[35] & 0x01:
        named.append("800x600p60")
    if data[36] & 0x08:
        named.append("1024x768p60")
    if len(data) >= 256 and data[126] and data[128] == 0x02:
        block = data[128:256]
        if sum(block) & 0xFF:
            raise ValueError("EDID extension checksum is wrong")
        dtd_start = block[2]
        index = 4
        while index < dtd_start:
            tag = block[index] >> 5
            length = block[index] & 0x1F
            if tag == 2:  # video data block: one VIC per byte
                for code in block[index + 1:index + 1 + length]:
                    for name, standard in MODES.items():
                        if standard.vic == code & 0x7F and name not in named:
                            named.append(name)
            index += 1 + length
        if dtd_start:
            offset = dtd_start
            while offset + 18 <= 127:
                mode = _detailed_timing(block, offset)
                if mode is None:
                    break
                modes.append(mode)
                offset += 18
    for name in named:
        modes.append(MODES[name])
    return modes


def _detailed_timing(data, offset):
    d = data[offset:offset + 18]
    clock = (d[0] | d[1] << 8) * 10_000
    if clock == 0:
        return None  # a display descriptor, not a timing
    width = d[2] | (d[4] >> 4) << 8
    hblank = d[3] | (d[4] & 0x0F) << 8
    height = d[5] | (d[7] >> 4) << 8
    vblank = d[6] | (d[7] & 0x0F) << 8
    hfp = d[8] | (d[11] >> 6) << 8
    hsync = d[9] | ((d[11] >> 4) & 0x03) << 8
    vfp = d[10] >> 4 | ((d[11] >> 2) & 0x03) << 4
    vsync = (d[10] & 0x0F) | (d[11] & 0x03) << 4
    flags = d[17]
    if flags & 0x80:
        return None  # interlaced: the bridge sends progressive video only
    # Digital separate sync carries both polarities; anything else counts as negative.
    separate = (flags & 0x18) == 0x18
    return Mode("%dx%d" % (width, height), clock, width, hfp, hsync, hblank - hfp - hsync,
                height, vfp, vsync, vblank - vfp - vsync,
                separate and bool(flags & 0x02), separate and bool(flags & 0x04))


def best_mode(modes, lanes, host_clock=P4_HOST_CLOCK, max_lane_rate=MAX_LANE_RATE):
    """Pick the largest of ``modes`` the host and the bridge can carry.

    Each mode goes through `check` as it stands, then `fit`, then `check`
    again. Among those that pass, the most
    pixels wins, then the higher refresh rate.

    Args:
        modes (list): `Mode` objects, such as `parse_edid` returns.
        lanes (int): DSI data lanes, 1 to 4.
        host_clock (int): As for `fit`.
        max_lane_rate (int): The host's limit per lane, in Hz.

    Returns:
        Mode: The fitted mode.

    Raises:
        ValueError: If none fits, listing why each was refused.
    """
    best = None
    refused = []
    for mode in modes:
        try:
            check(mode, lanes, max_lane_rate=max_lane_rate)
            fitted = fit(mode, host_clock)
            check(fitted, lanes, max_lane_rate=max_lane_rate)
        except ValueError as exc:
            refused.append(str(exc))
            continue
        if best is None or (fitted.width * fitted.height, fitted.refresh) > (best.width * best.height, best.refresh):
            best = fitted
    if best is None:
        raise ValueError("no mode fits: " + "; ".join(refused))
    return best


class Audio:
    """HDMI audio from I2S, for `LT8912B` or `Bridge.start`. Experimental.

    No public source documents this chip's I2S audio registers, so there
    are three recipes, most likely first. Each writes the HDMI page (0x4A),
    and starting the bridge with it puts the bridge in HDMI mode for it.

    ``"a"`` is the set a 2025 Linux patch for this chip used, tested with
    monitors on an i.MX8M Mini: channel status 0x0F, the N value at 0x35 to
    0x37, then 0x34 = 0xE2, 0x3C = 0x60, 0x07 = 0xF0, 0x06 = 0x08.

    ``"b"`` is Lontium's reference set, as Espressif's component and a
    vendor kernel ship it: 0x3C = 0x41, 0x06 = 0x08, 0x07 = 0xF0,
    0x34 = 0xD2, 0x0F = channel status. No N value.

    ``"c"`` is ``"a"`` with 0x34 = 0xD2, both packet bits in 0x3C (0x61),
    and an audio infoframe at 0xB2 enabled by bit 1 of 0x3D. The sister
    chip LT9611 keeps its audio infoframe there; that the LT8912B does too
    is a guess.

    The bridge has no MCLK input: send standard I2S (bit clock, word select
    and data) only.

    Args:
        rate (int): Sample rate in Hz: 32000, 44100, 48000, 88200, 96000,
            176400 or 192000.
        bits (int): Bits per sample on the wire: 16, 24, or 32 (a 32-bit
            slot holding 24 bits, announced as 24).
        recipe (str): ``"a"``, ``"b"`` or ``"c"``.

    Raises:
        ValueError: If a value isn't one of those.
    """

    # IEC 60958 channel status sampling frequency codes.
    RATE_CODES = {32000: 0x3, 44100: 0x0, 48000: 0x2, 88200: 0x8, 96000: 0xA, 176400: 0xC, 192000: 0xE}
    # IEC 60958 word length codes; 0xB is 24 bits.
    WORD_CODES = {16: 0x2, 24: 0xB, 32: 0xB}
    # HDMI recommended N for each rate; the chip measures CTS itself.
    N_VALUES = {32000: 4096, 44100: 6272, 48000: 6144, 88200: 12544, 96000: 12288, 176400: 25088, 192000: 24576}

    def __init__(self, rate=48000, bits=16, recipe="a"):
        if rate not in self.RATE_CODES:
            raise ValueError("rate must be one of %s, not %r" % (sorted(self.RATE_CODES), rate))
        if bits not in self.WORD_CODES:
            raise ValueError("bits must be 16, 24 or 32, not %r" % (bits,))
        if recipe not in ("a", "b", "c"):
            raise ValueError("recipe is 'a', 'b' or 'c', not %r" % (recipe,))
        self.rate = rate
        self.bits = bits
        self.recipe = recipe

    @property
    def channel_status(self):
        """The 0x0F byte: sampling frequency code high, word length code low."""
        return self.RATE_CODES[self.rate] << 4 | self.WORD_CODES[self.bits]

    def registers(self):
        """The (register, value) writes to the HDMI page, in order."""
        if self.recipe == "b":
            return ((0x3C, 0x41), (0x06, 0x08), (0x07, 0xF0), (0x34, 0xD2), (0x0F, self.channel_status))
        n = self.N_VALUES[self.rate]
        first = ((0x0F, self.channel_status), (0x35, n >> 16), (0x36, (n >> 8) & 0xFF), (0x37, n & 0xFF))
        if self.recipe == "a":
            return first + ((0x34, 0xE2), (0x3C, 0x60), (0x07, 0xF0), (0x06, 0x08))
        # Audio infoframe: type 0x84, version 1, length 10, the checksum,
        # then PB1 = 0x01 for two channels.
        frame = [0x84, 0x01, 0x0A, 0x00, 0x01] + [0] * 9
        frame[3] = -sum(frame) & 0xFF
        infoframe = tuple((0xB2 + index, value) for index, value in enumerate(frame))
        return first + ((0x34, 0xD2), (0x3C, 0x61), (0x07, 0xF0), (0x06, 0x08)) + infoframe

    def __repr__(self):
        return "<Audio %d Hz %d-bit recipe %s>" % (self.rate, self.bits, self.recipe)


def read_edid(i2c):
    """Read the monitor's EDID from 0x50: 128 bytes, or 256 with an extension.

    The DDC lines must reach this bus: on Adafruit's board, the DDC switch
    on. Read it before making the `LT8912B`, which needs the timing, and
    pass the result to `parse_edid`.

    Args:
        i2c: A bus with ``readfrom_mem``, such as ``machine.I2C``.

    Raises:
        OSError: If nothing answers at 0x50, with what to check.
    """
    try:
        data = bytes(i2c.readfrom_mem(EDID, 0x00, 128))
        if data[126]:
            data += bytes(i2c.readfrom_mem(EDID, 0x80, 128))
    except OSError as exc:
        raise OSError("no EDID at 0x50: is a monitor plugged in and on, and is the "
                      "board's DDC switch on? (%s)" % (exc,))
    return data


class Bridge:
    """The LT8912B's I2C side alone, with no DSI video.

    `LT8912B` uses one of these to set the bridge up. On its own, it shows
    the bridge's test pattern, reads its status and finds clashes on the
    bus, which proves the wiring and the monitor before any video runs.

    Args:
        i2c: A bus with ``writeto_mem``, ``readfrom_mem`` and ``scan``, such
            as ``machine.I2C``.
        lanes (int): DSI data lanes wired to the bridge, 1 to 4.
        reset: The ``machine.Pin`` wired to the bridge's active-low reset, or
            None if it isn't wired. It is made an output, held high. Without
            it, `start` cycles the bridge's clocks instead, which recovers
            less.
        hpd: The ``machine.Pin`` wired to the board's hot-plug output, low
            while a monitor is connected on Adafruit's board, or None to
            read the bridge's own status register. It is made an input.
        settle (int): The DSI receiver's settle count, register 0x11 of the
            DSI page. Espressif and Adafruit use 0x10.
        lane_swap (bool): Reverse the data lanes (DSI page 0x15).
        pn_swap (bool): Swap the polarity of every lane (main page 0x3E).

    Raises:
        ValueError: If ``lanes`` is out of range.
    """

    def __init__(self, i2c, *, lanes=2, reset=None, hpd=None, settle=0x10, lane_swap=False, pn_swap=False):
        if lanes not in (1, 2, 3, 4):
            raise ValueError("lanes must be 1 to 4, not %r" % (lanes,))
        self._i2c = i2c
        self._lanes = lanes
        self._reset = reset
        self._hpd = hpd
        self._settle = settle
        self._lane_swap = lane_swap
        self._pn_swap = pn_swap
        self._mode = None
        if reset is not None:
            reset.init(reset.OUT, value=1)
        if hpd is not None:
            hpd.init(hpd.IN)

    @property
    def mode(self):
        """The `Mode` the last `start` set up, or None."""
        return self._mode

    # -- I2C ----------------------------------------------------------------

    def _write(self, address, register, value):
        self._i2c.writeto_mem(address, register, bytes((value & 0xFF,)))

    def _write_all(self, address, pairs):
        for register, value in pairs:
            self._write(address, register, value)

    def _read(self, address, register, count=1):
        return self._i2c.readfrom_mem(address, register, count)

    # -- Finding the bridge and the monitor ---------------------------------

    def chip_id(self):
        """Read main page 0x00 and 0x01: ``b"\\x12\\xb2"`` on an LT8912B.

        Raises:
            OSError: If nothing answers at 0x48, with what to check.
        """
        try:
            return bytes(self._read(MAIN, 0x00, 2))
        except OSError as exc:
            raise OSError("no answer at 0x48: check the bridge's power, the I2C wiring, "
                          "and that its reset isn't held low (%s)" % (exc,))

    def detect(self):
        """Check all three addresses answer and the chip ID is an LT8912B.

        Returns:
            bytes: The chip ID.

        Raises:
            OSError: If an address is missing or the ID is wrong. A wrong ID
                usually means another device answers at 0x48, such as a
                monitor's controller reached over DDC: turn the board's DDC
                switch off.
        """
        found = set(self._i2c.scan())
        missing = [address for address in (MAIN, DSI, AVI) if address not in found]
        if missing:
            raise OSError("bridge addresses missing from the I2C scan: %s (found %s)" % (
                ", ".join("0x%02X" % a for a in missing), ", ".join("0x%02X" % a for a in sorted(found))))
        ident = self.chip_id()
        if ident != CHIP_ID:
            raise OSError("chip ID at 0x48 is %02X %02X, not 12 B2: another device answers there. "
                          "If a monitor is plugged in, turn the DDC switch off and try again" % (ident[0], ident[1]))
        return ident

    def hold_reset(self, held=True):
        """Hold the bridge in reset, or let it go.

        Raises:
            RuntimeError: If no reset pin was given.
        """
        if self._reset is None:
            raise RuntimeError("no reset pin was given")
        self._reset.value(0 if held else 1)
        time.sleep(0.01)

    def clashes(self):
        """List addresses that answer while the bridge is held in reset.

        Something answering at 0x48 to 0x4B then is another device on the
        bus, usually a monitor's controller reached over DDC, and it will
        take the bridge's writes. Needs the reset pin.

        Returns:
            list: The clashing addresses, empty when there are none.
        """
        self.hold_reset(True)
        try:
            found = self._i2c.scan()
        finally:
            self.hold_reset(False)
        return [address for address in (MAIN, DSI, AVI, 0x4B) if address in found]

    @property
    def hot_plug_detected(self):
        """True when a monitor asserts hot-plug detect.

        Reads the HPD pin if one was given, otherwise bit 7 of main page 0xC1.
        """
        if self._hpd is not None:
            return not self._hpd.value()
        return bool(self._read(MAIN, 0xC1)[0] & 0x80)

    # -- Video --------------------------------------------------------------

    def start(self, mode, *, lane_rate=None, hdmi=None, audio=None):
        """Reset the bridge and set it up for ``mode``, ready for DSI video.

        Call this before the host starts DSI video, then `sync` once it runs.

        Args:
            mode (Mode): The timing the host will send, from `fit`.
            lane_rate (int): The host's bit rate per lane in Hz, to check, or
                None to check only that the mode fits.
            hdmi (bool): True for HDMI, False for DVI. None picks HDMI when
                ``audio`` is given, otherwise DVI.
            audio (Audio): HDMI audio from I2S, or None for none.

        Raises:
            ValueError: If the mode doesn't fit, or audio is asked for on DVI.
        """
        check(mode, self._lanes, lane_rate)
        if hdmi is None:
            hdmi = audio is not None
        if audio is not None and not hdmi:
            raise ValueError("audio needs HDMI: a DVI monitor takes no audio")
        self._mode = mode
        self._chip_reset()
        self._write(MAIN, 0x33, _TX_OFF)
        self._write_all(MAIN, _MAIN_INIT)
        self._write_all(MAIN, ((0x3E, 0xF6 if self._pn_swap else 0xD6), (0x3F, 0xD4), (0x41, 0x3C)))
        self._write_all(DSI, (
            (0x10, 0x01),  # termination on
            (0x11, self._settle),
            (0x13, self._lanes % 4),  # 0 means four lanes
            (0x14, 0x00),
            (0x15, 0xA8 if self._lane_swap else 0x00),
            (0x1A, 0x03),
            (0x1B, 0x03),
        ))
        self._write_all(DSI, _DDS_INIT)
        self._seed_dds(mode.pixel_clock)
        self._write_all(DSI, self._timing(mode))
        self._write(MAIN, 0xAB, (0x02 if mode.hsync_positive else 0) | (0x01 if mode.vsync_positive else 0))
        self._write_all(AVI, self._avi_infoframe(mode))
        self._receiver_reset()
        self._write_all(MAIN, _LVDS_OFF)
        if audio is None:
            self._write_all(AVI, _AUDIO_OFF)
        else:
            self._write_audio(audio)
        self._write(MAIN, 0xB2, 0x01 if hdmi else 0x00)
        self._write(MAIN, 0x33, _TX_ON)

    def sync(self, pixel_clock=None):
        """Lock the bridge to DSI video that is now running.

        Seeds the pixel clock generator, then resets the DSI receiver and
        the generator, so they lock to the live stream.

        Args:
            pixel_clock (int): The clock the host really sends, in Hz, or
                None for the mode's.

        Raises:
            RuntimeError: If `start` hasn't run.
        """
        if self._mode is None:
            raise RuntimeError("call start() first")
        self._seed_dds(pixel_clock or self._mode.pixel_clock)
        self._receiver_reset()

    def output(self, on):
        """Turn the HDMI/DVI transmitter on or off, leaving the bridge set up."""
        self._write(MAIN, 0x33, _TX_ON if on else _TX_OFF)

    def test_pattern(self, mode=None):
        """Show the bridge's own colour bars, with no DSI video needed.

        The bridge makes the timing and clock itself, so this proves the
        I2C setup, the HDMI side and the monitor before DSI is involved.
        Call `start` first; calling it again clears the pattern.

        Args:
            mode (Mode): The timing to make, or None for the one `start` set.

        Raises:
            RuntimeError: If `start` hasn't run.
            ValueError: If the timing is too big for the pattern's registers.
        """
        if self._mode is None:
            raise RuntimeError("call start() first")
        mode = mode or self._mode
        if mode.htotal > 0xFFF or mode.vtotal > 0x7FF or mode.vsync > 63 or mode.vsync + mode.vbp > 127:
            raise ValueError("%s: the test pattern takes totals up to 4095x2047, vsync up to 63 "
                             "and vsync + back porch up to 127" % mode.name)
        de_delay = mode.hsync + mode.hbp
        self._write_all(DSI, (
            (0x72, 0x12),
            (0x73, de_delay & 0xFF),
            (0x74, de_delay >> 8),
            (0x75, (mode.vsync + mode.vbp) & 0xFF),
            (0x76, mode.width & 0xFF),
            (0x77, mode.height & 0xFF),
            (0x78, (mode.height >> 8) << 4 | mode.width >> 8),
            (0x79, mode.htotal & 0xFF),
            (0x7A, mode.vtotal & 0xFF),
            (0x7B, (mode.vtotal >> 8) << 4 | mode.htotal >> 8),
            (0x7C, mode.hsync & 0xFF),
            (0x7D, (mode.hsync >> 8) << 6 | mode.vsync),
            (0x70, 0x80),  # pattern on
            (0x71, 0x51),
            (0x42, 0x12),
            (0x1E, 0x67),
        ))
        word = _dds_word(mode.pixel_clock)
        self._write_all(DSI, ((0x4E, word & 0xFF), (0x4F, (word >> 8) & 0xFF), (0x50, word >> 16), (0x51, 0x80)))

    def status(self):
        """What the bridge thinks it is receiving: the best bench diagnostic.

        Returns:
            dict: ``hpd`` (a monitor is there), ``hsync`` and ``vsync`` (the
            counts the bridge measures from the DSI input, main page 0x9C to
            0x9F; 0xFFFF means no video arrives), ``video`` (hsync isn't
            0xFFFF) and ``dds`` (DSI page 0x0C to 0x0F, the pixel clock
            generator's state, low byte first).
        """
        sync = self._read(MAIN, 0x9C, 4)
        dds = self._read(DSI, 0x0C, 4)
        hsync = sync[0] | sync[1] << 8
        return {
            "hpd": bool(self._read(MAIN, 0xC1)[0] & 0x80),
            "hsync": hsync,
            "vsync": sync[2] | sync[3] << 8,
            "video": hsync != 0xFFFF,
            "dds": dds[0] | dds[1] << 8 | dds[2] << 16 | dds[3] << 24,
        }

    def deinit(self):
        """Turn the transmitter off and let go of the reset pin.

        The reset pin becomes an input again, and the board's pull-up keeps
        the bridge running with its setup.
        """
        self.output(False)
        self._mode = None
        if self._reset is not None:
            self._reset.init(self._reset.IN)
            self._reset = None

    # -- Internals ----------------------------------------------------------

    def _chip_reset(self):
        if self._reset is not None:
            self._reset.value(0)
            time.sleep(0.01)
            self._reset.value(1)
            time.sleep(0.01)
            return
        self._write_all(MAIN, _CLOCKS_OFF)
        time.sleep(0.02)
        self._write_all(MAIN, _CLOCKS_ON)
        time.sleep(0.02)

    def _receiver_reset(self):
        self._write(MAIN, 0x03, 0x7F)
        time.sleep(0.01)
        self._write(MAIN, 0x03, 0xFF)
        self._write(MAIN, 0x05, 0xFB)
        time.sleep(0.01)
        self._write(MAIN, 0x05, 0xFF)

    def _seed_dds(self, pixel_clock):
        word = _dds_word(pixel_clock)
        self._write_all(DSI, ((0x51, 0x80), (0x4E, word & 0xFF), (0x4F, (word >> 8) & 0xFF),
                              (0x50, (word >> 16) & 0xFF), (0x51, 0x00)))

    @staticmethod
    def _timing(mode):
        pairs = [
            (0x18, mode.hsync),
            (0x19, mode.vsync),
            (0x1C, mode.width & 0xFF),
            (0x1D, mode.width >> 8),
            (0x2F, 0x0C),  # FIFO length
        ]
        for register, value in ((0x34, mode.htotal), (0x36, mode.vtotal), (0x38, mode.vbp),
                                (0x3A, mode.vfp), (0x3C, mode.hbp), (0x3E, mode.hfp)):
            pairs.append((register, value & 0xFF))
            pairs.append((register + 1, value >> 8))
        return pairs

    @staticmethod
    def _avi_infoframe(mode):
        # PB0 is the checksum over the 82 02 0D header and PB1 to PB13.
        # PB1 = 0x10: RGB with active format information. PB2: picture
        # aspect in bits 5-4, active format "same as picture". PB4: the VIC.
        pb2 = mode.aspect_ratio << 4 | 0x08
        payload = [0, 0x10, pb2, 0, mode.vic] + [0] * 9
        payload[0] = (0x100 - 0x82 - 0x02 - 0x0D - pb2 - 0x10 - mode.vic) & 0xFF
        return [(0x43 + index, value) for index, value in enumerate(payload)]

    def _write_audio(self, audio):
        self._write_all(AVI, audio.registers())
        if audio.recipe == "c":
            # Bit 1 of 0x3D sends the audio infoframe on the LT9611.
            self._write(AVI, 0x3D, self._read(AVI, 0x3D)[0] | 0x02)


def _dds_word(pixel_clock):
    return pixel_clock * _DDS_PER_MHZ // 1_000_000


# The bus treats rates within 1 kHz of what is asked as meeting it.
_BUS_FREQUENCY_TOLERANCE = 1_000


def _color_options(color_depth, output_color_depth):
    """The ``mipidsi.Display`` colour arguments for the bridge's RGB888 input."""
    if color_depth == 16:
        if output_color_depth not in (None, 24):
            raise ValueError("the LT8912B takes RGB888: output_color_depth must be 24, not %r"
                             % (output_color_depth,))
        return {"color_depth": 16, "output_color_depth": 24}
    if color_depth == 24:
        if output_color_depth not in (None, 24):
            raise ValueError("an RGB888 framebuffer is RGB888 on the wire: leave output_color_depth out")
        options = {"color_depth": 24}
        if output_color_depth is not None:
            options["output_color_depth"] = 24
        return options
    raise ValueError("color_depth must be 16 (an RGB565 framebuffer sent as RGB888) or 24, not %r"
                     % (color_depth,))


if _Display is None:

    class LT8912B:
        """Needs ``mipidsi``, which this firmware doesn't have: use `Bridge` for the I2C side."""

        def __init__(self, *args, **kwargs):
            raise NotImplementedError("LT8912B is a mipidsi.Display, and this firmware has no mipidsi. "
                                      "Bridge drives the I2C side alone, with its test pattern")

else:

    class LT8912B(_Display):
        """An HDMI or DVI display: a ``mipidsi.Display`` that sets up an LT8912B first.

        The same constructor, properties and order of work as Adafruit's
        CircuitPython ``adafruit_lt8912b.LT8912B``: it resets the bridge and
        configures it for the timing over I2C, starts DSI video, checks the
        bus is fast enough for the pixel clock, then locks the bridge to the
        video. Draw into it as into any ``mipidsi.Display``, through
        displaydev's ``FBDisplay`` for example.

        The framebuffer is RGB565 and the DSI host sends it as RGB888, which
        is all the bridge takes, with the lanes kept in high speed through
        blanking. Pass ``color_depth=24`` for an RGB888 framebuffer, as with
        Adafruit's driver.

        The arguments after ``aspect_ratio`` are this driver's own. On an
        ESP32-P4 the pixel clock must be one the host makes exactly: `fit`
        gives one.

        Args:
            bus (mipidsi.Bus): The DSI bus the bridge is on. Make it with a
                ``minimum_frequency`` that carries 24 bits a pixel across its
                lanes, which `check` gives. The bus runs at the first rate its
                PHY makes that is at least that, and the bridge is checked
                against the rate it reports.
            i2c: The I2C bus the bridge is on, such as ``machine.I2C``.
            width (int): Active pixels per line.
            height (int): Active lines.
            hsync_pulse_width (int): Horizontal sync width, 1 to 255 pixels.
            hsync_back_porch (int): Horizontal back porch, pixels.
            hsync_front_porch (int): Horizontal front porch, pixels.
            vsync_pulse_width (int): Vertical sync width, 1 to 255 lines.
            vsync_back_porch (int): Vertical back porch, lines.
            vsync_front_porch (int): Vertical front porch, lines.
            pixel_clock_frequency (int): Pixel clock in Hz.
            reset: The ``machine.Pin`` wired to the bridge's active-low
                reset, or None.
            hsync_positive (bool): True for positive horizontal sync.
            vsync_positive (bool): True for positive vertical sync.
            vic (int): AVI video code, 0 to 127; 0 for a timing with no
                standard code.
            aspect_ratio (int): AVI picture aspect: 0 none, 1 4:3, 2 16:9.
            hpd: The ``machine.Pin`` wired to the hot-plug output, or None to
                read the bridge's status register.
            hdmi (bool): True for HDMI, False for DVI. None picks HDMI when
                ``audio`` is given, otherwise DVI.
            audio (Audio): HDMI audio from I2S. Experimental.
            settle (int): As for `Bridge`.
            lane_swap (bool): As for `Bridge`.
            pn_swap (bool): As for `Bridge`.
            **kwargs: Other ``mipidsi.Display`` arguments, such as
                ``non_burst``.

        Raises:
            ValueError: If an argument is out of range, or the bus is too slow
                for the pixel clock.
            OSError: If the bridge doesn't answer on I2C, or another device
                answers at its address.
        """

        def __init__(self, bus, i2c, *, width, height, hsync_pulse_width, hsync_back_porch,
                     hsync_front_porch, vsync_pulse_width, vsync_back_porch, vsync_front_porch,
                     pixel_clock_frequency, reset=None, hsync_positive=False, vsync_positive=False,
                     vic=0, aspect_ratio=0, hpd=None, hdmi=None,
                     audio=None, settle=0x10, lane_swap=False, pn_swap=False, **kwargs):
            h_total = width + hsync_front_porch + hsync_pulse_width + hsync_back_porch
            v_total = height + vsync_front_porch + vsync_pulse_width + vsync_back_porch
            if h_total > 0xFFFF or v_total > 0xFFFF:
                raise ValueError("horizontal or vertical total does not fit in 16 bits")
            if not 1 <= hsync_pulse_width <= 255:
                raise ValueError("hsync_pulse_width must be between 1 and 255")
            if not 1 <= vsync_pulse_width <= 255:
                raise ValueError("vsync_pulse_width must be between 1 and 255")
            if not 0 <= vic <= 127:
                raise ValueError("vic must be between 0 and 127")
            if not 0 <= aspect_ratio <= 2:
                raise ValueError("aspect_ratio must be 0, 1, or 2")
            color_depth = kwargs.pop("color_depth", 16)
            colors = _color_options(color_depth, kwargs.pop("output_color_depth", None))
            kwargs.update(colors)
            lanes = bus.num_lanes
            rate = bus.frequency
            mode = Mode("%dx%d" % (width, height), pixel_clock_frequency, width, hsync_front_porch,
                        hsync_pulse_width, hsync_back_porch, height, vsync_front_porch,
                        vsync_pulse_width, vsync_back_porch, hsync_positive, vsync_positive,
                        vic=vic, aspect_ratio=aspect_ratio)
            # Refuse a mode the lanes can't carry before touching the chip.
            check(mode, lanes, rate)

            # Configure the bridge before starting DSI video.
            self.bridge = Bridge(i2c, lanes=lanes, reset=reset, hpd=hpd, settle=settle,
                                 lane_swap=lane_swap, pn_swap=pn_swap)
            self.bridge.detect()
            self.bridge.start(mode, hdmi=hdmi, audio=audio)

            # Start DSI video only now. The lanes stay in high speed, so the
            # bridge's receiver must be ready for the one start of transmission.
            super().__init__(
                bus,
                b"",
                width=width,
                height=height,
                hsync_pulse_width=hsync_pulse_width,
                hsync_back_porch=hsync_back_porch,
                hsync_front_porch=hsync_front_porch,
                vsync_pulse_width=vsync_pulse_width,
                vsync_back_porch=vsync_back_porch,
                vsync_front_porch=vsync_front_porch,
                pixel_clock_frequency=pixel_clock_frequency,
                # The bridge regenerates the pixel clock from the DSI clock
                # and loses lock if the lanes drop to low power in blanking.
                low_power_blanking=False,
                **kwargs,
            )

            # Check the rate against the clock the host really makes.
            real_clock = self.pixel_clock_frequency
            needed = (real_clock * 24 + lanes - 1) // lanes
            if rate + _BUS_FREQUENCY_TOLERANCE < needed:
                self.deinit()
                raise ValueError("bus runs at %d, below the %d needed for this pixel clock" % (rate, needed))

            # Seed again from the real clock, now the bridge has video to track.
            self.bridge.sync(real_clock)

        @property
        def hot_plug_detected(self):
            """True when a monitor asserts hot-plug detect: see `Bridge.hot_plug_detected`."""
            return self.bridge.hot_plug_detected

        def status(self):
            """What the bridge measures from the DSI input: see `Bridge.status`."""
            return self.bridge.status()

        def deinit(self):
            """Stop the display, turn the transmitter off and release the reset pin."""
            self.bridge.deinit()
            super().deinit()
