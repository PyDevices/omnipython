# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""mp4mux's files, read back by ffprobe and decoded by ffmpeg.

ffmpeg makes the H.264 (baseline, as the ESP32-P4's encoder gives, and high)
and a 440 Hz sine; tests/mp4mux_file.py muxes them on CPython and
on unix MicroPython with frame times that vary and a hole in the sound.
"""

import hashlib
import json
import struct
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from array import array

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _mprun  # noqa: E402

MUX = os.path.join(HERE, "mp4mux_file.py")
LIB = os.path.join(os.path.dirname(HERE), "lib")

FRAMES = 100
FRAME_MS = (30, 40, 50)
RATE = 16000



# Two recordings made from bytes written here, so their files don't depend on
# the encoder installed. The default output is pinned byte for byte: recorders
# in the field write it, and a new option must not change it.
_SPS_BASELINE = b"\x67\x42\xc0\x1e" + bytes(range(16, 40))
_SPS_HIGH = b"\x67\x64\x00\x1f\xac" + bytes(range(40, 60))  # 4:2:0, 8-bit
_PPS = b"\x68\xce\x3c\x80"


def _access_unit(i, sps, keyframe):
    start = b"\x00\x00\x00\x01"
    au = start + b"\x09\xf0"
    if keyframe:
        au += start + sps + start + _PPS
    slice_ = bytes((0x65 if keyframe else 0x41,)) + bytes((i * 7 + k) & 0xFF for k in range(50 + 13 * (i % 5)))
    return au + b"\x00\x00\x01" + slice_


def _pcm(n, channels, seed):
    return bytes((seed + 3 * k) & 0xFF for k in range(2 * channels * n))


def _write_baseline(mp4mux, path, **options):
    """Video from 0 ms at varying frame times; sound from 100 ms with a hole."""
    mp4 = mp4mux.Writer(path, 320, 240, 25, audio_rate=16000, audio_channels=1, **options)
    mp4.add_video(_access_unit(0, _SPS_BASELINE, False), 0, False)  # dropped: no keyframe yet
    t = 0
    for i in range(60):
        mp4.add_video(_access_unit(i, _SPS_BASELINE, i % 20 == 0), t, i % 20 == 0)
        t += (30, 40, 50)[i % 3]
    for k, ms in enumerate(range(100, t, 20)):
        if not 1000 <= ms < 1200:
            mp4.add_audio(_pcm(320, 1, k), ms)
    mp4.close()


def _write_high(mp4mux, path, **options):
    """Stereo 48 kHz sound from 0 ms, video from 250 ms at a steady 25 fps."""
    mp4 = mp4mux.Writer(path, 640, 360, 25, audio_rate=48000, audio_channels=2, max_seconds=1, **options)
    for k in range(150):
        mp4.add_audio(array("h", _pcm(480, 2, k)), k * 10)
        if k >= 25 and k % 4 == 1:
            i = (k - 25) // 4
            mp4.add_video(_access_unit(i, _SPS_HIGH, i % 12 == 0), k * 10, i % 12 == 0)
    mp4.close()


DEFAULT_FILES = {"baseline": _write_baseline, "high": _write_high}


def _run(*args):
    return subprocess.run(args, capture_output=True, text=True, timeout=120, check=True)


def _boxes(path):
    """The file's top-level boxes, as (offset, kind, size)."""
    out = []
    with open(path, "rb") as f:
        end = f.seek(0, 2)
        pos = 0
        while pos < end:
            f.seek(pos)
            size, kind = struct.unpack(">I4s", f.read(8))
            out.append((pos, kind, size))
            pos += size
    return out


def _moov(path):
    for pos, kind, size in _boxes(path):
        if kind == b"moov":
            with open(path, "rb") as f:
                f.seek(pos)
                return f.read(size)
    raise AssertionError("no moov")


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "needs ffmpeg and ffprobe")
class TestMp4mux(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="mp4mux-")
        cls.pcm = os.path.join(cls.tmp, "in.pcm")
        _run("ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000",
             "-t", "5", "-f", "s16le", "-ac", "1", cls.pcm)
        cls.h264 = {}
        for profile in ("baseline", "high"):
            path = os.path.join(cls.tmp, profile + ".h264")
            _run("ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25",
                 "-frames:v", str(FRAMES), "-c:v", "libx264", "-profile:v", profile, "-bf", "0",
                 "-pix_fmt", "yuv420p", "-g", "25", "-x264-params", "aud=1",
                 "-bsf:v", "h264_mp4toannexb", "-f", "h264", path)
            cls.h264[profile] = path

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _check(self, interpreter, profile, *options):
        name = "-".join((os.path.basename(interpreter), profile) + options)
        out = os.path.join(self.tmp, name + ".mp4")
        _run(interpreter, MUX, self.h264[profile], self.pcm, out, *options)

        probe = json.loads(_run("ffprobe", "-v", "error", "-show_streams", "-of", "json", out).stdout)
        video, audio = probe["streams"]
        self.assertEqual(video["codec_name"], "h264")
        self.assertEqual((video["width"], video["height"]), (320, 240))
        if not options:
            self.assertEqual(int(video["nb_frames"]), FRAMES)
        self.assertEqual(audio["codec_name"], "pcm_s16le")
        self.assertEqual((int(audio["sample_rate"]), audio["channels"]), (RATE, 1))
        self.assertAlmostEqual(float(audio["start_time"]), 0.1, places=3)

        # Every frame keeps the time it was given.
        frames = json.loads(_run("ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
                                 "packet=pts_time,flags", "-of", "json", out).stdout)["packets"]
        want, t = [], 0
        for i in range(FRAMES):
            want.append(t)
            t += FRAME_MS[i % 3]
        self.assertEqual(len(frames), FRAMES)
        self.assertEqual([round(float(p["pts_time"]) * 1000) for p in frames], want)
        self.assertEqual([i for i, p in enumerate(frames) if "K" in p["flags"]], list(range(0, FRAMES, 25)))

        # The whole file decodes without a complaint.
        decode = subprocess.run(["ffmpeg", "-v", "error", "-i", out, "-f", "null", "-"],
                                capture_output=True, text=True, timeout=120)
        self.assertEqual((decode.returncode, decode.stderr), (0, ""))

        # The hole at 1.0..1.2 s is silence, and the sound either side of it isn't.
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", out, "-map", "0:a", "-f", "s16le", "-"],
                             capture_output=True, timeout=120, check=True).stdout
        samples = array("h", raw)
        at = lambda ms: (ms - 100) * RATE // 1000  # noqa: E731
        self.assertEqual(max(abs(s) for s in samples[at(1005) : at(1195)]), 0)
        self.assertGreater(max(abs(s) for s in samples[at(900) : at(995)]), 2000)  # ffmpeg's sine peaks at 4095
        self.assertGreater(max(abs(s) for s in samples[at(1205) : at(1300)]), 2000)  # ffmpeg's sine peaks at 4095
        self.assertEqual(len(samples), at(4000))  # 20 ms blocks from 100 ms while t < 3990
        return out

    def _check_fragmented(self, interpreter):
        out = self._check(interpreter, "baseline", "500")
        kinds = [kind for _, kind, _ in _boxes(out)]
        # A moov with no samples, then a moof and its mdat per keyframe.
        self.assertEqual(kinds, [b"ftyp", b"moov"] + [b"moof", b"mdat"] * 4)
        moov = _moov(out)
        self.assertIn(b"mvex", moov)
        self.assertEqual(moov.count(b"trex"), 2)

        # Cut short anywhere in its last fragment, as by a power loss, the
        # file still plays up to the fragment before. Until its mdat is
        # written, a fragment's moof is a free box.
        with open(out, "rb") as f:
            data = bytearray(f.read())
        last_moof = [pos for pos, kind, _ in _boxes(out) if kind == b"moof"][-1]
        data[last_moof + 4 : last_moof + 8] = b"free"
        cut = os.path.join(self.tmp, "cut.mp4")
        for keep in (8, 100, len(data) - last_moof - 1):
            with self.subTest(keep=keep):
                with open(cut, "wb") as f:
                    f.write(data[: last_moof + keep])
                frames = _run("ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
                              "packet=pts_time", "-of", "csv=p=0", cut).stdout.split()
                self.assertEqual(len(frames), 75)
                decode = subprocess.run(["ffmpeg", "-v", "error", "-i", cut, "-f", "null", "-"],
                                        capture_output=True, text=True, timeout=120)
                self.assertEqual((decode.returncode, decode.stderr), (0, ""))

    def _check_past_4gb(self, interpreter):
        # A sparse hole puts the media's end past 4 GB without writing it.
        skip = (1 << 32) - 30000
        try:
            out = self._check(interpreter, "baseline", "0", str(skip))
            mdats = [(pos, size) for pos, kind, size in _boxes(out) if kind == b"mdat"]
            self.assertEqual(len(mdats), 2)  # one mdat box holds up to 4 GB
            self.assertGreater(mdats[1][0] + mdats[1][1], 1 << 32)
            moov = _moov(out)
            self.assertEqual((moov.count(b"co64"), moov.count(b"stco")), (2, 0))
        finally:
            for name in os.listdir(self.tmp):
                if name.endswith(".mp4"):
                    os.remove(os.path.join(self.tmp, name))

    def test_cpython(self):
        for profile in self.h264:
            with self.subTest(profile=profile):
                self._check(sys.executable, profile)

    def test_micropython(self):
        _mprun.need_micropython(self)
        for profile in self.h264:
            with self.subTest(profile=profile):
                self._check(_mprun.micropython(), profile)

    def test_fragmented_cpython(self):
        self._check_fragmented(sys.executable)

    def test_fragmented_micropython(self):
        _mprun.need_micropython(self)
        self._check_fragmented(_mprun.micropython())

    def test_past_4gb_cpython(self):
        self._check_past_4gb(sys.executable)

    def test_past_4gb_micropython(self):
        _mprun.need_micropython(self)
        self._check_past_4gb(_mprun.micropython())


