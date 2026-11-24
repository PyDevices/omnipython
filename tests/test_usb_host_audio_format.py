# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""usb.host.audio must open a 16-bit stream when no format is given and the
device has one, since audiodev's formats are 8, 16 or 32 bits.

The descriptor is a USB-C hub's audio function (001f:0b21, "AB13X USB
Audio"), USB Audio 2.0: its speaker offers 24-bit (alt 1) and 16-bit (alt 2) stereo, its
microphone 16-bit (alt 1) and 24-bit (alt 2) mono, all at 44.1 and 48 kHz.
"""

import pathlib
import sys
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

_usbhost = types.ModuleType("_usbhost")
_usbhost.Ring = bytearray
sys.modules["_usbhost"] = _usbhost
# Other test modules install their own usb packages under these names.
for _name in [m for m in sys.modules if m == "usb" or m.startswith("usb.")]:
    del sys.modules[_name]
usb = types.ModuleType("usb")
usb.__path__ = [str(ROOT / "packages" / "usb" / "usb-host-audio" / "usb")]
sys.modules["usb"] = usb

from usb.host import audio  # noqa: E402

HUB = bytes.fromhex(
    "0902a701050100a096080b000301002000090400000001012000092401000204"
    "91000011240201010100090203000000000000001224060208030000000c0000"
    "000c000000000c2403030204040209000000112402040204030a010400000000"
    "0000000e24060504030000000c000000000c240306010100050a0000000e2406"
    "0704030000000c000000001024040802010702030000000000000008240a0907"
    "07000008240a0a07070000090401000001022004090401010101022004102401"
    "010501010000000203000000000624020103180705030d200101082501000001"
    "6400090401020101022004102401010501010000000203000000000624020102"
    "100705030dc00001082501000001640009040200000102200509040201010102"
    "2005102401060501010000000104000000000624020102100705830d60000108"
    "2501000001640009040202010102200510240106050101000000010400000000"
    "0624020103180705830d90000108250100000164000904030001030000000921"
    "1101000122380007058103400001090404000103000000092111010001222a00"
    "07058203400001"
)


class Dev:
    _id = 1

    def __init__(self, blob):
        self.blob = blob

    def configuration_descriptor(self):
        return self.blob

    def ctrl_transfer(self, request_type, request, value, index, buf, timeout):
        # A USB Audio 2.0 clock's RANGE answer: 44.1 and 48 kHz.
        answer = (2).to_bytes(2, "little")
        for rate in (44100, 48000):
            answer += rate.to_bytes(4, "little") * 2 + bytes(4)
        buf[:len(answer)] = answer
        return len(answer)


class DefaultFormatTests(unittest.TestCase):
    def test_a_speaker_whose_best_offer_is_24_bit_opens_at_16(self):
        self.assertEqual(audio._format(None, audio.Speaker, Dev(HUB)), {"bits": 16})

    def test_a_microphone_with_a_16_bit_stream_opens_at_16(self):
        self.assertEqual(audio._format(None, audio.Microphone, Dev(HUB)), {"bits": 16})

    def test_the_16_bit_stream_is_the_one_chosen(self):
        found = audio._streams(Dev(HUB))
        s = audio._uac.choose(found, audio.Speaker._direction, None, None, 16)
        self.assertEqual((s.bits, s.channels), (16, 2))

    def test_a_device_with_no_16_bit_stream_keeps_its_best_offer(self):
        streams = audio._streams
        try:
            audio._streams = lambda dev: [s for s in streams(dev) if s.bits != 16]
            self.assertEqual(audio._format(None, audio.Speaker, Dev(HUB)), {})
        finally:
            audio._streams = streams

    def test_a_format_given_is_used_as_it_is(self):
        fmt = types.SimpleNamespace(rate=44100, channels=2, bits=16)
        self.assertEqual(audio._format(fmt, audio.Speaker, Dev(HUB)), {"rate": 44100, "channels": 2, "bits": 16})


if __name__ == "__main__":
    unittest.main()
