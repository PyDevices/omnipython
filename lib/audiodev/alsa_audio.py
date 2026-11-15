# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""ALSA PCM backend for Linux, straight to ``libasound`` with no SDL or pygame.

Playback and capture use ALSA's own ring buffer in non-blocking mode: a write
takes what fits and waits a little for the rest, and ``queued_size()`` is what
the sound card still holds. There is no thread and no callback into Python.
It runs on CPython (through ``ctypes``) and on the unix MicroPython and
CircuitPython builds that have ``ffi``. Import fails unless ``libasound`` loads.

``device`` is any name ALSA's ``snd_pcm_open`` takes: ``"default"``, the
sound server's plug-in, when it is left out, or a card such as
``"plughw:2,0"``. `devices` lists the cards the kernel has.
"""

try:
    import asyncio
except ImportError:  # pragma: no cover
    try:
        import uasyncio as asyncio
    except ImportError:
        asyncio = None

import time

from audiodev import AudioFormat, PCMInput, PCMOutput, check_latency

try:
    import ctypes as _ctypes
except ImportError:  # unix MicroPython and CircuitPython
    _ctypes = None
    import ffi as _ffi

# Return type, then one letter per argument: the same letters ``ffi`` takes
# (i int, I unsigned, l long, L unsigned long, p pointer or buffer, s string).
_SIGNATURES = {
    "snd_pcm_open": ("i", "psii"),
    "snd_pcm_close": ("i", "p"),
    "snd_pcm_set_params": ("i", "piiIIiI"),
    "snd_pcm_get_params": ("i", "ppp"),
    "snd_pcm_writei": ("l", "ppL"),
    "snd_pcm_readi": ("l", "ppL"),
    "snd_pcm_recover": ("i", "pii"),
    "snd_pcm_prepare": ("i", "p"),
    "snd_pcm_start": ("i", "p"),
    "snd_pcm_drain": ("i", "p"),
    "snd_pcm_drop": ("i", "p"),
    "snd_pcm_avail": ("l", "p"),
    "snd_pcm_state": ("i", "p"),
    "snd_pcm_sw_params_sizeof": ("L", ""),
    "snd_pcm_sw_params_current": ("i", "pp"),
    "snd_pcm_sw_params_set_start_threshold": ("i", "ppL"),
    "snd_pcm_sw_params": ("i", "pp"),
    "snd_card_next": ("i", "p"),
    "snd_strerror": ("s", "i"),
}

_CTYPES = {}  # filled on first use: letter -> ctypes type

# snd_pcm_format_t, by (bits, signed, byteorder).
_FORMATS = {
    (8, True, "little"): 0,
    (8, False, "little"): 1,
    (16, True, "little"): 2,
    (16, True, "big"): 3,
    (16, False, "little"): 4,
    (16, False, "big"): 5,
    (32, True, "little"): 10,
    (32, True, "big"): 11,
    (32, False, "little"): 12,
    (32, False, "big"): 13,
}

STREAM_PLAYBACK = 0
STREAM_CAPTURE = 1
NONBLOCK = 1
ACCESS_RW_INTERLEAVED = 3

# snd_pcm_state_t values the backend acts on.
STATE_PREPARED = 2
STATE_RUNNING = 3
STATE_XRUN = 4
STATE_DRAINING = 5

EINTR = 4
EAGAIN = 11
EPIPE = 32
ESTRPIPE = 86

WRITE_WAIT_MS = 500
DRAIN_WAIT_MS = 2000

# (ring buffer in microseconds, milliseconds queued before the card starts).
_PLAY_PROFILES = {
    None: (200000, 50),
    "buffered": (200000, 50),
    "low": (40000, 10),
}
_CAPTURE_LATENCY_US = {None: 200000, "buffered": 200000, "low": 40000}

_lib = None


def _load():
    """Open ``libasound`` once and return its functions by name."""
    global _lib
    if _lib is not None:
        return _lib
    functions = {}
    if _ctypes is not None:
        if not _CTYPES:
            _CTYPES.update(
                i=_ctypes.c_int,
                I=_ctypes.c_uint,
                l=_ctypes.c_long,
                L=_ctypes.c_ulong,
                p=_ctypes.c_void_p,
                s=_ctypes.c_char_p,
            )
        try:
            lib = _ctypes.CDLL("libasound.so.2")
        except OSError as exc:
            raise ImportError("libasound is not installed: %s" % exc) from exc
        for name, (ret, args) in _SIGNATURES.items():
            func = getattr(lib, name)
            func.restype = _CTYPES[ret]
            func.argtypes = [_CTYPES[a] for a in args]
            functions[name] = func
    else:
        try:
            lib = _ffi.open("libasound.so.2")
        except OSError as exc:
            raise ImportError("libasound is not installed: %s" % exc) from exc
        for name, (ret, args) in _SIGNATURES.items():
            functions[name] = lib.func(ret, name, args)
    _lib = functions
    return functions


def _arg(value):
    """What ``ctypes`` needs for a buffer argument; ``ffi`` takes it as is."""
    if _ctypes is not None and isinstance(value, bytearray):
        return (_ctypes.c_char * len(value)).from_buffer(value)
    return value


def _call(name, *args):
    return _load()[name](*[_arg(a) for a in args])


def _error(code):
    text = _call("snd_strerror", code)
    if isinstance(text, bytes):
        text = text.decode()
    return "%s (%d)" % (text, code)


def _check(code, what):
    if code < 0:
        raise OSError("ALSA %s failed: %s" % (what, _error(code)))
    return code


def _pointer(buf):
    return int.from_bytes(buf, "little")


def _sleep_ms(milliseconds):
    if hasattr(time, "sleep_ms"):
        time.sleep_ms(milliseconds)
    else:
        time.sleep(milliseconds / 1000)


async def _asleep_ms(milliseconds):
    await asyncio.sleep(milliseconds / 1000)


def _ticks_ms():
    if hasattr(time, "ticks_ms"):
        return time.ticks_ms()
    return int(time.monotonic() * 1000)


def _since(start):
    if hasattr(time, "ticks_diff"):
        return time.ticks_diff(_ticks_ms(), start)
    return _ticks_ms() - start


def _format_code(fmt):
    key = (fmt.bits, fmt.signed, fmt.byteorder)
    if key not in _FORMATS:
        raise ValueError("alsa_audio cannot play %r" % (fmt,))
    return _FORMATS[key]


def has_cards():
    """True when the kernel has at least one sound card."""
    card = bytearray(b"\xff\xff\xff\xff")  # -1: start from the first card
    # The card number comes back as an int: 0 or more is a card, -1 is none.
    return _call("snd_card_next", card) == 0 and card[3] < 0x80


def devices():
    """The sound cards' PCM devices, from ``/proc/asound/pcm``.

    Returns a list of dicts: ``name`` (what to pass as ``device``, such as
    ``"plughw:2,0"``), ``card``, ``device``, ``description``, and whether it
    can ``playback`` or ``capture``. It is empty where there are no cards.
    """
    try:
        with open("/proc/asound/pcm") as f:
            lines = f.read().split("\n")
    except OSError:
        return []
    found = []
    for line in lines:
        if ":" not in line:
            continue
        ident, _, rest = line.partition(":")
        card, _, dev = ident.strip().partition("-")
        parts = [p.strip() for p in rest.split(":")]
        found.append(
            {
                "name": "plughw:%d,%d" % (int(card), int(dev)),
                "card": int(card),
                "device": int(dev),
                "description": parts[1] if len(parts) > 1 else parts[0],
                "playback": any(p.startswith("playback") for p in parts),
                "capture": any(p.startswith("capture") for p in parts),
            }
        )
    return found


class _Stream:
    """One ``snd_pcm_t`` in non-blocking mode, shared by playback and capture."""

    def _open_pcm(self, stream, latency_us):
        fmt = self.format
        handle = bytearray(8)
        name = self.device_name or "default"
        # ctypes wants bytes for a C string; ffi wants str.
        cname = name.encode() if _ctypes is not None else name
        _check(_call("snd_pcm_open", handle, cname, stream, NONBLOCK), "open of %r" % name)
        self._pcm = _pointer(handle)
        try:
            _check(
                _call(
                    "snd_pcm_set_params",
                    self._pcm,
                    _format_code(fmt),
                    ACCESS_RW_INTERLEAVED,
                    fmt.channels,
                    fmt.rate,
                    1,  # let ALSA resample to what the card takes
                    latency_us,
                ),
                "set_params",
            )
            buffer_frames = bytearray(8)
            period_frames = bytearray(8)
            _check(_call("snd_pcm_get_params", self._pcm, buffer_frames, period_frames), "get_params")
            self.buffer_frames = _pointer(buffer_frames)
            self.period_frames = _pointer(period_frames)
        except BaseException:
            self._close_pcm()
            raise

    def _set_start_threshold(self, frames):
        params = bytearray(_call("snd_pcm_sw_params_sizeof"))
        _check(_call("snd_pcm_sw_params_current", self._pcm, params), "sw_params_current")
        _check(_call("snd_pcm_sw_params_set_start_threshold", self._pcm, params, frames), "start threshold")
        _check(_call("snd_pcm_sw_params", self._pcm, params), "sw_params")

    def _close_pcm(self):
        pcm, self._pcm = self._pcm, None
        if pcm:
            _call("snd_pcm_close", pcm)

    def _recover(self, code):
        """Bring the stream back after an underrun or overrun; raise if it can't."""
        if code == -EPIPE:
            self.xruns += 1
        _check(_call("snd_pcm_recover", self._pcm, code, 1), "recover")


