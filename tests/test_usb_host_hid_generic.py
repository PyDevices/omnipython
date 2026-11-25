# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""usb.host.hid_generic turns gamepad reports into button, axis and hat events.

The descriptors are the ones real gamepads carry (a DragonRise-style generic
pad, adafruit_ble's gamepad map), plus a pad with report IDs, sixteen-bit
signed axes and a one-to-eight hat. Every expected event below was worked out
by hand from the descriptor's bit layout, not by running the decoder.
"""

import pathlib
import sys
import types
import unittest
from binascii import unhexlify

from _mprun import need_micropython, run

ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG = ROOT / "packages" / "usb" / "usb-host-hid"

# Other test modules install their own usb packages under these names.
for _name in [m for m in sys.modules if m == "usb" or m.startswith("usb.")]:
    del sys.modules[_name]
core = types.ModuleType("usb.core")


class USBError(Exception):
    pass


class USBTimeoutError(USBError):
    pass


core.USBError, core.USBTimeoutError = USBError, USBTimeoutError
usb = types.ModuleType("usb")
usb.__path__ = [str(PKG / "usb")]
usb.core = core
sys.modules["usb"] = usb
sys.modules["usb.core"] = core

from usb.host.hid_generic import (  # noqa: E402
    AXIS, BUTTON_DOWN, BUTTON_UP, HAT, Axis, Gamepad, Hat, parse)


def h(text):
    return unhexlify("".join(text.split()))


# A generic USB gamepad (DragonRise 0079:0011 style): five 8-bit axes (Z twice, as
# it reports), a four-bit hat 0 to 7 with a null state, twelve buttons, one vendor byte.
GENERIC = h("""
05 01 09 04 a1 01 a1 02 75 08 95 05 15 00 26 ff 00 35 00 46 ff 00 09 30 09 31 09 32
09 32 09 35 81 02 75 04 95 01 25 07 46 3b 01 65 14 09 39 81 42 65 00 75 01 95 0c
25 01 45 01 05 09 19 01 29 0c 81 02 06 00 ff 75 01 95 08 25 01 45 01 09 01 81 02
c0 a1 02 75 08 95 04 46 ff 00 26 ff 00 09 02 91 02 c0 c0
""")
# adafruit_ble's gamepad: report 5, sixteen buttons, four signed 8-bit axes.
BLE_PAD = h("""
05 01 09 05 a1 01 85 05 05 09 19 01 29 10 15 00 25 01 75 01 95 10 81 02
05 01 15 81 25 7f 09 30 09 31 09 32 09 35 75 08 95 04 81 02 c0
""")
# Report 1: four signed 16-bit axes, a hat 1 to 8 (0 is its null state), ten buttons.
WIDE_PAD = h("""
05 01 09 05 a1 01 85 01 09 30 09 31 09 33 09 34 16 00 80 26 ff 7f 75 10 95 04 81 02
09 39 15 01 25 08 35 00 46 3b 01 66 14 00 75 04 95 01 81 42
05 09 19 01 29 0a 15 00 25 01 75 01 95 0a 81 02 75 01 95 02 81 03 c0
""")
# usb_hid's Device.GAMEPAD: report 4, sixteen buttons, a hat, four signed
# axes. With its ID the report is eight bytes, one whole packet.
USB_HID_PAD = h("""
05 01 09 05 a1 01 85 04 05 09 19 01 29 10 15 00 25 01 75 01 95 10 81 02
05 01 09 39 15 01 25 08 35 00 46 3b 01 65 14 75 04 95 01 81 42
35 00 45 00 65 00 81 03 09 30 09 31 09 32 09 35 15 81 25 7f 75 08 95 04 81 02 c0
""")
# A full-speed pad in the PS3 layout, read from a real one: thirteen buttons, a hat, four
# 8-bit axes, then on a vendor page twelve pressure bytes and four 10-bit motion values.
PS3_LAYOUT = h("""
05 01 09 05 a1 01 15 00 25 01 35 00 45 01 75 01 95 0d 05 09 19 01 29 0d 81 02 95 03
81 01 05 01 25 07 46 3b 01 75 04 95 01 65 14 09 39 81 42 65 00 95 01 81 01 26 ff 00
46 ff 00 09 30 09 31 09 32 09 35 75 08 95 04 81 02 06 00 ff 09 20 09 21 09 22 09 23
09 24 09 25 09 26 09 27 09 28 09 29 09 2a 09 2b 95 0c 81 02 0a 21 26 95 08 b1 02 0a
21 26 91 02 26 ff 03 46 ff 03 09 2c 09 2d 09 2e 09 2f 75 10 95 04 81 02 c0
""")
KEYBOARD = h("05 01 09 06 a1 01 05 07 19 e0 29 e7 15 00 25 01 75 01 95 08 81 02 c0")


def config(desc_len, packet=8):
    return bytes([9, 2, 34, 0, 1, 1, 0, 0xA0, 50,
                  9, 4, 0, 0, 1, 3, 0, 0, 0,
                  9, 0x21, 0x11, 0x01, 0, 1, 0x22, desc_len & 255, desc_len >> 8,
                  7, 5, 0x81, 3, packet, 0, 10])


class FakePad:
    def __init__(self, descriptor, packet=8):
        self.descriptor = descriptor
        self._cfg = config(len(descriptor), packet)
        self.reports = []
        self.requests = []

    def configuration_descriptor(self):
        return self._cfg

    def set_configuration(self):
        pass

    def ctrl_transfer(self, request_type, request, value=0, index=0, data=None, timeout=None):
        self.requests.append((request_type, request, value))
        if request_type == 0x81 and request == 6 and value == 0x2200:
            return self.descriptor[:data]
        return 0

    def read(self, endpoint, buf, timeout=None, raise_on_timeout=True):
        if not self.reports:
            return 0
        whole = self.reports.pop(0)
        report = whole[:len(buf)]
        if len(whole) > len(report):
            self.reports.insert(0, whole[len(report):])     # the rest comes as the next packet
        buf[:len(report)] = report
        return len(report)

    def _release_all(self):
        pass


def events(pad, device):
    out = []
    while True:
        e = pad.read()
        if e is None:
            return out
        out.append(e)


class Parsing(unittest.TestCase):
    def test_the_generic_pad(self):
        fields, ids, apps = parse(GENERIC)
        self.assertFalse(ids)
        self.assertEqual(apps, [0x10004])
        kinds = [(f[0], f[2], f[3], f[6]) for f in fields]
        self.assertEqual(kinds[:5], [(1, 0, 8, Axis.X), (1, 8, 8, Axis.Y), (1, 16, 8, Axis.Z),
                                     (1, 24, 8, Axis.Z), (1, 32, 8, Axis.RZ)])
        self.assertEqual(kinds[5], (2, 40, 4, 0x10039))
        self.assertEqual([k[1] for k in kinds[6:18]], list(range(44, 56)))
        self.assertEqual([k[3] for k in kinds[6:18]], list(range(1, 13)))
        self.assertEqual(len(fields), 5 + 1 + 12 + 8)   # the vendor byte is eight one-bit extras
        self.assertEqual([f[0] for f in fields[18:]], [3] * 8)
        self.assertEqual([f[8] for f in fields[18:]], list(range(8)))
        self.assertEqual(fields[0][4:6], [0, 255])
        self.assertEqual(fields[5][4:6], [0, 7])

    def test_report_ids_move_every_offset_by_a_byte(self):
        fields, ids, apps = parse(BLE_PAD)
        self.assertTrue(ids)
        self.assertEqual(apps, [0x10005])
        self.assertEqual(fields[0][1:4], [5, 8, 1])
        self.assertEqual(fields[16][1:4], [5, 24, 8])
        self.assertEqual(fields[16][4:6], [-127, 127])

    def test_a_keyboard_has_no_gamepad_fields(self):
        fields, ids, apps = parse(KEYBOARD)
        self.assertEqual(fields, [])
        self.assertEqual(apps, [0x10006])


class Matching(unittest.TestCase):
    def test_match(self):
        self.assertTrue(Gamepad.match(FakePad(GENERIC)))
        self.assertTrue(Gamepad.match(FakePad(BLE_PAD)))
        self.assertFalse(Gamepad.match(FakePad(KEYBOARD)))

    def test_a_keyboard_is_refused(self):
        with self.assertRaises(ValueError):
            Gamepad(FakePad(KEYBOARD))
        with self.assertRaises(ValueError):
            Gamepad(None)


class Reading(unittest.TestCase):
    def test_the_generic_pad(self):
        dev = FakePad(GENERIC)
        pad = Gamepad(dev)
        # Rest: every axis at 0x7f, the hat's null state (15), nothing pressed.
        dev.reports = [bytes.fromhex("7f7f7f7f7f0f0000")]
        self.assertEqual(events(pad, dev), [
            (AXIS, Axis.X, 127), (AXIS, Axis.Y, 127), (AXIS, Axis.Z, 127), (AXIS, Axis.Z, 127),
            (AXIS, Axis.RZ, 127), (HAT, 0, Hat.CENTER)])
        # X full right, hat up-right, buttons 1, 2 and 5.
        dev.reports = [bytes.fromhex("ff7f7f7f7f310100")]
        self.assertEqual(events(pad, dev), [
            (BUTTON_DOWN, 1, 0), (BUTTON_DOWN, 2, 0), (BUTTON_DOWN, 5, 0),
            (AXIS, Axis.X, 255), (HAT, 0, Hat.UP_RIGHT)])
        self.assertEqual(pad.buttons, {1, 2, 5})
        self.assertEqual(pad.hats, {0: Hat.UP_RIGHT})
        self.assertEqual(pad.axes[Axis.X], 255)
        # Everything let go.
        dev.reports = [bytes.fromhex("7f7f7f7f7f0f0000")]
        self.assertEqual(events(pad, dev), [
            (BUTTON_UP, 1, 0), (BUTTON_UP, 2, 0), (BUTTON_UP, 5, 0),
            (AXIS, Axis.X, 127), (HAT, 0, Hat.CENTER)])
        self.assertEqual(pad.buttons, set())

    def test_a_report_that_changes_nothing_makes_no_event(self):
        dev = FakePad(GENERIC)
        pad = Gamepad(dev)
        dev.reports = [bytes.fromhex("7f7f7f7f7f0f0000")] * 2
        events(pad, dev)
        dev.reports = [bytes.fromhex("7f7f7f7f7f0f0000")]
        self.assertEqual(events(pad, dev), [])

    def test_the_hat_goes_round_clockwise(self):
        dev = FakePad(GENERIC)
        pad = Gamepad(dev)
        seen = []
        for direction in range(8):
            dev.reports = [bytes([0x7F] * 5 + [direction, 0, 0])]
            seen += [e[2] for e in events(pad, dev) if e[0] == HAT]
        self.assertEqual(seen, list(range(8)))

    def test_signed_axes_with_a_report_id(self):
        dev = FakePad(BLE_PAD)
        pad = Gamepad(dev)
        # Report 5: buttons 16 and 3, X -128 is out of range but -127 is the floor, Y 100, Z 0, Rz 127.
        dev.reports = [bytes([5, 0x04, 0x80, 0x81, 100, 0, 127])]
        got = events(pad, dev)
        self.assertEqual([e for e in got if e[0] != AXIS], [(BUTTON_DOWN, 3, 0), (BUTTON_DOWN, 16, 0)])
        self.assertEqual([e[2] for e in got if e[0] == AXIS], [-127, 100, 0, 127])
        self.assertEqual(pad.scaled(Axis.X), -1.0)
        self.assertEqual(pad.scaled(Axis.RZ), 1.0)
        self.assertEqual(pad.axis_range(Axis.X), (-127, 127))
        # A report with another ID is not this one's.
        dev.reports = [bytes([9, 0xFF, 0xFF, 0, 0, 0, 0])]
        self.assertEqual(events(pad, dev), [])

    def test_sixteen_bit_axes_and_a_one_to_eight_hat(self):
        dev = FakePad(WIDE_PAD, packet=8)
        pad = Gamepad(dev)
        # Report 1: X -32768, Y 32767, Rx 258, Ry -2; hat 3 (right-down is value 4: up is 1);
        # buttons 1 and 10 down.
        body = (-32768).to_bytes(2, "little", signed=True) + (32767).to_bytes(2, "little") \
            + (258).to_bytes(2, "little") + (-2).to_bytes(2, "little", signed=True)
        # hat 3 in bits 72-75, buttons from bit 76: button 1 is bit 76 (0x10 of the byte), button 10 is bit 85.
        dev.reports = [bytes([1]) + body + bytes([0x03 | 0x10, 0x20])]
        got = events(pad, dev)
        self.assertEqual([e for e in got if e[0] != AXIS], [
            (BUTTON_DOWN, 1, 0), (BUTTON_DOWN, 10, 0), (HAT, 0, Hat.RIGHT)])
        self.assertEqual([(e[1], e[2]) for e in got if e[0] == AXIS], [
            (Axis.X, -32768), (Axis.Y, 32767), (Axis.RX, 258), (Axis.RY, -2)])

    def test_an_eleven_byte_report_comes_over_two_packets(self):
        dev = FakePad(WIDE_PAD, packet=8)
        pad = Gamepad(dev)
        dev.reports = [bytes([1]) + bytes(8) + bytes([0x00, 0x00])]
        self.assertEqual([e for e in events(pad, dev) if e[0] == HAT], [(HAT, 0, Hat.CENTER)])

    def test_reports_that_each_fill_a_packet_stay_apart(self):
        # Two reports back to back, each exactly one packet: the second is the
        # next report, not the rest of the first.
        dev = FakePad(USB_HID_PAD, packet=8)
        pad = Gamepad(dev)
        dev.reports = [bytes([4, 0x01, 0, 0, 0, 0, 0, 0]), bytes([4, 0x03, 0, 0, 0, 0, 0, 0])]
        self.assertEqual([e for e in events(pad, dev) if e[0] == BUTTON_DOWN],
                         [(BUTTON_DOWN, 1, 0), (BUTTON_DOWN, 2, 0)])
        self.assertEqual(pad.buttons, {1, 2})
        dev = FakePad(GENERIC)
        pad = Gamepad(dev)
        dev.reports = [bytes.fromhex("7f7f7f7f7f1f0000"), bytes.fromhex("7f7f7f7f7f3f0000")]
        self.assertEqual([e for e in events(pad, dev) if e[0] == BUTTON_DOWN],
                         [(BUTTON_DOWN, 1, 0), (BUTTON_DOWN, 2, 0)])

    def test_tolerance_hides_small_axis_moves(self):
        dev = FakePad(GENERIC)
        pad = Gamepad(dev, tolerance=3)
        dev.reports = [bytes.fromhex("7f7f7f7f7f0f0000"), bytes.fromhex("827f7f7f7f0f0000"),
                       bytes.fromhex("847f7f7f7f0f0000")]
        got = []
        while dev.reports:      # the middle report makes no event, so read on past it
            got += events(pad, dev)
        self.assertEqual([e for e in got if e[0] == AXIS and e[1] == Axis.X], [(AXIS, Axis.X, 127), (AXIS, Axis.X, 132)])


class Extras(unittest.TestCase):
    def test_vendor_values_are_kept_in_report_order_and_make_no_events(self):
        dev = FakePad(PS3_LAYOUT, packet=64)
        pad = Gamepad(dev)
        self.assertEqual([i[0] for i in pad.extra_info],
                         [0xFF000000 | u for u in range(0x20, 0x30)])
        self.assertEqual(pad.extra_info[0][1:], (0, 255))
        self.assertEqual(pad.extra_info[12][1:], (0, 1023))
        self.assertEqual(pad.extras, [None] * 16)
        # As captured: button 2 (A) held, its pressure byte (the seventh) full, the
        # motion values at rest.
        dev.reports = [h("02 00 0f 80 7f 80 7f 00 00 00 00 00 00 ff 00 00 00 00 00 f3 01 ee 00 b4 01 03 02")]
        got = events(pad, dev)
        self.assertIn((BUTTON_DOWN, 2, 0), got)
        self.assertEqual(pad.extras, [0, 0, 0, 0, 0, 0, 255, 0, 0, 0, 0, 0, 499, 238, 436, 515])
        self.assertEqual(pad.reports, 1)
        # Only the motion values move: the report is read and kept, with no event.
        dev.reports = [h("02 00 0f 80 7f 80 7f 00 00 00 00 00 00 ff 00 00 00 00 00 00 02 ee 00 b4 01 03 02")]
        self.assertEqual(events(pad, dev), [])
        self.assertEqual(pad.extras[12], 512)
        self.assertEqual(pad.reports, 2)


    def test_a_vendor_usage_range_is_read_without_a_list(self):
        # Usage Page 0xFF00, Usage Minimum 1, Usage Maximum 0xFFFF, three 8-bit
        # values: a 32-bit board can't make range(0xFF000001, 0xFF010000).
        d = bytes([0x06, 0x00, 0xFF, 0x09, 0x01, 0xA1, 0x01, 0x19, 0x01, 0x2A, 0xFF, 0xFF,
                   0x15, 0x00, 0x26, 0xFF, 0x00, 0x75, 0x08, 0x95, 0x03, 0x81, 0x02, 0xC0])
        fields, ids, apps = parse(d)
        self.assertEqual([f[6] for f in fields], [0xFF000001, 0xFF000002, 0xFF000003])
        self.assertEqual(apps, [0xFF000001])

    def test_a_count_past_the_usage_range_repeats_its_last_usage(self):
        d = bytes([0x05, 0x09, 0x19, 0x01, 0x29, 0x02, 0x15, 0x00, 0x25, 0x01,
                   0x75, 0x01, 0x95, 0x04, 0x81, 0x02])
        fields, ids, apps = parse(d)
        self.assertEqual([f[6] for f in fields], [1, 2, 2, 2])


class OnMicroPython(unittest.TestCase):
    def test_the_decoder_runs_there(self):
        interpreter = need_micropython(self)
        r = run([interpreter, "usb_host_hid_generic_mp.py"], timeout=120,
                env={"USB_HOST_HID_ROOT": str(PKG)})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("ok", r.stdout)


if __name__ == "__main__":
    unittest.main()