class TestDefaultBytes(unittest.TestCase):
    """Without options, the writer's files stay exactly what they were."""

    PINNED = {
        "baseline": (80971, "7efbb93885d5ace0e31af822d52c1f16db6228736a6f35993d8bb7eb3d8fdba1"),
        "high": (292533, "f27ba2c2201d67abc61b29f908cda8fbaf97c816deced63631d89e07ad5237d6"),
    }

    def setUp(self):
        sys.path.insert(0, LIB)
        import mp4mux

        self.mp4mux = mp4mux
        self.path = tempfile.mktemp(suffix=".mp4")

    def tearDown(self):
        sys.path.remove(LIB)
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_default_files_are_byte_identical(self):
        for name, write in DEFAULT_FILES.items():
            with self.subTest(name):
                write(self.mp4mux, self.path)
                with open(self.path, "rb") as f:
                    data = f.read()
                self.assertEqual((len(data), hashlib.sha256(data).hexdigest()), self.PINNED[name])


class TestWriter(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, LIB)
        import mp4mux

        self.mp4mux = mp4mux
        self.path = tempfile.mktemp(suffix=".mp4")

    def tearDown(self):
        sys.path.remove(LIB)
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_frames_before_the_first_keyframe_are_dropped(self):
        with self.mp4mux.Writer(self.path, 16, 16) as mp4:
            self.assertFalse(mp4.add_video(b"\x00\x00\x00\x01\x41\x9a", 0, False))

    def test_an_array_of_samples_counts_as_its_bytes(self):
        with self.mp4mux.Writer(self.path, 16, 16) as mp4:
            mp4.add_audio(array("h", bytes(640)), 0)
            self.assertEqual(mp4.duration_ms, 20)

    def test_a_track_must_start_in_the_first_fragment(self):
        with self.mp4mux.Writer(self.path, 16, 16, fragment_ms=100) as mp4:
            for k in range(10):
                mp4.add_audio(bytes(640), 20 * k)
            with self.assertRaises(ValueError):
                mp4.add_video(_access_unit(0, _SPS_BASELINE, True), 200, True)

    def test_fragments_write_no_index_at_close(self):
        with self.mp4mux.Writer(self.path, 16, 16, fragment_ms=100) as mp4:
            for k in range(10):
                mp4.add_audio(bytes(640), 20 * k)
        self.assertEqual([kind for _, kind, _ in _boxes(self.path)], [b"ftyp", b"moov"] + [b"moof", b"mdat"] * 2)

    def test_pcm_must_be_whole_frames(self):
        with self.mp4mux.Writer(self.path, 16, 16, audio_channels=2) as mp4:
            with self.assertRaises(ValueError):
                mp4.add_audio(b"\x00\x00\x00", 0)


if __name__ == "__main__":
    unittest.main()
