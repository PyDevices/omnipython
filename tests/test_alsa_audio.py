# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""``audiodev.alsa_audio``: against ALSA's own ``null`` device, and a fake libasound.

The real library runs where it is installed (it is on most Linux machines and
CI runners; ALSA's ``null`` device needs no sound card). The fake one drives
the paths a quiet machine never takes: an underrun, a full ring, a card that
stops taking audio.
"""

import sys
import unittest
from unittest import mock

import _env  # noqa: F401

from audiodev import AudioFormat

try:
    from audiodev import alsa_audio

    alsa_audio._load()
    HAVE_ALSA = True
except ImportError:
    alsa_audio = None
    HAVE_ALSA = False

FMT = AudioFormat(48000, 2, 16)


@unittest.skipUnless(sys.platform.startswith("linux") and HAVE_ALSA, "needs Linux and libasound")
class NullDeviceTests(unittest.TestCase):
    def test_write_takes_every_byte_and_the_ring_reports_its_size(self):
        out = alsa_audio.pcm_out(FMT, device="null")
        self.addCleanup(out.close)
        pcm = bytes(range(256)) * 64
        self.assertEqual(out.write(pcm), len(pcm))
        self.assertGreater(out.buffer_frames, 0)
        self.assertEqual(out.xruns, 0)

    def test_the_low_profile_has_a_smaller_ring(self):
        low = alsa_audio.pcm_out(FMT, device="null", latency="low")
        normal = alsa_audio.pcm_out(FMT, device="null")
        self.addCleanup(low.close)
        self.addCleanup(normal.close)
        low.open()
        normal.open()
        self.assertLess(low.buffer_frames, normal.buffer_frames)

    def test_drain_returns_and_clear_leaves_the_output_usable(self):
        out = alsa_audio.pcm_out(FMT, device="null")
        self.addCleanup(out.close)
        out.write(bytes(4 * 1000))
        out.drain()
        out.clear()
        self.assertEqual(out.write(bytes(4 * 1000)), 4000)

    def test_capture_gives_whole_frames(self):
        inp = alsa_audio.pcm_in(AudioFormat(16000, 1, 16), device="null")
        self.addCleanup(inp.close)
        buf = bytearray(2 * 160)
        count = inp.readinto(buf)
        self.assertGreater(count, 0)
        self.assertEqual(count % 2, 0)

    def test_an_unknown_device_says_so(self):
        out = alsa_audio.pcm_out(FMT, device="no-such-device")
        with self.assertRaisesRegex(OSError, "open of 'no-such-device'"):
            out.open()

    def test_a_format_alsa_cannot_take_is_refused_before_opening(self):
        with self.assertRaises(ValueError):
            alsa_audio._format_code(AudioFormat(48000, 2, 8, signed=True, byteorder="big"))


class FakeLib:
    """libasound as a dict of functions, with a card that takes ``room`` frames."""

    def __init__(self, room=100000):
        self.room = room
        self.frames = 0
        self.script = []  # return codes handed out before writes succeed
        self.calls = []
        self.state = 2

    def functions(self):
        def call(name, fn):
            def run(*args):
                self.calls.append(name)
                return fn(*args)

            return run

        fns = {
            "snd_pcm_open": lambda h, n, s, m: h.__setitem__(slice(0, 8), (1234).to_bytes(8, "little")) or 0,
            "snd_pcm_close": lambda p: 0,
            "snd_pcm_set_params": lambda *a: 0,
            "snd_pcm_get_params": self.get_params,
            "snd_pcm_writei": self.writei,
            "snd_pcm_readi": lambda *a: 0,
            "snd_pcm_recover": lambda p, e, s: 0,
            "snd_pcm_prepare": lambda p: 0,
            "snd_pcm_start": lambda p: 0,
            "snd_pcm_drain": lambda p: 0,
            "snd_pcm_drop": lambda p: 0,
            "snd_pcm_avail": lambda p: self.room,
            "snd_pcm_state": lambda p: self.state,
            "snd_pcm_sw_params_sizeof": lambda: 16,
            "snd_pcm_sw_params_current": lambda *a: 0,
            "snd_pcm_sw_params_set_start_threshold": lambda *a: 0,
            "snd_pcm_sw_params": lambda *a: 0,
            "snd_card_next": lambda c: 0,
            "snd_strerror": lambda e: "error",
        }
        return {k: call(k, v) for k, v in fns.items()}

    def get_params(self, pcm, buf, period):
        buf[:8] = (9600).to_bytes(8, "little")
        period[:8] = (2400).to_bytes(8, "little")
        return 0

    def writei(self, pcm, data, frames):
        if self.script:
            return self.script.pop(0)
        self.frames += frames
        return frames


class FakeLibTests(unittest.TestCase):
    def setUp(self):
        if alsa_audio is None:
            self.skipTest("audiodev.alsa_audio needs ctypes or ffi")
        self.lib = FakeLib()
        for patch in (
            mock.patch.object(alsa_audio, "_lib", self.lib.functions()),
            mock.patch.object(alsa_audio, "_arg", lambda v: v),
            mock.patch.object(alsa_audio, "_sleep_ms", lambda ms: None),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.out = alsa_audio.pcm_out(FMT)
        self.addCleanup(self.out.close)

    def test_an_underrun_is_recovered_and_counted(self):
        self.lib.script = [-alsa_audio.EPIPE]
        self.assertEqual(self.out.write(bytes(400)), 400)
        self.assertEqual(self.out.xruns, 1)
        self.assertIn("snd_pcm_recover", self.lib.calls)
        self.assertEqual(self.lib.frames, 100)

    def test_a_full_ring_is_waited_out(self):
        self.lib.script = [-alsa_audio.EAGAIN] * 3
        self.assertEqual(self.out.write(bytes(400)), 400)
        self.assertEqual(self.lib.frames, 100)

    def test_a_partial_write_keeps_going_until_everything_is_taken(self):
        self.lib.script = [30, 30]
        self.assertEqual(self.out.write(bytes(400)), 400)
        self.assertEqual(self.lib.frames, 40)

    def test_a_card_that_stops_taking_audio_is_an_error_not_a_hang(self):
        clock = iter(range(0, 100000, 100))
        self.lib.script = [-alsa_audio.EAGAIN] * 1000
        with mock.patch.object(alsa_audio, "_ticks_ms", lambda: next(clock)):
            with self.assertRaisesRegex(OSError, "no write progress"):
                self.out.write(bytes(400))

    def test_a_hard_error_names_alsa(self):
        self.lib.script = [-5]
        with self.assertRaisesRegex(OSError, "ALSA write failed"):
            self.out.write(bytes(400))

    def test_queued_size_is_what_the_ring_holds(self):
        self.out.open()
        self.lib.room = 9600 - 2400
        self.lib.state = alsa_audio.STATE_RUNNING
        self.assertEqual(self.out.queued_size(), 2400 * 4)
        self.lib.state = alsa_audio.STATE_XRUN
        self.assertEqual(self.out.queued_size(), 0)

    def test_the_card_waits_for_the_prebuffer(self):
        self.out.open()
        self.assertEqual(self.out.prebuffer_bytes, 2400 * 4)
        self.assertIn("snd_pcm_sw_params_set_start_threshold", self.lib.calls)


class DevicesTests(unittest.TestCase):
    def test_the_card_list_is_read_from_proc(self):
        if alsa_audio is None:
            self.skipTest("audiodev.alsa_audio needs ctypes or ffi")
        text = (
            "00-00: MAI PCM i2s-hifi-0 : MAI PCM i2s-hifi-0 : playback 1\n"
            "02-00: bcm2835 Headphones : bcm2835 Headphones : playback 8\n"
            "03-00: USB Audio : USB Audio : playback 1 : capture 1\n"
        )
        with mock.patch("builtins.open", mock.mock_open(read_data=text)):
            found = alsa_audio.devices()
        self.assertEqual([d["name"] for d in found], ["plughw:0,0", "plughw:2,0", "plughw:3,0"])
        self.assertEqual([d["capture"] for d in found], [False, False, True])
        self.assertEqual(found[1]["description"], "bcm2835 Headphones")

    def test_no_cards_is_an_empty_list(self):
        if alsa_audio is None:
            self.skipTest("audiodev.alsa_audio needs ctypes or ffi")
        with mock.patch("builtins.open", side_effect=OSError):
            self.assertEqual(alsa_audio.devices(), [])


if __name__ == "__main__":
    unittest.main()
