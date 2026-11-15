# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Write an MP4 file of H.264 video and 16-bit PCM sound while you record.

Hand it each access unit as the encoder makes it, and each block of sound as
the microphone gives it, with the time each was captured; ``close()`` writes
the index that makes the file play::

    import mp4mux

    mp4 = mp4mux.Writer("/sd/clip.mp4", 1280, 720, fps_hint=25)
    mp4.add_video(enc.encode(frame), time.ticks_ms(), enc.keyframe)
    mp4.add_audio(pcm_block, time.ticks_ms())
    mp4.close()

Video is Annex B H.264, as ``h264enc`` and most encoders give it. The start
codes are stripped and each NAL unit is stored behind its length; the SPS and
PPS go into the track's ``avcC`` box. Frames keep the times they were given,
so a frame rate that varies plays back at the speed it was recorded.

Sound is 16-bit little-endian PCM, stored as QuickTime's ``sowt``, which
ffmpeg, VLC and Windows read. A gap in the times given is filled with silence,
so the sound stays in step with the picture when a read comes late.

The sample tables live in RAM until ``close()``: about 12 bytes a frame and 8
a block of sound, preallocated for ``max_seconds`` and grown past it. If
power is lost before ``close()``, the file has its media but no index, and
players refuse it. Pass ``fragment_ms`` to write a fragmented MP4 instead,
which plays up to its last whole fragment however it ends.

A file may pass 4 GB: its offsets then go into a ``co64`` box.
"""

import struct
from array import array

try:
    from micropython import const
except ImportError:  # CPython

    def const(x):
        return x


_VIDEO_TIMESCALE = const(90000)
_MOVIE_TIMESCALE = const(1000)
_GAP_MS = const(40)  # a sound gap longer than this is filled with silence
_NAL_SPS = const(7)
_NAL_PPS = const(8)
_NAL_AUD = const(9)
_LIMIT = 0xFFFFFFFF
_KEY_FLAGS = const(0x02000000)  # depends on no other sample
_DELTA_FLAGS = const(0x01010000)  # depends on others, not a sync sample


class _Table:
    """A growable table of big-endian 32-bit values, written out as is.

    A value past 32 bits widens the whole table to 64-bit values.
    """

    def __init__(self, capacity):
        self.buf = bytearray(4 * max(capacity, 16))
        self.n = 0
        self.width = 4
        self.fmt = ">I"

    def append(self, value):
        if value > _LIMIT and self.width == 4:
            self._widen()
        w = self.width
        if w * self.n == len(self.buf):
            self.buf.extend(bytearray(len(self.buf)))
        struct.pack_into(self.fmt, self.buf, w * self.n, value)
        self.n += 1

    def _widen(self):
        old = self.buf
        self.buf = bytearray(2 * len(old))
        for i in range(self.n):
            struct.pack_into(">Q", self.buf, 8 * i, struct.unpack_from(">I", old, 4 * i)[0])
        self.width = 8
        self.fmt = ">Q"

    def get(self, i):
        return struct.unpack_from(self.fmt, self.buf, self.width * i)[0]

    def set(self, i, value):
        struct.pack_into(self.fmt, self.buf, self.width * i, value)

    def data(self):
        return memoryview(self.buf)[: self.width * self.n]


def _box(kind, *parts):
    size = 8
    for p in parts:
        size += len(p)
    return [struct.pack(">I4s", size, kind)] + list(parts)


def _join(chunks):
    out = []
    for c in chunks:
        if isinstance(c, list):
            out.extend(c)
        else:
            out.append(c)
    return out


def _size(chunks):
    n = 0
    for c in chunks:
        n += len(c)
    return n


def _container(kind, *children):
    body = _join(children)
    return [struct.pack(">I4s", 8 + _size(body), kind)] + body


def _full(kind, version, flags, *parts):
    return _box(kind, struct.pack(">I", (version << 24) | flags), *parts)


def _rbsp(nal):
    """The NAL unit's payload with emulation-prevention bytes removed."""
    out = bytearray()
    zeros = 0
    for b in nal[1:]:
        if zeros >= 2 and b == 3:
            zeros = 0
            continue
        out.append(b)
        zeros = zeros + 1 if b == 0 else 0
    return out


