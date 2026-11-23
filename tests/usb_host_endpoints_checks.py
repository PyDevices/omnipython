# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""usb.host.endpoints against a stand-in host port, runnable on MicroPython and CPython.

    python tests/usb_host_endpoints_checks.py        # from the repo root, or
    micropython tests/usb_host_endpoints_checks.py

The stand-in is the firmware's _usbhost C module, so the real usb.core runs
on top of it. Devices are plugged in and pulled out by changing its list and
its counters, the way the C host does. Two of the devices are descriptors
captured from real hardware (a USB audio codec and a Logitech C920e's video); the
rest are built here. test_usb_host_endpoints.py runs this under both
interpreters.
"""

import os
import sys

_root = os.getcwd()
try:
    sys.dont_write_bytecode = True  # the tree below is removed after the run
except AttributeError:
    pass  # MicroPython writes no bytecode and has no such setting

# usb.core and usb.host.endpoints live in two packages that both hold a usb/
# folder, and MicroPython has no namespace packages, so put them in one tree.
_tree = _root + "/.usb_host_endpoints_tree"


def _mkdir(path):
    try:
        os.mkdir(path)
    except OSError:
        pass


def _copy(src, dst):
    with open(src, "rb") as f:
        data = f.read()
    with open(dst, "wb") as f:
        f.write(data)


for _d in ("", "/usb", "/usb/host"):
    _mkdir(_tree + _d)
_copy(_root + "/packages/usb/usb-core/usb/core.py", _tree + "/usb/core.py")
_copy(_root + "/packages/usb/usb-core/usb/util.py", _tree + "/usb/util.py")
_copy(_root + "/packages/usb/usb-host-endpoints/usb/host/endpoints.py", _tree + "/usb/host/endpoints.py")
for _p in (_root + "/utils", _tree, _root + "/packages/endpointkit", _root + "/tests"):
    sys.path.insert(0, _p)

FAILS = []


def check(cond, what):
    if cond:
        print("ok   ", what)
    else:
        FAILS.append(what)
        print("FAIL ", what)


# -- the stand-in host port -------------------------------------------------------


def _utf16(text):
    out = bytearray([2 + 2 * len(text), 3])
    for c in text:
        out += bytes([ord(c) & 0xFF, ord(c) >> 8])
    return bytes(out)


class FakeDevice:
    def __init__(self, vid, pid, blob, classes, product=None, serial=None, reports=None, speed="full"):
        self.vid, self.pid, self.blob, self.classes = vid, pid, blob, classes
        self.product, self.serial, self.speed = product, serial, speed
        self.reports = reports or {}   # interface -> report descriptor
        self.ctrl_calls = 0

    def device_descriptor(self):
        return bytes([18, 1, 0, 2, 0, 0, 0, 64, self.vid & 0xFF, self.vid >> 8, self.pid & 0xFF, self.pid >> 8,
                      0, 1, 0, 2 if self.product else 0, 3 if self.serial else 0, 1])


class FakeUsbHost:
    """What usb.core calls on the firmware's _usbhost."""

    def __init__(self):
        self.running = False
        self.attaches = self.detaches = 0
        self.devices = {}   # id -> FakeDevice
        self._next = 1
        self.list_calls = 0
        self.stats_calls = 0

    def plug(self, dev):
        self.devices[self._next] = dev
        self._next += 1
        self.attaches += 1
        return self._next - 1

    def pull(self, dev_id):
        del self.devices[dev_id]
        self.detaches += 1

    # -- _usbhost's own calls

    def host_start(self, classes, full_speed=False):
        self.running = True

    def host_stop(self):
        self.running = False

    def host_stats(self):
        self.stats_calls += 1
        return (self.running, self.attaches, self.detaches, 0, len(self.devices), 1)

    def host_devices(self):
        self.list_calls += 1
        return tuple((i, d.vid, d.pid, None, None, set(d.classes), d.speed) for i, d in self.devices.items())

    def host_desc(self, dev_id):
        if dev_id not in self.devices:
            raise OSError(19)
        return self.devices[dev_id].blob

    def host_ctrl(self, dev_id, setup, buf, timeout):
        dev = self.devices.get(dev_id)
        if dev is None:
            raise OSError(19)
        dev.ctrl_calls += 1
        request_type, request, value, index = setup[0], setup[1], setup[2] | setup[3] << 8, setup[4] | setup[5] << 8
        if request != 6:
            return 0
        kind, number = value >> 8, value & 0xFF
        if request_type == 0x80 and kind == 1:
            reply = dev.device_descriptor()
        elif request_type == 0x80 and kind == 3:
            reply = {0: bytes([4, 3, 9, 4]), 2: _utf16(dev.product or ""), 3: _utf16(dev.serial or "")}[number]
        elif request_type == 0x81 and kind == 0x22 and index in dev.reports:
            reply = dev.reports[index]
        else:
            raise OSError(32)   # a stall, as a device without it answers
        n = min(len(reply), len(buf))
        buf[:n] = reply[:n]
        return n


fake = FakeUsbHost()
sys.modules["_usbhost"] = fake

import endpointkit  # noqa: E402
import usb.core  # noqa: E402
from _usb_descriptors import _C920E, _CODEC, _uac2_blob  # noqa: E402
from usb.host import endpoints  # noqa: E402

# -- devices ----------------------------------------------------------------------


def config(*parts):
    blob = bytes([9, 2, 0, 0, 1, 1, 0, 0x80, 50]) + b"".join(parts)
    return blob[:2] + bytes([len(blob) & 0xFF, len(blob) >> 8]) + blob[4:]


def itf(number, cls, sub, proto, n_eps, alt=0):
    return bytes([9, 4, number, alt, n_eps, cls, sub, proto, 0])


def ep(address, attributes=2, size=64):
    return bytes([7, 5, address, attributes, size & 0xFF, size >> 8, 1])


def hid_desc(length):
    return bytes([9, 0x21, 0x11, 1, 0, 1, 0x22, length & 0xFF, length >> 8])


# Report descriptors: a gamepad, and a receiver that is keyboard and mouse at once.
GAMEPAD = bytes([0x05, 0x01, 0x09, 0x05, 0xA1, 0x01, 0x05, 0x09, 0x19, 1, 0x29, 16, 0x81, 0x02, 0xC0])
COMBO = bytes([0x05, 0x01, 0x09, 0x06, 0xA1, 0x01, 0x85, 1, 0x05, 0x07, 0x81, 0x02, 0xC0,
               0x05, 0x01, 0x09, 0x02, 0xA1, 0x01, 0x85, 2, 0x09, 0x01, 0xA1, 0x00, 0x81, 0x02, 0xC0, 0xC0,
               0x05, 0x0C, 0x09, 0x01, 0xA1, 0x01, 0x85, 3, 0x81, 0x02, 0xC0])

KEYBOARD = FakeDevice(0x046D, 0xC31C, config(itf(0, 3, 1, 1, 1), hid_desc(65), ep(0x81, 3, 8)), ("hid",), "USB Keyboard")
MOUSE = FakeDevice(0x046D, 0xC077, config(itf(0, 3, 1, 2, 1), hid_desc(52), ep(0x81, 3, 4)), ("hid",), "USB Optical Mouse")
PAD = FakeDevice(0x2DC8, 0x3106, config(itf(0, 3, 0, 0, 1), hid_desc(len(GAMEPAD)), ep(0x81, 3, 16)), ("hid",),
                 "8BitDo Pro 2", reports={0: GAMEPAD})
RECEIVER = FakeDevice(0x046D, 0xC52B, config(itf(2, 3, 0, 0, 1), hid_desc(len(COMBO)), ep(0x83, 3, 32)), ("hid",),
                      "USB Receiver", reports={2: COMBO})
MIDI = FakeDevice(0x1C75, 0x0288, config(itf(0, 1, 1, 0, 0), itf(1, 1, 3, 0, 2), ep(0x81), ep(0x02)), ("midi",),
                  "Arturia KeyStep 37", serial="00000000001A")
TWO_PORTS = FakeDevice(0x0582, 0x0012, config(itf(0, 1, 3, 0, 1), ep(0x81), itf(1, 1, 3, 0, 1), ep(0x02),
                                              itf(2, 1, 3, 0, 1), ep(0x83)), ("midi",), "UM-ONE")
DRIVE = FakeDevice(0x0781, 0x5581, config(itf(0, 8, 6, 0x50, 2), ep(0x81), ep(0x02)), ("msc",), "Ultra",
                   serial="4C530001:090305")
DRIVE2 = FakeDevice(0x0781, 0x5581, config(itf(0, 8, 6, 0x50, 2), ep(0x81), ep(0x02)), ("msc",), "Ultra",
                    serial="4C530001:999999")
SERIAL = FakeDevice(0x2E8A, 0x0005, config(itf(0, 2, 2, 1, 1), ep(0x83, 3, 8), itf(1, 10, 0, 0, 2), ep(0x81),
                                           ep(0x02)), ("cdc",), "Board in FS mode")
ECM = FakeDevice(0x0BDA, 0x8153, config(itf(0, 2, 6, 0, 1), ep(0x83, 3, 16), itf(1, 10, 0, 0, 0),
                                        itf(1, 10, 0, 0, 2, alt=1), ep(0x81), ep(0x02)), ("cdc",), "USB 10/100/1000 LAN")
RNDIS = FakeDevice(0x04E8, 0x6863, config(itf(0, 0xE0, 1, 3, 1), ep(0x82, 3, 8), itf(1, 10, 0, 0, 2), ep(0x81),
                                          ep(0x01)), ("cdc",), "SAMSUNG_Android")
PHONE_FILES = FakeDevice(0x04E8, 0x6860, config(itf(0, 6, 1, 1, 3), ep(0x81), ep(0x01), ep(0x82, 3, 28)), ("other",),
                         "SAMSUNG_Android")
HUB = FakeDevice(0x05E3, 0x0610, config(itf(0, 9, 0, 0, 1), ep(0x81, 3, 1)), ("other",), "USB2.0 Hub")
CODEC = FakeDevice(0x08BB, 0x2900, _CODEC, ("uac", "hid"), "USB Audio CODEC")
SPEAKER = FakeDevice(0x303A, 0x4002, _uac2_blob(), ("uac",), None, speed="high")
CAMERA = FakeDevice(0x046D, 0x08B6, _C920E, ("uvc", "uac"), "HD Pro Webcam C920e", serial="1A2B3C4D", speed="high")


def labels(kind, registry):
    return sorted(e.label for e in registry.endpoints(kind))


class Silent:
    """A device that stalls every request, for the parsers alone."""

    def ctrl_transfer(self, *args):
        raise OSError(32)


def t_parsers():
    found = endpoints.interfaces(_uac2_blob())
    stream = [i for i in found if i["number"] == 3][0]
    check(stream["outs"] == [0x03] and stream["ins"] == [], "a speaker's feedback endpoint isn't read as audio in")
    check(endpoints.hid_kinds(GAMEPAD) == ["gamepad"], "a gamepad's report descriptor names a gamepad")
    check(endpoints.hid_kinds(COMBO) == ["keys", "pointer"], "a receiver's names keys and pointer, not its media keys")
    check(endpoints.hid_kinds(b"") == [], "an empty report descriptor names nothing")
    check(endpoints.hid_kinds(bytes([0x06, 0x00, 0xFF, 0x09, 0x01, 0xA1, 0x01, 0xC0])) == [], "a vendor page names nothing")
    kinds = [k for k, _ in endpoints.kinds_of(Silent(), _CODEC)]
    check("audio.out" in kinds and "audio.in" in kinds, "the captured codec plays and records: %r" % kinds)
    kinds = [k for k, _ in endpoints.kinds_of(Silent(), _C920E)]
    check(kinds == ["camera"], "the captured C920e's twelve streaming alternates are one camera: %r" % kinds)


def t_not_started():
    # Registered with start=False, nothing starts the port: its devices are
    # listed on the first poll after a program starts it.
    reg = endpointkit.Registry()
    made = endpoints.register(reg, start=False)
    late = FakeDevice(0x1234, 0x0001, config(itf(0, 3, 1, 1, 1), ep(0x81, 3, 8)), ("hid",), "Late Keyboard")
    dev_id = fake.plug(late)
    reg.poll()
    check(not usb.core.running() and not fake.running, "register(start=False) leaves the port stopped")
    check("Late Keyboard" not in labels("keys", reg), "and lists nothing while it's stopped")
    usb.core.start(full_speed=True)
    reg.poll()
    check("Late Keyboard" in labels("keys", reg), "a program starting the port gets its devices listed on the next poll")
    fake.pull(dev_id)
    reg.poll()
    endpoints.unregister(reg, made)
    usb.core.stop()


def t_hotplug():
    reg = endpointkit.Registry()
    check(not usb.core.running(), "the port isn't running before register")
    made = endpoints.register(reg)
    check(usb.core.running(), "register starts the port")
    check([p.kind for p in made] == list(endpoints.KINDS), "one provider per kind")
    check("storage" in endpointkit.KINDS and "serial" in endpointkit.KINDS, "storage and serial are kinds now")
    check(all(not reg.endpoints(k) for k in endpoints.KINDS), "nothing plugged in, nothing listed")

    calls = fake.list_calls
    for _ in range(20):
        reg.poll()
    check(fake.list_calls == calls, "polls with nothing plugged in don't list devices (%d calls)" % (fake.list_calls - calls))
    stats = fake.stats_calls
    reg.poll()
    check(fake.stats_calls == stats + 1, "a poll reads the host's counters once (%d)" % (fake.stats_calls - stats))

    ids = {}
    for dev in (KEYBOARD, MOUSE, PAD, RECEIVER, MIDI, TWO_PORTS, DRIVE, DRIVE2, SERIAL, ECM, RNDIS, PHONE_FILES, HUB,
                CODEC, SPEAKER, CAMERA):
        ids[dev] = fake.plug(dev)
    calls = fake.list_calls
    check(reg.poll(), "a poll after plugging in reports a change")
    check(fake.list_calls == calls + 1, "eleven providers share one listing (%d)" % (fake.list_calls - calls))
    check(not reg.poll(), "the next poll has nothing new")

    check(labels("keys", reg) == ["USB Keyboard", "USB Receiver"], "keys: %r" % labels("keys", reg))
    check(labels("pointer", reg) == ["USB Optical Mouse", "USB Receiver"], "pointer: %r" % labels("pointer", reg))
    check(labels("gamepad", reg) == ["8BitDo Pro 2"], "gamepad: %r" % labels("gamepad", reg))
    check(labels("midi.in", reg) == ["Arturia KeyStep 37", "UM-ONE 1", "UM-ONE 2"], "midi.in: %r" % labels("midi.in", reg))
    check(labels("midi.out", reg) == ["Arturia KeyStep 37", "UM-ONE"], "midi.out: %r" % labels("midi.out", reg))
    check(labels("storage", reg) == ["SAMSUNG_Android", "Ultra 1", "Ultra 2"], "two of one drive are numbered: %r" % labels("storage", reg))
    check(labels("serial", reg) == ["Board in FS mode"], "serial: %r" % labels("serial", reg))
    check(labels("net", reg) == ["SAMSUNG_Android", "USB 10/100/1000 LAN"], "net: %r" % labels("net", reg))
    check(labels("camera", reg) == ["HD Pro Webcam C920e"], "camera: %r" % labels("camera", reg))
    check(labels("audio.out", reg) == ["USB Audio CODEC", "USB device 303a:4002"], "audio.out: %r" % labels("audio.out", reg))
    check(labels("audio.in", reg) == ["USB Audio CODEC"], "audio.in: %r" % labels("audio.in", reg))
    every = [e for k in endpoints.KINDS for e in reg.endpoints(k)]
    check(not [e for e in every if e.caps["vid"] == 0x05E3], "a hub serves no kind")
    check(len(set(e.id for e in every)) == len(every), "every endpoint id is different")
    check(not [e for e in every if e.id.count(":") != 1], "no serial number puts a second ':' in an id")

    drive = [e for e in reg.endpoints("storage") if "090305" in e.id][0]
    check(drive.id == "usb-storage:0781-5581-4C530001_090305-i0", "a drive's id holds its serial: %s" % drive.id)
    dev = endpoints.device(drive)
    check(dev is not None and dev.idProduct == 0x5581 and "msc" in dev.classes, "device() hands back its usb.core.Device")
    check(endpoints.interface(drive) == 0, "interface() names the interface")

    reg.select("storage", drive.id)
    check(reg.find(drive.id).state == endpointkit.CONNECTED, "choosing a drive marks it connected")

    fake.pull(ids[DRIVE])
    fake.pull(ids[KEYBOARD])
    check(reg.poll(), "pulling devices out is a change")
    check(labels("keys", reg) == ["USB Receiver"], "the keyboard is gone from keys")
    check(labels("storage", reg) == ["SAMSUNG_Android", "Ultra"], "the drive is gone from storage: %r" % labels("storage", reg))
    check(drive.id in reg.chosen("storage"), "its choice stays, for when it's back")
    check(endpoints.device(drive) is None, "device() is None once it's gone")

    ids[DRIVE] = fake.plug(DRIVE)
    reg.poll()
    back = reg.find(drive.id)
    check(back is not None and back.state == endpointkit.CONNECTED, "plugged back in, the chosen drive is connected again")

    endpoints.unregister(reg, made)
    check(not reg.providers(), "unregister removes every provider")
    check(usb.core.running(), "and leaves the port running")


def t_flaky():
    reg = endpointkit.Registry()
    made = endpoints.register(reg)
    gone = FakeDevice(0x1234, 0x5678, config(itf(0, 3, 1, 1, 1), ep(0x81, 3, 8)), ("hid",), "Flaky")
    fake.plug(gone)
    real = fake.host_desc

    def refuses(dev_id):
        if fake.devices.get(dev_id) is gone:
            raise OSError(19)
        return real(dev_id)

    fake.host_desc = refuses
    reg.poll()
    check("Flaky" not in labels("keys", reg), "a device that won't answer is left out, not raised")
    fake.host_desc = real
    endpoints.unregister(reg, made)


def t_no_host():
    saved = sys.modules.pop("_usbhost")

    class NoHost:
        def host_stats(self):
            raise AttributeError("host_stats")

    sys.modules["_usbhost"] = NoHost()
    usb.core._usbhost = sys.modules["_usbhost"]
    try:
        endpoints.register(endpointkit.Registry())
        raised = None
    except OSError as exc:
        raised = str(exc)
    check(raised and "no USB host" in raised, "firmware without a host: register says so (%r)" % raised)
    sys.modules["_usbhost"] = saved
    usb.core._usbhost = saved


def t_audio_out():
    # A USB speaker chosen under audio.out opens through usb.host.audio, on
    # the device the endpoint names. A stand-in records what it was asked.
    reg = endpointkit.Registry()
    made = endpoints.register(reg)
    out = [p for p in made if p.kind == "audio.out"][0]
    check(isinstance(out, endpoints.UsbAudioOut), "audio.out's provider can open what it lists")
    if not [d for d in fake.devices.values() if d is CODEC]:
        fake.plug(CODEC)
    reg.poll()
    codec = [e for e in reg.endpoints("audio.out") if e.label == "USB Audio CODEC"][0]
    try:
        out.open_out(codec)
        raised = None
    except ImportError as exc:
        raised = str(exc)
    check(raised and "usb-host-audio" in raised, "without usb-host-audio, opening says what's missing (%r)" % raised)

    class Audio:
        calls = []

        @staticmethod
        def audio_out(format=None, **kwargs):
            Audio.calls.append((format, kwargs))
            return "player"

    import usb.host

    sys.modules["usb.host.audio"] = Audio
    usb.host.audio = Audio
    try:
        reg.select("audio.out", codec.id)
        check(reg.find(codec.id).state == endpointkit.CONNECTED, "choosing the codec marks it connected")
        got = out.open_out(codec, "fmt", latency="buffered")
        fmt, kwargs = Audio.calls[-1] if Audio.calls else (None, {})
        check(got == "player" and fmt == "fmt", "open_out hands back usb.host.audio's player for the format asked")
        check(kwargs.get("dev") is endpoints.device(codec) and kwargs.get("dev") is not None,
              "on the device the endpoint names")
        check(kwargs.get("latency") == "buffered", "with the keywords it was given: %r" % kwargs)
        for dev_id, dev in list(fake.devices.items()):
            if dev is CODEC:
                fake.pull(dev_id)
        reg.poll()
        try:
            out.open_out(codec)
            code = None
        except OSError as exc:
            code = exc.args[0]
        check(code == 19, "a pulled-out speaker can't be opened (%r)" % code)
    finally:
        del sys.modules["usb.host.audio"]
        del usb.host.audio
        endpoints.unregister(reg, made)


def _cleanup():
    for d in ("/usb/host/endpoints.py", "/usb/core.py", "/usb/util.py"):
        try:
            os.remove(_tree + d)
        except OSError:
            pass
    for d in ("/usb/host", "/usb", ""):
        try:
            os.rmdir(_tree + d)
        except OSError:
            pass


try:
    t_parsers()
    t_not_started()
    t_hotplug()
    t_flaky()
    t_audio_out()
    t_no_host()
finally:
    _cleanup()

if FAILS:
    print("%d failed" % len(FAILS))
    sys.exit(1)
print("all checks passed on %s" % sys.implementation.name)
