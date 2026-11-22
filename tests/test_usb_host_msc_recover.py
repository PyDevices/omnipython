# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""usb.host.msc puts a drive back in step after a command fails part way.

A read the host can't finish (it times out, or there's no memory for its
transfer) leaves the drive in the middle of the command. Without a reset the
next command's CBW lands in that data phase and every command after it is
out of step. These tests run the module's own file against a fake drive.
"""

import importlib.util
import pathlib
import struct
import sys
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "packages" / "usb" / "usb-host-msc" / "usb" / "host" / "msc.py"
_FAKED = ("usb", "usb.core", "usb.host", "usb.host.msc")


class USBError(OSError):
    pass


class Drive:
    """A Bulk-Only drive with 512-byte blocks, as usb.core hands it over.
    ``fail_next_read`` makes the next data-phase read raise that errno."""

    def __init__(self):
        self.fail_next_read = None
        self.resets = 0
        self.cleared = []
        self.pending = None     # the command waiting for its data phase
        self.csw = None

    def configuration_descriptor(self):
        cfg = bytes((9, 2, 32, 0, 1, 1, 0, 0x80, 50))
        itf = bytes((9, 4, 0, 0, 2, 0x08, 0x06, 0x50, 0))
        ep_in = bytes((7, 5, 0x81, 2, 0, 2, 0))
        ep_out = bytes((7, 5, 0x02, 2, 0, 2, 0))
        return cfg + itf + ep_in + ep_out

    def write(self, ep, data, timeout):
        if len(data) == 31 and data[:4] == b"USBC":
            if self.pending is not None:
                raise AssertionError("a CBW arrived in the middle of a command")
            tag = struct.unpack("<I", data[4:8])[0]
            self.pending = (tag, data[15])
            self.csw = struct.pack("<IIIB", 0x53425355, tag, 0, 0)
            if data[15] == 0x00:            # TEST UNIT READY: no data phase
                self.pending = ("csw", tag)
        return len(data)

    def read(self, ep, buf, timeout):
        if self.pending is None:
            raise AssertionError("a read with no command")
        if self.pending[0] == "csw":
            buf[:13] = self.csw
            self.pending = None
            return 13
        op = self.pending[1]
        if self.fail_next_read is not None:
            e, self.fail_next_read = self.fail_next_read, None
            raise USBError(e, "fake")
        if op == 0x25:
            buf[:8] = struct.pack(">II", 999, 512)
        else:
            for i in range(len(buf)):
                buf[i] = 0x5A
        self.pending = ("csw", self.pending[0])
        return len(buf)

    def ctrl_transfer(self, bmRequestType, bRequest, wValue, wIndex, data, timeout):
        if (bmRequestType, bRequest) == (0x21, 0xFF):
            self.resets += 1
            self.pending = None
        elif (bmRequestType, bRequest) == (0x02, 0x01):
            self.cleared.append(wIndex)


def load():
    saved = {name: sys.modules.get(name) for name in _FAKED}
    usb = types.ModuleType("usb")
    core = types.ModuleType("usb.core")
    core.USBError = USBError
    usb.core = core
    sys.modules["usb"] = usb
    sys.modules["usb.core"] = core
    try:
        spec = importlib.util.spec_from_file_location("usb.host.msc", SOURCE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        for name, mod in saved.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod
    return module


class RecoverTest(unittest.TestCase):
    def setUp(self):
        self.msc = load()
        self.dev = Drive()
        self.drive = self.msc.Drive(self.dev)

    def test_opens(self):
        self.assertEqual(self.drive.blocks, 1000)
        self.assertEqual(self.drive.block_size, 512)

    def test_a_read_with_no_memory_resets_and_the_next_read_works(self):
        buf = bytearray(32768)
        self.dev.fail_next_read = 12        # ENOMEM
        with self.assertRaises(USBError) as caught:
            self.drive.readblocks(0, buf)
        self.assertEqual(caught.exception.errno, 12)
        self.assertEqual(self.dev.resets, 1)
        self.assertEqual(sorted(self.dev.cleared), [0x02, 0x81])
        self.drive.readblocks(0, buf)
        self.assertEqual(bytes(buf[:4]), b"ZZZZ")

    def test_a_read_that_times_out_resets_too(self):
        self.dev.fail_next_read = 110
        with self.assertRaises(USBError):
            self.drive.readblocks(0, bytearray(512))
        self.assertEqual(self.dev.resets, 1)
        self.drive.readblocks(0, bytearray(512))


if __name__ == "__main__":
    unittest.main()