class _Bits:
    def __init__(self, data):
        self.data = data
        self.pos = 0

    def bit(self):
        byte = self.data[self.pos >> 3]
        b = (byte >> (7 - (self.pos & 7))) & 1
        self.pos += 1
        return b

    def ue(self):
        zeros = 0
        while self.bit() == 0:
            zeros += 1
        v = 0
        for _ in range(zeros):
            v = (v << 1) | self.bit()
        return (1 << zeros) - 1 + v


def _avcc(sps, pps):
    """The ``avcC`` box body for one SPS and one PPS."""
    profile = sps[1]
    body = bytearray((1, profile, sps[2], sps[3], 0xFF, 0xE1))
    body += struct.pack(">H", len(sps)) + sps
    body += b"\x01" + struct.pack(">H", len(pps)) + pps
    if profile in (100, 110, 122, 144):
        # High profiles carry the chroma format and bit depths too.
        bits = _Bits(_rbsp(sps)[3:])
        bits.ue()  # seq_parameter_set_id
        chroma = bits.ue()
        if chroma == 3:
            bits.bit()  # separate_colour_plane_flag
        luma = bits.ue()
        chroma_depth = bits.ue()
        body += bytes((0xFC | chroma, 0xF8 | luma, 0xF8 | chroma_depth, 0))
    return bytes(body)


def _nals(au):
    """Yield (start, end) of each NAL unit in an Annex B access unit."""
    find = au.find
    n = len(au)
    i = find(b"\x00\x00\x01")
    while i >= 0:
        start = i + 3
        nxt = find(b"\x00\x00\x01", start)
        end = n if nxt < 0 else nxt
        while end > start and au[end - 1] == 0:
            end -= 1  # the leading zero of a four-byte start code
        if end > start:
            yield start, end
        i = nxt


def _runs(table, count):
    """Run-length encode the first ``count`` values of a `_Table` for stts."""
    out = bytearray()
    entries = 0
    if count:
        run_value = table.get(0)
        run = 1
        for i in range(1, count):
            v = table.get(i)
            if v == run_value:
                run += 1
            else:
                out += struct.pack(">II", run, run_value)
                entries += 1
                run_value = v
                run = 1
        out += struct.pack(">II", run, run_value)
        entries += 1
    return entries, out


