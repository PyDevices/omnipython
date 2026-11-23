# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""Cast the screen a board already has, as well as showing it there.

`HlsDisplay` and `CastDisplay` are displays of their own: the app draws into
them and nowhere else. These two functions take a display you already have,
a panel that keeps its whole frame in memory (an `FBDisplay`: MIPI DSI, RGB,
DVI), and send what it shows::

    from castdisplay.mirror import mirror_hls

    hls = mirror_hls(display_drv)  # prints the URL to open in VLC

    from castdisplay.mirror import mirror_cast

    cast = mirror_cast(display_drv, "192.168.1.143", kind="windows")

The panel and the app carry on as before. Each frame the app finishes is
handed to the stream, which encodes it on its own: on an ESP32-P4 that is the
firmware's ``castif`` task, on CPython ffmpeg.
"""

import time

from multimer import every

try:
    import castif
except ImportError:
    castif = None


def _frame(display):
    bufs = display.framebuffers() if hasattr(display, "framebuffers") else None
    if bufs is None:
        raise ValueError("this display keeps no frame in memory to cast")
    w, h = display.width, display.height
    if w % 16 or h % 16:
        raise ValueError("casting needs a width and height in multiples of 16, not %dx%d" % (w, h))
    if bufs[3] != w * 2:
        raise ValueError("this panel pads its rows, which the encoder can't read")
    return bufs


def _front(display):
    bufs = display.framebuffers()
    # A double-buffered panel names the buffer on screen second.
    return bufs[1] if bufs[1] is not None else bufs[0]


def _watch(display, changed):
    # Call changed() after each drawing call the display gets.
    blit, fill, flush = display.blit_rect, display.fill_rect, display.flush_rect

    def blit_rect(buf, x, y, w, h):
        r = blit(buf, x, y, w, h)
        changed()
        return r

    def fill_rect(x, y, w, h, c):
        r = fill(x, y, w, h, c)
        changed()
        return r

    def flush_rect(x, y, w, h):
        r = flush(x, y, w, h)
        changed()
        return r

    display.blit_rect = blit_rect
    display.fill_rect = fill_rect
    display.flush_rect = flush_rect


def _own_address():
    try:
        import network
    except ImportError:
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 53))
            return s.getsockname()[0]
        except OSError:
            return "localhost"
        finally:
            s.close()
    wlan = network.WLAN(network.STA_IF)
    # Wi-Fi power saving holds each packet up to a beacon interval, and a
    # player waiting on a segment skips.
    try:
        wlan.config(pm=wlan.PM_NONE)
    except (AttributeError, ValueError, OSError):
        pass
    return wlan.ifconfig()[0]


class HlsMirror:
    """Live HLS of a display's panel. Made by `mirror_hls`.

    Attributes:
        url (str): Where to point VLC or another HLS player.
    """

    def __init__(self, display, fps=20, bitrate=2_000_000, port=8090, segments=4, log=print):
        _frame(display)
        self.display = display
        w, h = display.width, display.height
        path = "/r%d" % (time.ticks_ms() & 0xFFFFFF if hasattr(time, "ticks_ms") else int(time.time() * 1000) & 0xFFFFFF)
        if castif is not None:
            self.hls = castif.Hls(w, h, fps=fps, bitrate=bitrate, port=port, path=path, segments=segments)
        else:
            import sys

            if sys.implementation.name != "cpython":
                raise RuntimeError("mirror_hls needs an ESP32-P4 (castif) or CPython with ffmpeg")
            from .hls_display import _FfmpegHls

            self.hls = _FfmpegHls(w, h, fps=fps, bitrate=bitrate, port=port, path=path, segments=segments)
        self.hls.start()
        self.url = "http://%s:%d%s/stream.m3u8" % (_own_address(), port, path)
        log("HLS at", self.url)
        self._dirty = True
        _watch(display, self._changed)
        self._timer = every(max(1, 1000 // fps), self._tick, name="hlsmirror")

    def _changed(self):
        self._dirty = True

    def _tick(self, _timer=None):
        if not self._dirty:
            return
        # The stream copies the frame it takes, and skips one while it is
        # still busy with the last: try again on the next tick.
        if self.hls.offer(_front(self.display)) is not False:
            self._dirty = False

    def stats(self):
        """The stream's counters: frames, offers, overruns, requests."""
        return self.hls.stats()

    def close(self):
        """Stop the stream. The panel carries on."""
        if self._timer is not None:
            self._timer.deinit()
            self._timer = None
        self.hls.close()


def mirror_hls(display, fps=20, bitrate=2_000_000, port=8090, segments=4, log=print):
    """Serve what ``display`` shows as live HLS, for VLC or any HLS player.

    HLS runs several seconds behind, so it suits watching rather than driving.

    Args:
        display: A display whose ``framebuffers()`` names the whole frame,
            with a width and height in multiples of 16.
        fps (int): Frames encoded a second at most. Default 20.
        bitrate (int): Bits a second. Default 2,000,000.
        port (int): The HTTP port. Default 8090.
        segments (int): How many one-second segments the playlist lists.
        log: Where the URL is printed. Default ``print``.

    Returns:
        HlsMirror: The stream; its ``url`` is where to look.

    Raises:
        ValueError: The display keeps no whole frame, or its size can't be
            encoded.
        RuntimeError: Neither ``castif`` nor ffmpeg is here.
    """
    return HlsMirror(display, fps=fps, bitrate=bitrate, port=port, segments=segments, log=log)


def mirror_cast(display, sink, kind="windows", **kwargs):
    """Cast what ``display`` shows over Miracast, about a frame behind.

    Args:
        display: A display with one frame buffer (not double-buffered), a
            width and height in multiples of 16, and unpadded rows.
        sink: The TV's or the PC's IP address.
        kind: ``"windows"`` (the Wireless Display app) or ``"roku"``.
        **kwargs: `CastDisplay`'s other options (``fps``, ``bitrate``,
            ``audio``, ``log``, ...).

    Returns:
        CastDisplay: The cast. Draw on ``display`` as before, not on this.

    Raises:
        ValueError: The display can't be cast as it is; a double-buffered
            panel can still use `mirror_hls`.
    """
    bufs = _frame(display)
    if bufs[1] is not None:
        raise ValueError("this panel flips between two buffers; Miracast reads one fixed buffer, so use mirror_hls")
    from .cast_display import CastDisplay

    cast = CastDisplay(sink, display.width, display.height, kind=kind, buffer=bufs[0], **kwargs)
    _watch(display, cast.show)
    return cast
