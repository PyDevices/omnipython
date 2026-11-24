# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""usb.host.msc puts a drive back in step after a command fails part way.

A read the host can't finish (it times out, or there's no memory for its
transfer) leaves the drive in the middle of the command. Without a reset the
next command's CBW lands in that data phase and every command after it is
out of step. These tests run the module's own file against a fake drive.

Some drives don't come back from that reset, so the module also never asks the
host for more than it can allocate: a command's data phase goes in pieces.
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
    ``fail_next_read`` makes the next data-phase read raise that errno.
    ``max_transfer`` is the largest transfer the host can allocate: a bigger
    one raises ENOMEM, as an ESP32-S3 short of DMA-capable RAM does, after
    the CBW has gone. ``has`` is how much data the drive sends for a read."""

    def __init__(self):
        self.fail_next_read = None
        self.max_transfer = None
        self.has = None
        self.resets = 0
        self.cleared = []
        self.pending = None     # the command waiting for its data phase
        self.left = 0           # bytes of its data phase still to come
        self.csw = None
        self.written = bytearray()
        self.transfers = []

    def _fits(self, n):
        self.transfers.append(n)
        if self.max_transfer is not None and n > self.max_transfer:
            raise USBError(12, "fake: no memory for the transfer")

    def configuration_descriptor(self):
        cfg = bytes((9, 2, 32, 0, 1, 1, 0, 0x80, 50))
        itf = bytes((9, 4, 0, 0, 2, 0x08, 0x06, 0x50, 0))
        ep_in = bytes((7, 5, 0x81, 2, 0, 2, 0))
        ep_out = bytes((7, 5, 0x02, 2, 0, 2, 0))
        return cfg + itf + ep_in + ep_out

    def write(self, ep, data, timeout):
        if self.pending is not None and self.pending[0] != "csw" and self.left:
            self._fits(len(data))
            if len(data) > self.left:
                raise AssertionError("more data than the command asked for")
            self.written += bytes(data)
            self.left -= len(data)
            if not self.left:
                self.pending = ("csw", self.pending[0])
            return len(data)
        if len(data) == 31 and data[:4] == b"USBC":
            if self.pending is not None:
                raise AssertionError("a CBW arrived in the middle of a command")
            tag, length = struct.unpack("<II", data[4:12])
            self.pending = (tag, data[15])
            self.left = length
            self.csw = struct.pack("<IIIB", 0x53425355, tag, 0, 0)
            if not length:                  # TEST UNIT READY: no data phase
                self.pending = ("csw", tag)
            return len(data)
        raise AssertionError("data with no command")

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
        self._fits(len(buf))
        if op == 0x25:
            buf[:8] = struct.pack(">II", 999, 512)
            n = 8
        else:
            if self.has is not None:
                self.left = min(self.left, self.has)
                self.has = None
            n = min(len(buf), self.left)
            for i in range(n):
                buf[i] = 0x5A
        self.left -= n
        if self.left <= 0 or n < len(buf):  # all sent, or a short packet
            self.pending = ("csw", self.pending[0])
        return n

    def ctrl_transfer(self, bmRequestType, bRequest, wValue, wIndex, data, timeout):
        if (bmRequestType, bRequest) == (0x21, 0xFF):
            self.resets += 1
            self.pending = None
            self.left = 0
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

    def test_a_32k_read_fits_a_host_with_no_32k_to_spare(self):
        self.dev.max_transfer = 4096
        buf = bytearray(32768)
        self.drive.readblocks(0, buf)
        self.assertEqual(bytes(buf), b"Z" * 32768)
        self.assertEqual(self.dev.resets, 0)
        self.assertLessEqual(max(self.dev.transfers), 4096)

    def test_a_32k_write_fits_a_host_with_no_32k_to_spare(self):
        self.dev.max_transfer = 4096
        data = bytes(range(256)) * 128
        self.drive.writeblocks(8, data)
        self.assertEqual(bytes(self.dev.written), data)
        self.assertEqual(self.dev.resets, 0)
        self.assertLessEqual(max(self.dev.transfers), 4096)

    def test_a_short_packet_ends_the_data_phase(self):
        self.dev.has = 5000             # less than the 8 KB asked for
        self.assertEqual(self.drive._command(bytes((0x28,)) + bytes(9), data_in=bytearray(8192)), 0)
        self.assertEqual(self.dev.resets, 0)
        self.drive.readblocks(0, bytearray(512))


if __name__ == "__main__":
    unittest.main()
