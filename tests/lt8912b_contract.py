# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""The LT8912B bridge driver, checked write by write on a fake I2C bus.

The bus records every write as ``AARR=VV`` (7-bit address, register, value)
and answers reads from a register file. The checks are:

* `start` writes, in order, the tables Adafruit's and Espressif's drivers
  write, with this mode's timing, pixel clock word, sync polarity and AVI
  infoframe in their places, for every standard mode that fits two lanes;
* the timing fields are packed low byte first, spelled out by hand for 720p;
* modes the lanes or the bridge can't carry are refused with the numbers;
* with no audio, nothing but the four audio-off writes reaches the audio
  registers, and with audio each recipe writes its own set;
* a real monitor's EDID (a Dell E207WFP, from the linuxhw/EDID collection)
  parses to the timings edid-decode reports, and `best_mode` picks 720p;
* detection, hot-plug, the test pattern, `sync`, `status` and the options;
* `LT8912B`, as a subclass of a fake ``mipidsi.Display``, takes Adafruit's
  constructor, sets the bridge up before the DSI video starts and locks it
  after, asks for RGB888 on the wire, and refuses what it can't do before
  touching the chip.

None of this shows a monitor agrees: it shows the driver writes the registers
those sources write.

A plain script, so it runs on CPython and on MicroPython::

    python tests/lt8912b_contract.py
    micropython tests/lt8912b_contract.py
    python tests/lt8912b_contract.py --plant=hfp-hbp   # must FAIL