class Writer:
    """An MP4 file being recorded.

    Args:
        path (str): Where to write it. An existing file is replaced.
        width (int): The video's width in pixels.
        height (int): The video's height in pixels.
        fps_hint (float): The frame rate you expect; it sizes the tables and
            sets the last frame's duration. The file keeps the real times.
        audio_rate (int): The sound's sample rate in Hz.
        audio_channels (int): 1 or 2.
        max_seconds (int): The length the tables are preallocated for.
        fragment_ms (int): 0 writes one index at ``close()``. More writes a
            fragmented MP4: each fragment carries its own index and is
            written once this many milliseconds have gathered, at the next
            keyframe when there is video. A recording that stops without
            ``close()`` still plays up to its last fragment. The fragment
            being gathered is held in RAM, and every track must start
            before the first fragment is written.
    """

    def __init__(self, path, width, height, fps_hint=25, audio_rate=16000, audio_channels=1, *, max_seconds=600, fragment_ms=0):
        self.width = width
        self.height = height
        self.fps_hint = fps_hint
        self.audio_rate = audio_rate
        self.audio_channels = audio_channels
        self._frame_bytes = 2 * audio_channels
        self._fragment_ms = fragment_ms
        if fragment_ms:
            max_seconds = fragment_ms // 1000 + 1
        frames = int(fps_hint * max_seconds) + 1
        self._v_sizes = _Table(frames)
        self._v_offsets = _Table(frames)
        self._v_durations = _Table(frames)
        self._v_sync = _Table(frames // 8)
        self._v_count = 0
        self._v_t0 = None
        self._v_last = None
        self._sps = None
        self._pps = None
        blocks = max_seconds * 25
        self._a_offsets = _Table(blocks)
        self._a_frames = _Table(blocks)
        self._a_total = 0
        self._a_t0 = None
        self._f = open(path, "wb")
        self.closed = False
        if fragment_ms:
            self._f.write(
                b"".join(_box(b"ftyp", b"isom", struct.pack(">I", 512), b"isomiso6avc1mp41"))
            )
            self._v_data = []  # the fragment being gathered
            self._a_data = []
            self._v_done = 0  # ticks of video in fragments already written
            self._a_done = 0  # frames of sound in fragments already written
            self._frag_start = None
            self._a_frag = 0
            self._tracks = None  # (video, audio), fixed by the first fragment
            self._t0 = 0
            self._sequence = 0
            self._v_last_dur = 0
            return
        self._f.write(
            b"".join(_box(b"ftyp", b"isom", struct.pack(">I", 512), b"isomiso2avc1mp41"))
        )
        self._mdat = self._tell()
        self._f.write(struct.pack(">I4s", 0, b"mdat"))
        self._pos = self._mdat + 8

    def _tell(self):
        return self._f.seek(0, 1)

    def _check_room(self, more):
        # One mdat box holds up to 4 GB. Past that, a new one starts, and the
        # offsets past 32 bits widen their tables to co64.
        if self._pos + more - self._mdat > _LIMIT:
            f = self._f
            f.seek(self._mdat)
            f.write(struct.pack(">I", self._pos - self._mdat))
            f.seek(self._pos)
            f.write(struct.pack(">I4s", 0, b"mdat"))
            self._mdat = self._pos
            self._pos += 8

    # -- video ----------------------------------------------------------------

    def add_video(self, access_unit, pts_ms, keyframe):
        """Add one access unit of Annex B H.264.

        Frames before the first keyframe that carries an SPS and a PPS are
        dropped, since nothing could decode them.

        Args:
            access_unit (bytes): One frame's NAL units, with start codes.
            pts_ms (int): When it was captured, in milliseconds, on the same
                clock as the sound's.
            keyframe (bool): True for an IDR frame.

        Returns:
            bool: True when the frame was written.
        """
        raw = access_unit
        if not isinstance(raw, (bytes, bytearray)):
            raw = bytes(raw)
        keep = []
        for start, end in _nals(raw):
            kind = raw[start] & 0x1F
            if kind == _NAL_SPS:
                if self._sps is None:
                    self._sps = bytes(raw[start:end])
                continue
            if kind == _NAL_PPS:
                if self._pps is None:
                    self._pps = bytes(raw[start:end])
                continue
            if kind == _NAL_AUD:
                continue
            keep.append((start, end))
        if self._v_count == 0 and not (keyframe and self._sps and self._pps):
            return False
        if not keep:
            return False
        size = 0
        for start, end in keep:
            size += 4 + end - start
        if self._fragment_ms:
            return self._gather_video(raw, keep, size, pts_ms, keyframe)
        self._check_room(size)
        f = self._f
        mv = memoryview(raw)
        for start, end in keep:
            f.write(struct.pack(">I", end - start))
            f.write(mv[start:end])
        if self._v_count:
            self._v_durations.append(max(1, int((pts_ms - self._v_last) * 90)))
        else:
            self._v_t0 = pts_ms
        self._v_last = pts_ms
        self._v_offsets.append(self._pos)
        self._v_sizes.append(size)
        self._v_count += 1
        if keyframe:
            self._v_sync.append(self._v_count)
        self._pos += size
        return True

    def _gather_video(self, raw, keep, size, pts_ms, keyframe):
        if self._tracks is not None and not self._tracks[0]:
            raise ValueError("the first fragment had no video, so this file has none: start the video sooner")
        if self._v_count:
            self._v_last_dur = max(1, int((pts_ms - self._v_last) * 90))
            self._v_durations.append(self._v_last_dur)
            if keyframe and pts_ms - self._frag_start >= self._fragment_ms:
                self._cut()
        else:
            self._v_t0 = pts_ms
        if self._frag_start is None:
            self._frag_start = pts_ms
        self._v_last = pts_ms
        au = bytearray(size)
        mv = memoryview(raw)
        at = 0
        for start, end in keep:
            struct.pack_into(">I", au, at, end - start)
            au[at + 4 : at + 4 + end - start] = mv[start:end]
            at += 4 + end - start
        self._v_data.append(au)
        self._v_sizes.append(size)
        self._v_sync.append(_KEY_FLAGS if keyframe else _DELTA_FLAGS)
        self._v_count += 1
        return True

    # -- sound ----------------------------------------------------------------

    def add_audio(self, pcm, pts_ms):
        """Add a block of 16-bit little-endian PCM, ``audio_channels``
        interleaved.

        Args:
            pcm (bytes): Whole frames of samples: bytes, a bytearray, a
                memoryview of bytes, or an ``array("h")``.
            pts_ms (int): When its first sample was captured, in
                milliseconds, on the same clock as the video's.
        """
        fb = self._frame_bytes
        n = len(pcm)
        if isinstance(pcm, array):
            n *= 2  # 16-bit samples; MicroPython's array has no itemsize
        if n % fb:
            raise ValueError("pcm must be whole frames of %d bytes" % fb)
        if not n:
            return
        silence = 0
        if self._a_t0 is None:
            self._a_t0 = pts_ms
        else:
            due = self._a_t0 + self._a_total * 1000 // self.audio_rate
            if pts_ms - due > _GAP_MS:
                silence = (pts_ms - due) * self.audio_rate // 1000
        if self._fragment_ms:
            self._gather_audio(pcm, n, silence, pts_ms)
            return
        self._check_room(silence * fb + n)
        offset = self._pos
        if silence:
            zeros = bytes(fb * min(silence, 1024))
            left = silence
            while left:
                k = min(left, 1024)
                self._f.write(zeros if k == 1024 else zeros[: k * fb])
                left -= k
        self._f.write(pcm)
        frames = silence + n // fb
        self._a_offsets.append(offset)
        self._a_frames.append(frames)
        self._a_total += frames
        self._pos += fb * frames

    def _gather_audio(self, pcm, n, silence, pts_ms):
        if self._tracks is not None and not self._tracks[1]:
            raise ValueError("the first fragment had no sound, so this file has none: start the sound sooner")
        fb = self._frame_bytes
        if silence:
            self._a_data.append(bytes(silence * fb))
        self._a_data.append(bytes(pcm))
        frames = silence + n // fb
        self._a_frames.append(frames)
        self._a_total += frames
        self._a_frag += frames
        if self._frag_start is None:
            self._frag_start = pts_ms
        if not self._v_count and self._a_frag * 1000 >= self._fragment_ms * self.audio_rate:
            self._cut()

    def _cut(self):
        """Write the gathered samples as one fragment: a moof, then its mdat."""
        if self._tracks is None:
            self._tracks = (self._v_count > 0, self._a_total > 0)
            t0, _, _ = self._spans()
            self._t0 = t0
            for chunk in self._moov():
                self._f.write(chunk)
        v_n = len(self._v_data)
        if not v_n and not self._a_frag:
            return
        self._sequence += 1
        v_bytes = 0
        for d in self._v_data:
            v_bytes += len(d)
        a_bytes = self._a_frag * self._frame_bytes
        if 8 + v_bytes + a_bytes > _LIMIT:
            raise OSError("a fragment holds up to 4 GB: make fragment_ms shorter")
        # The trun data offsets count from the moof's start, so its size goes
        # in first: build it once with zero offsets, then again with real ones.
        moof = self._moof(0, 0)
        size = _size(moof)
        moof = self._moof(size + 8, size + 8 + v_bytes)
        # The moof goes down as a free box and is named once its mdat is
        # written, so a fragment cut short by a power loss is skipped
        # rather than making the whole file unreadable.
        f = self._f
        at = self._tell()
        f.write(struct.pack(">I4s", size, b"free"))
        for chunk in moof[1:]:
            f.write(chunk)
        f.write(struct.pack(">I4s", 8 + v_bytes + a_bytes, b"mdat"))
        for d in self._v_data:
            f.write(d)
        for d in self._a_data:
            f.write(d)
        f.flush()
        end = self._tell()
        f.seek(at + 4)
        f.write(b"moof")
        f.seek(end)
        f.flush()
        for i in range(v_n):
            self._v_done += self._v_durations.get(i)
        self._a_done += self._a_frag
        # The frame still waiting for its duration carries over.
        self._v_data = []
        self._a_data = []
        self._a_frag = 0
        self._v_sizes.n = 0
        self._v_sync.n = 0
        self._v_durations.n = 0
        self._a_frames.n = 0
        self._frag_start = None

    def _moof(self, v_offset, a_offset):
        trafs = []
        track_id = 1
        if self._tracks[0]:
            n = len(self._v_data)
            if n:
                entries = bytearray(12 * n)
                for i in range(n):
                    struct.pack_into(
                        ">III", entries, 12 * i,
                        self._v_durations.get(i), self._v_sizes.get(i), self._v_sync.get(i),
                    )
                start = (self._v_t0 - self._t0) * 90 + self._v_done
                trafs.append(_container(
                    b"traf",
                    _full(b"tfhd", 0, 0x020000, struct.pack(">I", track_id)),
                    _full(b"tfdt", 1, 0, struct.pack(">Q", start)),
                    _full(b"trun", 0, 0x000701, struct.pack(">Ii", n, v_offset), entries),
                ))
            track_id += 1
        if self._tracks[1]:
            n = self._a_frames.n
            if n:
                entries = bytearray(8 * n)
                fb = self._frame_bytes
                for i in range(n):
                    k = self._a_frames.get(i)
                    struct.pack_into(">II", entries, 8 * i, k, k * fb)
                start = (self._a_t0 - self._t0) * self.audio_rate // 1000 + self._a_done
                trafs.append(_container(
                    b"traf",
                    _full(b"tfhd", 0, 0x020020, struct.pack(">II", track_id, _KEY_FLAGS)),
                    _full(b"tfdt", 1, 0, struct.pack(">Q", start)),
                    _full(b"trun", 0, 0x000301, struct.pack(">Ii", n, a_offset), entries),
                ))
        mfhd = _full(b"mfhd", 0, 0, struct.pack(">I", self._sequence))
        return _container(b"moof", mfhd, *trafs)

    def flush(self):
        """Push what has been written so far to the file system."""
        self._f.flush()

    # -- the index ------------------------------------------------------------

    def close(self):
        """Write the index and close the file. A file closed with no video
        and no sound holds no tracks."""
        if self.closed:
            return
        self.closed = True
        f = self._f
        if self._fragment_ms:
            try:
                if self._v_count:
                    self._v_durations.append(self._last_duration())
                self._cut()
            finally:
                f.close()
            return
        try:
            f.seek(self._mdat)
            f.write(struct.pack(">I", self._pos - self._mdat))
            f.seek(self._pos)
            for chunk in self._moov():
                f.write(chunk)
        finally:
            f.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    @property
    def duration_ms(self):
        """The length of what has been recorded so far."""
        t0, video, audio = self._spans()
        end = 0
        for start, length in (video, audio):
            if length:
                end = max(end, start - t0 + length)
        return end

    def _video_ms(self):
        if not self._v_count:
            return 0
        ticks = 0
        for i in range(self._v_durations.n):
            ticks += self._v_durations.get(i)
        if self._fragment_ms:
            ticks += self._v_done
        return (ticks + self._last_duration()) // 90

    def _last_duration(self):
        if self._v_durations.n:
            return self._v_durations.get(self._v_durations.n - 1)
        if self._fragment_ms and self._v_last_dur:
            return self._v_last_dur
        return int(_VIDEO_TIMESCALE / self.fps_hint)

    def _spans(self):
        video = (self._v_t0 or 0, self._video_ms())
        audio = (self._a_t0 or 0, self._a_total * 1000 // self.audio_rate)
        starts = [s for s, n in (video, audio) if n]
        t0 = min(starts) if starts else 0
        return t0, video, audio

    def _moov(self):
        if self._fragment_ms:
            return self._fragmented_moov()
        t0, video, audio = self._spans()
        movie_ms = 0
        traks = []
        track_id = 1
        if self._v_count:
            self._v_durations.append(self._last_duration())
            traks.append(self._video_trak(track_id, video[0] - t0, video[1]))
            movie_ms = max(movie_ms, video[0] - t0 + video[1])
            track_id += 1
        if self._a_total:
            traks.append(self._audio_trak(track_id, audio[0] - t0, audio[1]))
            movie_ms = max(movie_ms, audio[0] - t0 + audio[1])
            track_id += 1
        mvhd = _full(
            b"mvhd", 0, 0,
            struct.pack(">IIII", 0, 0, _MOVIE_TIMESCALE, movie_ms),
            struct.pack(">IH", 0x00010000, 0x0100) + bytes(10),
            _MATRIX,
            bytes(24),
            struct.pack(">I", track_id),
        )
        return _container(b"moov", mvhd, *traks)

    def _fragmented_moov(self):
        """The moov of a fragmented file: the tracks' descriptions, no samples."""
        traks = []
        trexs = []
        track_id = 1
        for has, trak in ((self._tracks[0], self._video_trak), (self._tracks[1], self._audio_trak)):
            if has:
                traks.append(trak(track_id, 0, 0))
                flags = _DELTA_FLAGS if trak == self._video_trak else _KEY_FLAGS
                trexs.append(_full(b"trex", 0, 0, struct.pack(">IIIII", track_id, 1, 0, 0, flags)))
                track_id += 1
        mvhd = _full(
            b"mvhd", 0, 0,
            struct.pack(">IIII", 0, 0, _MOVIE_TIMESCALE, 0),
            struct.pack(">IH", 0x00010000, 0x0100) + bytes(10),
            _MATRIX,
            bytes(24),
            struct.pack(">I", track_id),
        )
        return _container(b"moov", mvhd, *traks, _container(b"mvex", *trexs))

    @staticmethod
    def _offsets(table, count):
        """``stco``, or ``co64`` once an offset has passed 32 bits."""
        kind = b"co64" if table.width == 8 else b"stco"
        return _full(kind, 0, 0, struct.pack(">I", count), table.data())

    def _empty_stbl(self, stsd):
        return _container(
            b"stbl", stsd,
            _full(b"stts", 0, 0, bytes(4)),
            _full(b"stsc", 0, 0, bytes(4)),
            _full(b"stsz", 0, 0, bytes(8)),
            _full(b"stco", 0, 0, bytes(4)),
        )

    def _tkhd(self, track_id, duration_ms, audio):
        return _full(
            b"tkhd", 0, 3,
            struct.pack(">IIIII", 0, 0, track_id, 0, duration_ms),
            bytes(8),
            struct.pack(">HHHH", 0, 0, 0x0100 if audio else 0, 0),
            _MATRIX,
            struct.pack(">II", 0 if audio else self.width << 16, 0 if audio else self.height << 16),
        )

    @staticmethod
    def _edts(offset_ms, duration_ms):
        if offset_ms <= 0:
            return []
        elst = _full(
            b"elst", 0, 0,
            struct.pack(">I", 2),
            struct.pack(">IiI", offset_ms, -1, 0x00010000),
            struct.pack(">IiI", duration_ms, 0, 0x00010000),
        )
        return _container(b"edts", elst)

    @staticmethod
    def _mdhd(timescale, duration):
        return _full(b"mdhd", 0, 0, struct.pack(">IIIIHH", 0, 0, timescale, duration, 0x55C4, 0))

    @staticmethod
    def _hdlr(kind, name):
        return _full(b"hdlr", 0, 0, struct.pack(">I4s", 0, kind), bytes(12), name + b"\x00")

    @staticmethod
    def _dinf():
        url = _full(b"url ", 0, 1)
        return _container(b"dinf", _container(b"dref", [struct.pack(">II", 0, 1)], url))

    def _video_trak(self, track_id, offset_ms, duration_ms):
        n = self._v_count
        ticks = 0
        if not self._fragment_ms:
            for i in range(n):
                ticks += self._v_durations.get(i)
        avcc = _box(b"avcC", _avcc(self._sps, self._pps))
        avc1 = _box(
            b"avc1",
            bytes(6) + struct.pack(">H", 1),
            bytes(16),
            struct.pack(">HHIIIH", self.width, self.height, 0x00480000, 0x00480000, 0, 1),
            bytes(32),
            struct.pack(">Hh", 0x0018, -1),
            b"".join(avcc),
        )
        stsd = _full(b"stsd", 0, 0, struct.pack(">I", 1), b"".join(avc1))
        if self._fragment_ms:
            stbl = self._empty_stbl(stsd)
        else:
            entries, runs = _runs(self._v_durations, n)
            stbl = _container(
                b"stbl",
                stsd,
                _full(b"stts", 0, 0, struct.pack(">I", entries), runs),
                _full(b"stss", 0, 0, struct.pack(">I", self._v_sync.n), self._v_sync.data()),
                _full(b"stsc", 0, 0, struct.pack(">IIII", 1, 1, 1, 1)),
                _full(b"stsz", 0, 0, struct.pack(">II", 0, n), self._v_sizes.data()),
                self._offsets(self._v_offsets, n),
            )
        vmhd = _full(b"vmhd", 0, 1, bytes(8))
        minf = _container(b"minf", vmhd, self._dinf(), stbl)
        mdia = _container(b"mdia", self._mdhd(_VIDEO_TIMESCALE, ticks), self._hdlr(b"vide", b"VideoHandler"), minf)
        return _container(b"trak", self._tkhd(track_id, max(offset_ms, 0) + duration_ms, False), self._edts(offset_ms, duration_ms), mdia)

    def _audio_trak(self, track_id, offset_ms, duration_ms):
        blocks = self._a_offsets.n
        sowt = _box(
            b"sowt",
            bytes(6) + struct.pack(">H", 1),
            bytes(8),
            struct.pack(">HHHH", self.audio_channels, 16, 0, 0),
            struct.pack(">I", self.audio_rate << 16),
        )
        # One stsc entry per run of blocks holding the same number of frames.
        stsc = bytearray()
        entries = 0
        last = None
        for i in range(blocks):
            k = self._a_frames.get(i)
            if k != last:
                stsc += struct.pack(">III", i + 1, k, 1)
                entries += 1
                last = k
        stsd = _full(b"stsd", 0, 0, struct.pack(">I", 1), b"".join(sowt))
        if self._fragment_ms:
            stbl = self._empty_stbl(stsd)
        else:
            stbl = _container(
                b"stbl",
                stsd,
                _full(b"stts", 0, 0, struct.pack(">III", 1, self._a_total, 1)),
                _full(b"stsc", 0, 0, struct.pack(">I", entries), stsc),
                _full(b"stsz", 0, 0, struct.pack(">II", self._frame_bytes, self._a_total)),
                self._offsets(self._a_offsets, blocks),
            )
        smhd = _full(b"smhd", 0, 0, bytes(4))
        minf = _container(b"minf", smhd, self._dinf(), stbl)
        total = 0 if self._fragment_ms else self._a_total
        mdia = _container(b"mdia", self._mdhd(self.audio_rate, total), self._hdlr(b"soun", b"SoundHandler"), minf)
        return _container(b"trak", self._tkhd(track_id, max(offset_ms, 0) + duration_ms, True), self._edts(offset_ms, duration_ms), mdia)


# The identity transform, in 16.16 and 2.30 fixed point.
_MATRIX = struct.pack(">9I", 0x00010000, 0, 0, 0, 0x00010000, 0, 0, 0, 0x40000000)