class AlsaPCMOutput(_Stream, PCMOutput):
    def __init__(self, fmt, *, device=None, latency_us=200000, prebuffer_ms=50, poll_ms=2, session=None):
        super().__init__(fmt, session=session)
        self.device_name = device
        self.latency_us = int(latency_us)
        self.poll_ms = int(poll_ms)
        self._prebuffer_ms = int(prebuffer_ms)
        self._pcm = None
        self.buffer_frames = 0
        self.period_frames = 0
        #: Underruns the card has had since this output opened. A healthy run has none.
        self.xruns = 0

    def _open(self):
        self._open_pcm(STREAM_PLAYBACK, self.latency_us)
        threshold = max(1, self.format.rate * self._prebuffer_ms // 1000)
        threshold = min(threshold, max(1, self.buffer_frames // 2))
        try:
            self._set_start_threshold(threshold)
        except BaseException:
            self._close_pcm()
            raise
        self._prebuffer_bytes = threshold * self.format.frame_size
        self.xruns = 0

    def _close(self):
        if self._pcm:
            _call("snd_pcm_drop", self._pcm)
        self._close_pcm()

    def _queued_frames(self):
        if not self._pcm:
            return 0
        state = _call("snd_pcm_state", self._pcm)
        if state not in (STATE_PREPARED, STATE_RUNNING, STATE_DRAINING):
            return 0
        avail = _call("snd_pcm_avail", self._pcm)
        if avail < 0:
            return 0
        return max(0, self.buffer_frames - avail)

    def queued_size(self):
        return self._queued_frames() * self.format.frame_size

    def is_active(self):
        return bool(self._pcm) and _call("snd_pcm_state", self._pcm) == STATE_RUNNING and self._queued_frames() > 0

    def clear(self):
        if self._pcm:
            _call("snd_pcm_drop", self._pcm)
            _call("snd_pcm_prepare", self._pcm)

    def _write(self, buf):
        """Queue as much of *buf* as the card takes, waiting a little for room.

        Returns the bytes taken; less than all of it means the card stopped
        taking audio for ``WRITE_WAIT_MS``.
        """
        data = bytes(buf)
        size = self.format.frame_size
        frames = len(data) // size
        sent = 0
        started = _ticks_ms()
        while sent < frames:
            chunk = data[sent * size :] if sent else data
            written = _call("snd_pcm_writei", self._pcm, chunk, frames - sent)
            if written >= 0:
                sent += written
                if written:
                    started = _ticks_ms()
                    continue
            elif written == -EAGAIN:
                pass
            elif written in (-EPIPE, -ESTRPIPE, -EINTR):
                self._recover(int(written))
                continue
            else:
                raise OSError("ALSA write failed: %s" % _error(int(written)))
            if _since(started) >= WRITE_WAIT_MS:
                break
            _sleep_ms(self.poll_ms)
        return sent * size

    async def _awrite(self, buf):
        data = bytes(buf)
        sent = 0
        view = memoryview(data)
        while sent < len(data):
            taken = self._write_nowait(view[sent:])
            if taken:
                sent += taken
                continue
            await _asleep_ms(self.poll_ms)
        return len(data)

    def _write_nowait(self, view):
        """One non-blocking write, in bytes; 0 when the card has no room."""
        size = self.format.frame_size
        frames = len(view) // size
        while True:
            written = _call("snd_pcm_writei", self._pcm, bytes(view), frames)
            if written >= 0:
                return written * size
            if written == -EAGAIN:
                return 0
            if written in (-EPIPE, -ESTRPIPE, -EINTR):
                self._recover(int(written))
                continue
            raise OSError("ALSA write failed: %s" % _error(int(written)))

    def _drain(self):
        """Wait until everything queued has played."""
        if not self._pcm:
            return
        if _call("snd_pcm_state", self._pcm) == STATE_PREPARED and self._queued_frames():
            _check(_call("snd_pcm_start", self._pcm), "start")
        started = _ticks_ms()
        while True:
            code = _call("snd_pcm_drain", self._pcm)
            if code == 0:
                break
            if code == -EAGAIN and _since(started) < DRAIN_WAIT_MS:
                _sleep_ms(self.poll_ms)
                continue
            if code == -EAGAIN:
                break  # still draining after DRAIN_WAIT_MS: the card is not consuming
            if code == -EPIPE:
                break
            _check(code, "drain")
        _call("snd_pcm_prepare", self._pcm)

    async def _adrain(self):
        while self.queued_size() and _call("snd_pcm_state", self._pcm) == STATE_RUNNING:
            await _asleep_ms(self.poll_ms)
        self._drain()


class AlsaPCMInput(_Stream, PCMInput):
    def __init__(self, fmt, *, device=None, latency_us=200000, poll_ms=2, session=None):
        super().__init__(fmt, session=session)
        self.device_name = device
        self.latency_us = int(latency_us)
        self.poll_ms = int(poll_ms)
        self._pcm = None
        self.buffer_frames = 0
        self.period_frames = 0
        #: Overruns since this input opened: audio the caller didn't read in time.
        self.xruns = 0

    def _open(self):
        self._open_pcm(STREAM_CAPTURE, self.latency_us)
        self.xruns = 0
        _check(_call("snd_pcm_start", self._pcm), "start")

    def _close(self):
        if self._pcm:
            _call("snd_pcm_drop", self._pcm)
        self._close_pcm()

    def queued_size(self):
        if not self._pcm:
            return 0
        avail = _call("snd_pcm_avail", self._pcm)
        return max(0, avail) * self.format.frame_size

    def clear(self):
        if self._pcm:
            _call("snd_pcm_drop", self._pcm)
            _call("snd_pcm_prepare", self._pcm)
            _call("snd_pcm_start", self._pcm)

    def _read_available(self, buf):
        """Read what the card holds, up to ``len(buf)`` bytes; 0 when it holds none."""
        size = self.format.frame_size
        frames = len(buf) // size
        scratch = bytearray(frames * size)
        while True:
            got = _call("snd_pcm_readi", self._pcm, scratch, frames)
            if got > 0:
                buf[: got * size] = scratch[: got * size]
                return got * size
            if got in (0, -EAGAIN):
                return 0
            if got in (-EPIPE, -ESTRPIPE, -EINTR):
                self._recover(int(got))
                _call("snd_pcm_start", self._pcm)
                continue
            raise OSError("ALSA read failed: %s" % _error(int(got)))

    def _readinto(self, buf):
        while True:
            count = self._read_available(buf)
            if count:
                return count
            _sleep_ms(self.poll_ms)

    async def _areadinto(self, buf):
        while True:
            count = self._read_available(buf)
            if count:
                return count
            await _asleep_ms(self.poll_ms)


def pcm_out(format=None, *, device=None, latency=None, poll_ms=2):
    """Create an ALSA `PCMOutput`.

    ``latency`` picks the ring buffer: ``"low"`` is 40 ms, the others 200 ms.
    """
    check_latency(latency)
    latency_us, prebuffer_ms = _PLAY_PROFILES[latency]
    fmt = format or AudioFormat(48000, 2, 16)
    return AlsaPCMOutput(fmt, device=device, latency_us=latency_us, prebuffer_ms=prebuffer_ms, poll_ms=poll_ms)


def pcm_in(format=None, *, device=None, latency=None, poll_ms=2):
    """Create an ALSA `PCMInput`."""
    check_latency(latency)
    fmt = format or AudioFormat(16000, 1, 16)
    return AlsaPCMInput(fmt, device=device, latency_us=_CAPTURE_LATENCY_US[latency], poll_ms=poll_ms)