"""

import sys
from binascii import unhexlify

try:
    _here = __file__
except NameError:  # pragma: no cover
    _here = sys.argv[0]
_sep = "\\" if "\\" in _here else "/"
_dir = _here.rsplit(_sep, 1)[0] if _sep in _here else "."
sys.path.insert(0, _dir + _sep + ".." + _sep + "drivers" + _sep + "display")


class FakeDisplay:
    """``mipidsi.Display`` as far as `LT8912B` sees it."""

    log = None  # the I2C write list, so video starting shows among the writes
    report_clock = None  # a pixel_clock_frequency to report, or None for the one asked for

    def __init__(self, bus, init_sequence, **kwargs):
        if kwargs.get("color_depth") not in (16, 24):
            raise ValueError("color_depth must be 16 or 24")
        self.init_sequence = init_sequence
        self.kw = kwargs
        self.width = kwargs["width"]
        self.height = kwargs["height"]
        self.deinited = False
        # The clock the host really makes: the one asked for, unless a test says otherwise.
        self.pixel_clock_frequency = FakeDisplay.report_clock or kwargs["pixel_clock_frequency"]
        FakeDisplay.log.append("VIDEO")

    def deinit(self):
        self.deinited = True


class FakeBus:
    """``mipidsi.Bus``, which reports the lanes and the rate it runs at."""

    def __init__(self, num_lanes, frequency):
        self.num_lanes = num_lanes
        self.frequency = frequency


class fake_mipidsi:
    Display = FakeDisplay
    Bus = FakeBus


sys.modules["mipidsi"] = fake_mipidsi

import lt8912b  # noqa: E402

PLANT = None
for _arg in sys.argv[1:]:
    if _arg.startswith("--plant="):
        PLANT = _arg[len("--plant=") :]

_passed = 0
_failed = 0


def check(name, ok, detail=""):
    global _passed, _failed
    if ok:
        _passed += 1
        print("PASS", name)
    else:
        _failed += 1
        print("FAIL", name, detail)


def raises(fn, *needles):
    """The ValueError message if ``fn`` raises one containing every needle, else None."""
    try:
        fn()
    except ValueError as exc:
        message = str(exc)
        for needle in needles:
            if needle not in message:
                return None
        return message
    return None


class FakeTime:
    def __init__(self):
        self.slept = []

    def sleep(self, seconds):
        self.slept.append(seconds)


class FakeI2C:
    def __init__(self, regs=None, present=(0x48, 0x49, 0x4A)):
        self.regs = {(0x48, 0x00): 0x12, (0x48, 0x01): 0xB2}
        self.regs.update(regs or {})
        self.present = list(present)
        self.writes = []

    def writeto_mem(self, address, register, data):
        for offset, value in enumerate(data):
            self.writes.append("%02X%02X=%02X" % (address, register + offset, value))
            self.regs[(address, register + offset)] = value

    def readfrom_mem(self, address, register, count):
        if address not in self.present:
            raise OSError(19)
        return bytes(self.regs.get((address, register + i), 0) for i in range(count))

    def scan(self):
        return list(self.present)


class LogPin:
    OUT = "out"
    IN = "in"

    def __init__(self, log, level=1):
        self.log = log
        self.level = level
        self.mode = None

    def init(self, mode, value=None):
        self.mode = mode
        if value is not None:
            self.value(value)

    def value(self, level=None):
        if level is None:
            return self.level
        self.level = level
        self.log.append(level)


def pairs(address, text):
    """``"02F7 08FF"`` on page ``address`` as ``["4802=F7", "4808=FF"]``."""
    out = []
    for item in text.split():
        out.append("%02X%s=%s" % (address, item[:2].upper(), item[2:].upper()))
    return out


# The tables as Adafruit_CircuitPython_LT8912B and esp_lcd_lt8912b write them,
# typed again here from those sources rather than read from the driver.
MAIN_INIT = "02F7 08FF 09FF 0AFF 0B7C 0CFF 31E1 32E1 330C 3700 3822 6082 3945 3A00 3B00 4431 5544 5701 5A02 3ED6 3FD4 413C"
DSI_RX_TAIL = "1400 1500 1A03 1B03"
DDS_TABLE = (
    "4E93 4F3E 5029 5180 1E4F 1F5E 2001 212C 2201 23FA 2400 25C8 2600 275E 2801 292C "
    "2A01 2BFA 2C00 2DC8 2E00 4264 4300 4404 4500 4659 4700 48F2 4906 4A00 4B72 4C45 "
    "4D00 5208 5300 54B2 5500 56E4 570D 5800 59E4 5A8A 5B00 5C34 5100 7000"
)
LVDS_OFF = "4430 5105 5024 512D 5204 690E 698E 6A00 6CB8 6B51 04FB 04FF 7F00 A813 4431"
AUDIO_OFF = "0600 0700 3452 3C40"
CLOCK_CYCLE = "0200 0800 0900 0A00 0B00 0C00 0300 0500 02F7 08FF 09FF 0AFF 0B7C 0CFF 03FF 05FF"
RX_RESET = "037F 03FF 05FB 05FF"

# A Dell E207WFP's EDID: base block and CTA-861 extension, 256 bytes.
DELL_E207WFP = unhexlify(
    "00ffffffffffff0010ac10d04c325130"
    "2c100103a02b1b78ba8db0a2544a9c25"
    "115054a54b00714f8180b30001010101"
    "01010101010121399030621a274068b0"
    "3600ae0e1100001c000000ff00363431"
    "38303641563051324c0a000000fd0038"
    "4b1e530f000a202020202020000000fc"
    "0044454c4c20453230375746500a01c9"
    "02031b71230907078301000067030c00"
    "1000802143011084e2000f011d007251"
    "d01e206e28550081490000001e000000"
    "10000000000000000000000000000000"
    "00001000000000000000000000000000"
    "00000000100000000000000000000000"
    "00000000000010000000000000000000"
    "000000000000000000000000000000bf"
)


def word16(register, value):
    return "%02X%02X %02X%02X" % (register, value % 256, register + 1, value // 256)


def dds(clock):
    # Adafruit's formula, in floating point: MHz times 0x16C16.
    word = int(clock / 1e6 * 0x16C16)
    return "%02X%02X %02X%02X %02X%02X" % (0x4E, word % 256, 0x4F, (word // 256) % 256, 0x50, word // 65536)


def avi(mode):
    pb2 = mode.aspect_ratio * 16 + 8
    body = [0x10, pb2, 0, mode.vic] + [0] * 9
    checksum = (256 - (0x82 + 0x02 + 0x0D + sum(body)) % 256) % 256
    return " ".join("%02X%02X" % (0x43 + i, v) for i, v in enumerate([checksum] + body))


def expected_start(mode, lanes=2, hdmi=False, audio_text=None, reset_pin=False):
    out = []
    if not reset_pin:
        out += pairs(0x48, CLOCK_CYCLE)
    out += pairs(0x48, "330C")
    out += pairs(0x48, MAIN_INIT)
    out += pairs(0x49, "1001 1110 13%02X " % (lanes % 4) + DSI_RX_TAIL)
    out += pairs(0x49, DDS_TABLE)
    out += pairs(0x49, "5180 " + dds(mode.pixel_clock) + " 5100")
    timing = "18%02X 19%02X " % (mode.hsync, mode.vsync) + word16(0x1C, mode.width) + " 2F0C "
    timing += " ".join((
        word16(0x34, mode.width + mode.hfp + mode.hsync + mode.hbp),
        word16(0x36, mode.height + mode.vfp + mode.vsync + mode.vbp),
        word16(0x38, mode.vbp),
        word16(0x3A, mode.vfp),
        word16(0x3C, mode.hbp),
        word16(0x3E, mode.hfp),
    ))
    out += pairs(0x49, timing)
    out += pairs(0x48, "AB%02X" % ((2 if mode.hsync_positive else 0) + (1 if mode.vsync_positive else 0)))
    out += pairs(0x4A, avi(mode))
    out += pairs(0x48, RX_RESET)
    out += pairs(0x48, LVDS_OFF)
    out += pairs(0x4A, audio_text or AUDIO_OFF)
    out += pairs(0x48, "B2%02X 330E" % (1 if hdmi else 0))
    return out


def bridge(**kwargs):
    bus = FakeI2C(kwargs.pop("regs", None))
    return lt8912b.Bridge(bus, **kwargs), bus


def first_difference(got, want):
    for index in range(max(len(got), len(want))):
        a = got[index] if index < len(got) else None
        b = want[index] if index < len(want) else None
        if a != b:
            return "write %d: got %s, want %s" % (index, a, b)
    return ""


lt8912b.time = FakeTime()

############### Plants ################

if PLANT == "hfp-hbp":
    # Swap the horizontal porches in the timing registers.
    _timing = lt8912b.Bridge._timing

    def _bad_timing(mode):
        swapped = lt8912b.Mode(mode.name, mode.pixel_clock, mode.width, mode.hbp, mode.hsync, mode.hfp,
                               mode.height, mode.vfp, mode.vsync, mode.vbp,
                               mode.hsync_positive, mode.vsync_positive, mode.vic, mode.aspect_ratio)
        return _timing(swapped)

    lt8912b.Bridge._timing = staticmethod(_bad_timing)
elif PLANT == "no-lane-check":
    lt8912b.check = lambda mode, lanes, lane_rate=None, max_lane_rate=0: lane_rate
elif PLANT == "audio-leak":
    # Leave the channel status written even with audio off.
    lt8912b._AUDIO_OFF = lt8912b._AUDIO_OFF + ((0x0F, 0x2B),)
elif PLANT == "edid-polarity":
    _parse = lt8912b._detailed_timing

    def _bad_detailed(data, offset):
        mode = _parse(data, offset)
        if mode is not None:
            mode.hsync_positive, mode.vsync_positive = mode.vsync_positive, mode.hsync_positive
        return mode

    lt8912b._detailed_timing = _bad_detailed
elif PLANT == "video-first":
    # Start the DSI video before the bridge is set up, then set it up.
    _start = lt8912b.Bridge.start
    _sync = lt8912b.Bridge.sync

    def _late_start(self, mode, **kwargs):
        self._late = (mode, kwargs)
        self._mode = mode

    def _late_sync(self, pixel_clock=None):
        _start(self, self._late[0], **self._late[1])
        _sync(self, pixel_clock)

    lt8912b.Bridge.start = _late_start
    lt8912b.Bridge.sync = _late_sync
elif PLANT == "color-remap":
    # Quietly turn color_depth=24 into an RGB565 framebuffer.
    lt8912b._color_options = lambda color_depth, output_color_depth: {"color_depth": 16, "output_color_depth": 24}
elif PLANT is not None:
    print("unknown plant", PLANT)
    sys.exit(2)

if PLANT:
    print("PLANTED", PLANT)

############### Checks ################


def check_modes():
    fitted = {}
    for name in ("640x480p60", "800x600p60", "1024x768p60", "1280x720p60", "1920x1080p30"):
        mode = lt8912b.fit(lt8912b.MODES[name])
        fitted[name] = mode
        rate = lt8912b.check(mode, 2)
        check(name + " fits two lanes", rate <= 1_500_000_000, rate)
        dev, bus = bridge()
        dev.start(mode)
        want = expected_start(mode)
        check(name + ": start writes the sources' sequence", bus.writes == want, first_difference(bus.writes, want))
        line = mode.pixel_clock / mode.htotal
        standard = lt8912b.MODES[name]
        check(name + ": line rate within 0.1% of the standard",
              abs(line / (standard.pixel_clock / standard.htotal) - 1) < 0.001, line)
        check(name + ": the clock is 240 MHz over a whole number",
              mode.pixel_clock in [240_000_000 // d for d in range(1, 20)], mode.pixel_clock)
    check("640x480 runs at 240/9 MHz", fitted["640x480p60"].pixel_clock == 26_666_666)
    check("800x600 is exact and keeps its timing", fitted["800x600p60"] is lt8912b.MODES["800x600p60"])
    check("720p keeps its VIC only if untouched", fitted["1280x720p60"].vic == 0)
    check("a padded 720p announces the VIC asked for",
          lt8912b.fit(lt8912b.MODES["1280x720p60"], vic=4).vic == 4)
    check("an exact mode keeps its own VIC",
          lt8912b.fit(lt8912b.MODES["800x600p60"], vic=4) is lt8912b.MODES["800x600p60"])
    check("720p needs 960 Mbps a lane", lt8912b.check(fitted["1280x720p60"], 2) == 960_000_000)
    check("1080p30 needs 960 Mbps a lane", lt8912b.check(fitted["1920x1080p30"], 2) == 960_000_000)
    check("640x480 needs 320 Mbps a lane", lt8912b.check(fitted["640x480p60"], 2) == 320_000_000)

    # 720p as the host sends it, every timing byte by hand: 80 MHz, htotal
    # 1650 * 80 / 74.25 = 1777.8 -> 1778, so the front porch is 110 + 128.
    dev, bus = bridge()
    dev.start(fitted["1280x720p60"])
    spelled = (
        "4918=28 4919=05 491C=00 491D=05 492F=0C 4934=F2 4935=06 4936=EE 4937=02 "
        "4938=14 4939=00 493A=05 493B=00 493C=DC 493D=00 493E=EE 493F=00"
    ).split()
    check("720p timing bytes, by hand", all(w in bus.writes for w in spelled),
          [w for w in spelled if w not in bus.writes])
    seed = "4951=80 494E=E0 494F=C6 4950=71 4951=00".split()
    start = bus.writes.index(seed[0], bus.writes.index("4970=00"))
    check("720p pixel clock word 80 x 0x16C16 = 0x71C6E0", bus.writes[start:start + 5] == seed,
          bus.writes[start:start + 5])
    check("720p sync positive both", "48AB=03" in bus.writes)
    # 640x480 is negative both, and a 4:3 VIC 0 infoframe: PB2 = 0x18, PB0 = 0x5F - 0x18.
    dev, bus = bridge()
    dev.start(fitted["640x480p60"])
    check("640x480 sync negative both", "48AB=00" in bus.writes)
    check("640x480 infoframe checksum", "4A43=47" in bus.writes and "4A45=18" in bus.writes)
    # A standard 720p with its VIC: PB0 = 0x5F - 0x28 - 4 = 0x33.
    dev, bus = bridge()
    dev.start(lt8912b.MODES["1280x720p60"], hdmi=True)
    check("720p VIC 4 infoframe", "4A43=33" in bus.writes and "4A45=28" in bus.writes and "4A47=04" in bus.writes)
    check("hdmi=True sets 0xB2", "48B2=01" in bus.writes)
    check("DVI by default", "48B2=00" in bridge_start_writes(fitted["1280x720p60"]))


def bridge_start_writes(mode, **kwargs):
    dev, bus = bridge()
    dev.start(mode, **kwargs)
    return bus.writes


def check_refusals():
    p60 = lt8912b.MODES["1920x1080p60"]
    message = raises(lambda: lt8912b.check(p60, 2), "1782 Mbps", "2 lanes", "1500")
    check("1080p60 refused on two lanes, with the numbers", message is not None)
    print("   ", message)
    message = raises(lambda: lt8912b.fit(p60), "240", "150")
    check("1080p60 can't be fitted to a 240 MHz source", message is not None)
    check("1080p60 fits four lanes", lt8912b.check(p60, 4) == 891_000_000)
    dev, bus = bridge()
    check("start refuses 1080p60 before writing", raises(lambda: dev.start(p60), "1782") is not None and not bus.writes,
          bus.writes[:3])
    slow = raises(lambda: lt8912b.check(lt8912b.fit(lt8912b.MODES["1280x720p60"]), 2, lane_rate=500_000_000), "960", "500")
    check("a bus too slow for 720p is refused", slow is not None)
    check("five lanes refused", raises(lambda: lt8912b.check(p60, 5), "lanes") is not None)
    check("Bridge(lanes=0) refused", raises(lambda: lt8912b.Bridge(FakeI2C(), lanes=0), "lanes") is not None)
    wide = lt8912b.Mode("wide", 25_000_000, 640, 16, 300, 48, 480, 10, 2, 33, False, False)
    check("hsync over 255 refused", raises(lambda: lt8912b.check(wide, 2), "sync") is not None)
    fast = lt8912b.Mode("fast", 160_000_000, 1920, 88, 44, 148, 1080, 4, 5, 36, True, True)
    check("pixel clock over 150 MHz refused", raises(lambda: lt8912b.check(fast, 4), "150") is not None)


def check_audio():
    mode = lt8912b.fit(lt8912b.MODES["1280x720p60"])
    audio_regs = (0x06, 0x07, 0x0F, 0x34, 0x35, 0x36, 0x37, 0x3C, 0x3D) + tuple(range(0xB2, 0xC0))
    writes = bridge_start_writes(mode)
    touched = [w for w in writes if w.startswith("4A") and int(w[2:4], 16) in audio_regs]
    check("audio off writes only the four audio-off registers", touched == pairs(0x4A, AUDIO_OFF), touched)

    a = lt8912b.Audio(48000, 16, "a")
    check("48 kHz 16-bit channel status 0x22", a.channel_status == 0x22)
    check("48 kHz 24-bit channel status 0x2B, as Espressif writes",
          lt8912b.Audio(48000, 24, "b").channel_status == 0x2B)
    writes = bridge_start_writes(mode, audio=a)
    want = pairs(0x4A, "0F22 3500 3618 3700 34E2 3C60 07F0 0608")
    check("recipe a: 48 kHz, N = 6144, the patch's enables", all(w in writes for w in want), want)
    check("recipe a: no audio-off writes", "4A3452" not in " ".join(writes) and "4A06=00" not in writes)
    check("audio turns HDMI on", "48B2=01" in writes)
    order = [writes.index(w) for w in want]
    check("recipe a: in the patch's order", order == sorted(order), order)

    writes = bridge_start_writes(mode, audio=lt8912b.Audio(48000, 24, "b"))
    want = pairs(0x4A, "3C41 0608 07F0 34D2 0F2B")
    check("recipe b: Espressif's set", all(w in writes for w in want), want)
    check("recipe b: no N", not any(w.startswith("4A35") for w in writes))

    bus = FakeI2C({(0x4A, 0x3D): 0x08})
    dev = lt8912b.Bridge(bus)
    dev.start(mode, audio=lt8912b.Audio(44100, 16, "c"))
    frame = [0x84, 0x01, 0x0A, 0, 0x01] + [0] * 9
    frame[3] = (256 - sum(frame) % 256) % 256
    check("recipe c: audio infoframe checksum 0x70", frame[3] == 0x70)
    want = pairs(0x4A, "0F02 3500 3618 3780 34D2 3C61") + ["4A%02X=%02X" % (0xB2 + i, v) for i, v in enumerate(frame)]
    check("recipe c: 44.1 kHz, N = 6272, infoframe at 0xB2", all(w in bus.writes for w in want),
          [w for w in want if w not in bus.writes])
    check("recipe c: keeps AVI bit, adds audio bit in 0x3D", bus.writes[-3] == "4A3D=0A", bus.writes[-3:])

    check("audio on DVI refused", raises(lambda: bridge()[0].start(mode, hdmi=False, audio=a), "HDMI") is not None)
    check("bad rate refused", raises(lambda: lt8912b.Audio(22050)) is not None)
    check("bad recipe refused", raises(lambda: lt8912b.Audio(recipe="z")) is not None)


def check_edid():
    check("EDID fixture checksums", sum(DELL_E207WFP[:128]) % 256 == 0 and sum(DELL_E207WFP[128:]) % 256 == 0)
    modes = lt8912b.parse_edid(DELL_E207WFP)
    first = modes[0]
    got = (first.width, first.height, first.pixel_clock, first.hfp, first.hsync, first.hbp,
           first.vfp, first.vsync, first.vbp, first.hsync_positive, first.vsync_positive)
    # edid-decode: 1680x1050 146.25 MHz, H 104/176/280 N, V 3/6/30 P.
    want = (1680, 1050, 146_250_000, 104, 176, 280, 3, 6, 30, False, True)
    check("preferred mode as edid-decode reads it", got == want, got)
    second = modes[1]
    got = (second.width, second.height, second.pixel_clock, second.hfp, second.hsync, second.hbp,
           second.vfp, second.vsync, second.vbp, second.hsync_positive, second.vsync_positive)
    want = (1280, 720, 74_250_000, 110, 40, 220, 5, 5, 20, True, True)
    check("CEA block's detailed 720p", got == want, got)
    names = [m.name for m in modes[2:]]
    want = ["640x480p60", "800x600p60", "1024x768p60", "1920x1080p60", "1280x720p60"]
    check("established timings and VICs 1, 16, 4", names == want, names)
    check("dummy descriptors skipped", len(modes) == 7, len(modes))
    best = lt8912b.best_mode(modes, 2)
    check("best for two lanes is 720p at 80 MHz", (best.width, best.height, best.pixel_clock) == (1280, 720, 80_000_000),
          best)
    best4 = lt8912b.best_mode(modes, 4)
    check("four lanes still can't take 1680x1050 off a 240 MHz source", (best4.width, best4.height) == (1280, 720), best4)
    broken = bytearray(DELL_E207WFP)
    broken[20] ^= 1
    check("bad checksum refused", raises(lambda: lt8912b.parse_edid(bytes(broken)), "checksum") is not None)
    check("bad header refused", raises(lambda: lt8912b.parse_edid(b"\x00" * 128), "header") is not None)

    regs = {(0x50, i): DELL_E207WFP[i] for i in range(256)}
    bus = FakeI2C(regs, present=(0x48, 0x49, 0x4A, 0x50))
    check("read_edid reads both blocks", lt8912b.read_edid(bus) == DELL_E207WFP)
    try:
        lt8912b.read_edid(FakeI2C())
        message = ""
    except OSError as exc:
        message = str(exc)
    check("no EDID names the DDC switch", "DDC switch" in message, message)


def check_bridge():
    dev, bus = bridge()
    check("detect", dev.detect() == b"\x12\xb2")
    dev, bus = bridge(regs={(0x48, 0x00): 0x26, (0x48, 0x01): 0x60})
    try:
        dev.detect()
        message = ""
    except OSError as exc:
        message = str(exc)
    check("a wrong chip ID names the DDC switch", "26 60" in message and "DDC" in message, message)
    bus = FakeI2C(present=(0x48, 0x49))
    try:
        lt8912b.Bridge(bus).detect()
        message = ""
    except OSError as exc:
        message = str(exc)
    check("a missing page is named", "0x4A" in message, message)

    dev, bus = bridge(regs={(0x48, 0xC1): 0x80})
    check("hot-plug from 0xC1 bit 7", dev.hot_plug_detected is True)
    log = []
    pin = LogPin(log, 0)
    dev = lt8912b.Bridge(FakeI2C(), hpd=pin)
    check("hot-plug pin is active low", dev.hot_plug_detected is True)
    check("hot-plug pin made an input", pin.mode == "in")

    log = []
    pin = LogPin(log)
    dev, bus = bridge(reset=pin)
    check("reset pin made an output, high", pin.mode == "out" and log == [1], (pin.mode, log))
    mode = lt8912b.fit(lt8912b.MODES["1280x720p60"])
    dev.start(mode)
    check("reset pin pulsed low then high", log == [1, 0, 1], log)
    check("no clock cycle with a reset pin", bus.writes[0] == "4833=0C", bus.writes[:2])
    dev.hold_reset(True)
    bus.present = []
    check("clashes empty when nothing answers in reset", dev.clashes() == [])

    for lanes, value in ((1, "01"), (3, "03"), (4, "00")):
        dev, bus = bridge(lanes=lanes)
        dev.start(lt8912b.fit(lt8912b.MODES["640x480p60"]))
        check("%d lanes writes 0x13=%s" % (lanes, value), "4913=" + value in bus.writes)
    dev, bus = bridge(lane_swap=True, pn_swap=True, settle=0x08)
    dev.start(mode)
    check("lane swap, P/N swap, settle", all(w in bus.writes for w in ("4915=A8", "483E=F6", "4911=08")))

    dev, bus = bridge()
    dev.start(mode)
    del bus.writes[:]
    dev.sync()
    want = pairs(0x49, "5180 4EE0 4FC6 5071 5100") + pairs(0x48, RX_RESET)
    check("sync reseeds then resets", bus.writes == want, bus.writes)

    del bus.writes[:]
    dev.test_pattern()
    # 720p fitted: DE delay 40 + 220 = 260 = 0x104, top 5 + 20 = 25, totals 1778 x 750.
    want = pairs(0x49, "7212 7304 7401 7519 7600 77D0 7825 79F2 7AEE 7B26 7C28 7D05 7080 7151 4212 1E67 "
                       "4EE0 4FC6 5071 5180")
    check("test pattern writes Espressif's set for 720p", bus.writes == want, first_difference(bus.writes, want))

    regs = {(0x48, 0x9C): 0xF2, (0x48, 0x9D): 0x06, (0x48, 0x9E): 0xEE, (0x48, 0x9F): 0x02, (0x48, 0xC1): 0x80}
    dev, bus = bridge(regs=regs)
    status = dev.status()
    check("status decodes", status["hsync"] == 1778 and status["vsync"] == 750 and status["video"] and status["hpd"],
          status)
    dev, bus = bridge(regs={(0x48, 0x9C): 0xFF, (0x48, 0x9D): 0xFF})
    check("status sees no video", dev.status()["video"] is False)
    dev, bus = bridge()
    dev.start(mode)
    dev.deinit()
    check("deinit turns the transmitter off", bus.writes[-1] == "4833=0C" and dev.mode is None)


ADAFRUIT_720P = {
    # Adafruit's lt8912b_720p.py, as it calls the constructor.
    "width": 1280, "height": 720, "hsync_pulse_width": 32, "hsync_back_porch": 80,
    "hsync_front_porch": 408, "vsync_pulse_width": 5, "vsync_back_porch": 13, "vsync_front_porch": 3,
    "pixel_clock_frequency": 80_000_000, "hsync_positive": True, "vsync_positive": True,
    "vic": 0, "aspect_ratio": 2,
}


def display(i2c=None, bus=None, report_clock=None, **kwargs):
    i2c = i2c or FakeI2C({(0x48, 0xC1): 0x80})
    FakeDisplay.log = i2c.writes
    FakeDisplay.report_clock = report_clock
    timing = dict(ADAFRUIT_720P)
    timing.update(kwargs)
    return lt8912b.LT8912B(bus or FakeBus(2, 960_000_000), i2c, **timing), i2c


def refusal(fn):
    try:
        fn()
    except (ValueError, TypeError, OSError) as exc:
        return "%s: %s" % (type(exc).__name__, exc)
    return None


def check_display():
    check("LT8912B is a mipidsi.Display", issubclass(lt8912b.LT8912B, FakeDisplay))
    mode = lt8912b.Mode("1280x720", 80_000_000, 1280, 408, 32, 80, 720, 3, 5, 13, True, True, vic=0, aspect_ratio=2)

    # Adafruit's 720p call, unchanged, on a bus that reports its figures.
    log = []
    pin = LogPin(log)
    dev, i2c = display(reset=pin)
    video = i2c.writes.index("VIDEO") if "VIDEO" in i2c.writes else -1
    want = expected_start(mode, reset_pin=True)
    check("Adafruit's call: the bridge is set up before video", i2c.writes[:video] == want,
          first_difference(i2c.writes[:video], want))
    after = pairs(0x49, "5180 " + dds(80_000_000) + " 5100") + pairs(0x48, RX_RESET)
    check("then reseeded and locked to the video", i2c.writes[video + 1:] == after, i2c.writes[video + 1:])
    kw = dev.kw
    check("mipidsi gets RGB565 in, RGB888 out, no LP blanking",
          (kw.get("color_depth"), kw.get("output_color_depth"), kw.get("low_power_blanking")) == (16, 24, False), kw)
    timing = dict((k, v) for k, v in ADAFRUIT_720P.items() if k not in ("hsync_positive", "vsync_positive", "vic", "aspect_ratio"))
    check("mipidsi gets the timing and no init sequence",
          all(kw.get(k) == v for k, v in timing.items()) and dev.init_sequence == b"", kw)
    check("width and height read through", (dev.width, dev.height) == (1280, 720))
    check("hot_plug_detected", dev.hot_plug_detected is True)
    check("reset pin pulsed", log == [1, 0, 1], log)
    dev.deinit()
    check("deinit stops video, turns the transmitter off, releases reset",
          dev.deinited and i2c.writes[-1] == "4833=0C" and pin.mode == "in", (dev.deinited, i2c.writes[-1], pin.mode))

    # Our extras: the mode from fit(), and **mode.timing().
    fitted = lt8912b.fit(lt8912b.MODES["1280x720p60"])
    dev, i2c = display(**fitted.timing())
    check("**fit(...).timing() takes the same path", "VIDEO" in i2c.writes and dev.kw["hsync_front_porch"] == 238,
          dev.kw.get("hsync_front_porch"))
    dev, i2c = display(audio=lt8912b.Audio(48000, 16, "a"))
    check("audio= reaches the bridge, in HDMI", "4A06=08" in i2c.writes and "48B2=01" in i2c.writes)
    dev, i2c = display(non_burst=True)
    check("other mipidsi arguments pass through", dev.kw.get("non_burst") is True)

    # The bus's own lanes and rate are what the bridge is set up and checked with.
    _, two_lanes = display(bus=FakeBus(2, 960_000_000))
    _, four_lanes = display(bus=FakeBus(4, 480_000_000))
    check("the bridge is set up for the bus's lanes", "VIDEO" in four_lanes.writes
          and four_lanes.writes != two_lanes.writes)

    # Refusals, before the chip is touched.
    i2c = FakeI2C()
    message = refusal(lambda: display(i2c=i2c, bus=FakeBus(2, 500_000_000)))
    check("a slow bus is refused before any write", message is not None and "960" in message and not i2c.writes, message)
    for name, value, needle in (("hsync_pulse_width", 0, "hsync_pulse_width must be between 1 and 255"),
                                ("vsync_pulse_width", 256, "vsync_pulse_width must be between 1 and 255"),
                                ("vic", 128, "vic must be between 0 and 127"),
                                ("aspect_ratio", 3, "aspect_ratio must be 0, 1, or 2"),
                                ("hsync_back_porch", 70000, "does not fit in 16 bits")):
        i2c = FakeI2C()
        message = refusal(lambda: display(i2c=i2c, **{name: value}))
        check("Adafruit's refusal: %s=%d" % (name, value), message is not None and needle in message and not i2c.writes,
              message)
    i2c = FakeI2C(present=(0x48, 0x49))
    message = refusal(lambda: display(i2c=i2c))
    check("a missing bridge is refused before any write", message is not None and "0x4A" in message
          and not i2c.writes, message)

    # Colour depth: Adafruit's color_depth=24 reaches mipidsi as asked;
    # nothing is remapped.
    dev, i2c = display(color_depth=24)
    check("color_depth=24 reaches mipidsi as asked", dev.kw.get("color_depth") == 24
          and "output_color_depth" not in dev.kw, dev.kw)
    message = refusal(lambda: display(output_color_depth=16))
    check("RGB565 on the wire is refused", message is not None and "RGB888" in message, message)
    message = refusal(lambda: display(color_depth=8))
    check("color_depth=8 is refused", message is not None and "color_depth" in message, message)

    # A display that reports a faster real clock than the bus carries.
    message = refusal(lambda: display(report_clock=85_000_000))
    check("the real clock is checked against the bus after video starts", message is not None
          and "below the 1020000000 needed" in message, message)
    dev, i2c = display(report_clock=79_999_999)
    seed = pairs(0x49, "5180 " + dds(79_999_999) + " 5100")
    check("reseeded from the clock the display reports", i2c.writes[-9:-4] == seed, i2c.writes[-9:-4])


for _fn in (check_modes, check_refusals, check_audio, check_edid, check_bridge, check_display):
    try:
        _fn()
    except Exception as _e:
        check(_fn.__name__ + " ran to the end", False, repr(_e))

print("%d passed, %d failed (%s)" % (_passed, _failed, sys.implementation.name))
sys.exit(1 if _failed else 0)
