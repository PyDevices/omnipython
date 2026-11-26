# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""Show a display in a web browser, and use it from there.

`RemoteDisplay` is a display with no panel behind it. A board with no
screen gets one in any browser on its network, and every app runs on it
unchanged, LVGL included::

    from displaydev.remotedisplay import RemoteDisplay

    display_drv = RemoteDisplay(480, 320)
    host_read = display_drv.get_events

`mirror` puts a display that already has a panel in the browser as well.
It works on displays that keep the whole frame in memory, which are the
`FBDisplay` panels (MIPI DSI, RGB, DVI). The browser shows what the panel
shows, and its clicks and keys reach the app beside the panel's own touch::

    from displaydev.remotedisplay import mirror

    host_read = mirror(display_drv).read

Then open ``http://<the board's address>/`` (or the port you gave). One
browser at a time: a second one takes over, and the first page says so.

To watch without a browser, open ``http://<the board's address>/stream.mjpg``
in VLC (Media > Open Network Stream) or any player that takes Motion JPEG.
That needs `jpegio` in the firmware. The ESP32-P4 encodes on its JPEG engine,
17 ms for 800x480, so the player sees every change. Other boards encode in
software, about half a second a frame on an ESP32-S3, and the server leaves
the app four times that between frames, so expect a picture every two
seconds or so. A player counts as the one viewer too, and only watches.

The server reads the frame from memory when it sends, not when the app
draws, so a slow network or a closed browser never slows the app or the
panel. Only the parts that changed are sent, as runs of equal pixels where
that is smaller. The board needs Wi-Fi (or another network) up first.
"""

import json
import socket

import events
from multimer import every, ticks_diff, ticks_ms

from displaydev import alloc_buffer
from displaydev._domkeys import (
    _buttons_tuple,
    _caps,
    enrich_mod,
    key_to_keycode,
    mod_mask,
)
from displaydev._remotepage import PAGE
from displaydev.fbdisplay import FBDisplay

try:
    # Viper, where the build has the native emitter: tens of times faster.
    from displaydev._remotefast import _diff, _pal, _raw, _rle

    _VIPER = True
except (ImportError, SyntaxError, AttributeError, ValueError):
    _VIPER = False

# Tiles the frame is compared in. Wider tiles cost fewer headers; taller
# ones make a moving edge resend more.
_TW = 32
_TH = 16
_HEAD = 16  # bytes before each rectangle's pixels
_WS_ROOM = 10  # a WebSocket header fits in front of the payload
_BUF = 32768  # bytes of pixels packed per message, at least

# What a non-blocking socket raises when nothing is waiting: EAGAIN,
# EINPROGRESS, BSD's EWOULDBLOCK, Windows' WSAEWOULDBLOCK and WSAEINPROGRESS.
_AGAIN = (11, 115, 35, 10035, 10036)
_WS_GUID = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
_MAX_HEADER = 4096


def _again(e):
    return bool(e.args) and e.args[0] in _AGAIN


if not _VIPER:
    # CPython and builds without viper: a CRC per tile, and raw pixels only.
    import binascii as _binascii

    def _diff(fb, hashes, stride, w, h, flags, tx0, ty0, tx1, ty1):
        fb = memoryview(fb)
        cols_t = (w + _TW - 1) // _TW
        n = 0
        for ty in range(ty0, ty1):
            y0 = ty * _TH
            rows = min(_TH, h - y0)
            for tx in range(tx0, tx1):
                x0 = tx * _TW
                cols = min(_TW, w - x0)
                hv = 1
                for r in range(rows):
                    p = ((y0 + r) * stride + x0) * 2
                    hv = _binascii.crc32(fb[p : p + cols * 2], hv)
                i = ty * cols_t + tx
                if hashes[i] != hv:
                    hashes[i] = hv
                    flags[i] = 1
                    n += 1
                else:
                    flags[i] = 0
        return n

    def _rle(fb, stride, x, y, w, h, dst, off, cap):
        return -1

    def _pal(fb, stride, x, y, w, h, dst, off, cap, scratch):
        return -1

    def _raw(fb, stride, x, y, w, h, dst, off):
        fb = memoryview(fb)
        row = w * 2
        for r in range(h):
            p = ((y + r) * stride + x) * 2
            dst[off : off + row] = fb[p : p + row]
            off += row
        return w * h * 2


def _sha1(data):
    import hashlib

    try:
        return hashlib.sha1(data).digest()
    except AttributeError:
        return hashlib.new("sha1", data).digest()


class _Conn:
    """A connection that hasn't said yet whether it wants the page or the display."""

    def __init__(self, sock):
        sock.setblocking(False)
        self.sock = sock
        self.inbuf = b""
        self.out = b""
        self.done = False  # close once ``out`` is sent
        self.asked = False  # a WebSocket waiting for the password

    def flush(self):
        """Send what the socket takes. False when the connection is gone."""
        while self.out:
            try:
                n = self.sock.send(self.out)
            except OSError as e:
                if _again(e):
                    return True
                return False
            if not n:
                return True
            self.out = self.out[n:]
        return not self.done

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


class RemoteServer:
    """Serves one display to one browser at a time.

    You don't usually make one yourself: `RemoteDisplay` makes its own, and
    `mirror` makes one for a display you already have.

    Args:
        display: The display whose frame is shown. Its ``framebuffers()``
            must name the whole frame in memory.
        port (int): The TCP port for the page and the display. Default 80.
        period_ms (int): How often to look for changes and send them.
            Default 40 (25 times a second at most).
        sweep_ms (int): How often to compare the whole frame, for drawing
            the display wasn't told about (a program painting
            ``framebuffers()`` directly without ``flush_rect``). Between
            sweeps only the areas the display was told about are compared,
            which is what keeps a large frame cheap. Default 2000.
        bind (str): The address to listen on. Default all of them.
        password (str): Asked for before a browser sees the display or a
            video player gets the stream (as an HTTP password, any user
            name). Default None: anyone on the network can use it.

    Attributes:
        url (str): Where to point a browser, as best the board knows its
            own address.
        name_url (str): The same by the board's host name
            (``http://omnipython-a1b2c3.local/``), which stays right when the
            address changes, or None where there is no host name (a desktop).
        sent (int): Bytes of pixels sent since the server started.
        frames (int): Updates sent since the server started.
        quality (int): JPEG quality, 1 to 100, for a video player. Default 70.
    """

    def __init__(self, display, port=80, period_ms=40, sweep_ms=2000, bind="0.0.0.0", password=None):
        self.display = display
        self._password = password
        self._unwatch = None
        self._sweep_ms = sweep_ms
        self._last_sweep = ticks_ms()
        self._full = True
        self._force = False  # send every tile next, without comparing
        self._hint = None  # [x0, y0, x1, y1] drawn since the last update
        self._prev = None  # the update before's, until its frame was shown
        self.port = port
        self.quality = 70  # of the JPEGs a video player gets
        self._w = display.width
        self._h = display.height
        ntiles = ((self._w + _TW - 1) // _TW) * ((self._h + _TH - 1) // _TH)
        self._flags = bytearray(ntiles)
        self._scratch = bytearray(32)  # _pal's colours
        # The last hash of each tile: words for the viper loop, ints otherwise.
        self._hashes = bytearray(4 * ntiles) if _VIPER else [0] * ntiles
        self._buf = None
        self._range = None  # tiles of an update still being packed
        self._cursor = None  # (tile row, tile column) to pack next
        self._fb = None  # (frame, stride) for that update
        self._mjpeg = False  # the viewer is a video player, not the page
        self._jpeg = None  # its encoder
        self._next = []  # what to send once _out is out, in order
        self._lossy = bytearray(ntiles)  # tiles last sent as JPEG
        self._nlossy = 0
        self._jpeg_engine = None  # an encoder for large changes, or False
        # Large changes as JPEG: None where the chip has a JPEG engine,
        # True always, False never.
        self.jpeg_changes = None
        self._last_jpeg = 0
        self._jpeg_gap = 0  # ms to leave the app between two JPEGs
        self._view = None  # the browser's _Conn, once it has a WebSocket
        self._pending = []
        self._out = None  # memoryview of the frame still being sent
        self._events = []
        self._pressed = set()
        self._last_pos = (0, 0)
        self.sent = 0
        self.frames = 0

        s = socket.socket()
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except (OSError, AttributeError):
            pass
        s.bind(socket.getaddrinfo(bind, port)[0][-1])
        s.listen(2)
        s.setblocking(False)
        self._listener = s
        at = "" if port == 80 else ":%d" % port
        self.url = "http://%s%s/" % (_own_address(), at)
        name = _own_name()
        self.name_url = "http://%s.local%s/" % (name, at) if name else None
        self._page = _titled(PAGE, _board_name())
        self._timer = every(period_ms, self.poll, name="remotedisplay")
        if self.name_url:
            print("Display at %s and %s" % (self.url, self.name_url))
        else:
            print("Display at %s" % self.url)

    # -- the frame --

    def _frame(self):
        # The buffer on screen: a double-buffered panel names it second.
        bufs = self.display.framebuffers()
        if bufs is None:
            raise ValueError("this display keeps no frame in memory to send")
        fb = bufs[1] if bufs[1] is not None else bufs[0]
        return fb, bufs[3] // 2

    def _start_view(self):
        w, h = self._w, self._h
        if self._buf is None:
            # Room for a whole row of tiles at least. A bigger update goes
            # out over several polls, so no frame-sized buffer is needed.
            self._buf = bytearray(_WS_ROOM + max(_BUF, w * _TH * 2 + _HEAD))
        self._range = None
        self._full = True
        self._force = True
        swap = 1 if self.display.requires_byteswap else 0
        self._send_ws(json.dumps({"w": w, "h": h, "swap": swap}).encode(), 1)

    def note(self, x, y, w, h):
        """Say an area of the frame was drawn, so the next update looks there.

        The display's ``blit_rect``, ``fill_rect`` and ``flush_rect`` call
        this already; call it yourself only when you paint the frame another
        way and can't wait for the next sweep.
        """
        if self._view is None:
            return
        x1 = x + w
        y1 = y + h
        hint = self._hint
        if hint is None:
            self._hint = [x, y, x1, y1]
            return
        if x < hint[0]:
            hint[0] = x
        if y < hint[1]:
            hint[1] = y
        if x1 > hint[2]:
            hint[2] = x1
        if y1 > hint[3]:
            hint[3] = y1

    def _tiles(self):
        """The tile range to compare now, or None when there is nothing to look at."""
        w, h = self._w, self._h
        cols = (w + _TW - 1) // _TW
        rows = (h + _TH - 1) // _TH
        now = ticks_ms()
        hint, prev = self._hint, self._prev
        self._hint = None
        # A double-buffered panel shows what was drawn only after its next
        # present, so an area is compared again on the following update.
        self._prev = hint
        if self._full or ticks_diff(now, self._last_sweep) >= self._sweep_ms:
            self._full = False
            self._last_sweep = now
            return 0, 0, cols, rows
        if hint is None:
            hint = prev
        elif prev is not None:
            hint = [min(hint[0], prev[0]), min(hint[1], prev[1]), max(hint[2], prev[2]), max(hint[3], prev[3])]
        if hint is None:
            return None
        x0 = max(0, hint[0]) // _TW
        y0 = max(0, hint[1]) // _TH
        x1 = min(cols, (min(w, hint[2]) + _TW - 1) // _TW)
        y1 = min(rows, (min(h, hint[3]) + _TH - 1) // _TH)
        if x1 <= x0 or y1 <= y0:
            return None
        return x0, y0, x1, y1

    def _encode(self):
        """Pack what changed into ``_buf``. Returns the payload's length.

        An update too big for the buffer is packed over several calls.
        """
        w, h = self._w, self._h
        flags = self._flags
        if self._range is None:
            tiles = self._tiles()
            if self._nlossy:
                # Tiles sent as JPEG are sent again exactly once they stop
                # changing, wherever they are.
                tiles = (0, 0, (w + _TW - 1) // _TW, (h + _TH - 1) // _TH)
            if tiles is None:
                return 0
            tx0, ty0, tx1, ty1 = tiles
            fb, stride = self._frame()
            n = _diff(fb, self._hashes, stride, w, h, flags, tx0, ty0, tx1, ty1)
            if self._force:
                # The browser has nothing yet: every tile goes.
                self._force = False
                for i in range(len(flags)):
                    flags[i] = 1
                n = len(flags)
            if n >= len(flags) >> 3 and self._send_jpeg(fb, stride, tiles):
                return 0
            if self._nlossy:
                lossy = self._lossy
                for i in range(len(flags)):
                    if lossy[i]:
                        lossy[i] = 0
                        flags[i] = 1
                        n += 1
                self._nlossy = 0
            if not n:
                return 0
            self._range = tiles
            self._cursor = (ty0, tx0)
            self._fb = (fb, stride)
        tx0, ty0, tx1, ty1 = self._range
        fb, stride = self._fb
        buf = self._buf
        cap = len(buf)
        cols = (w + _TW - 1) // _TW
        off = _WS_ROOM
        ty, t = self._cursor
        while ty < ty1:
            y0 = ty * _TH
            th = min(_TH, h - y0)
            ti = ty * cols
            while t < tx1:
                if not flags[ti + t]:
                    t += 1
                    continue
                t1 = t
                while t1 < tx1 and flags[ti + t1]:
                    t1 += 1
                x = t * _TW
                rw = min(t1 * _TW, w) - x
                data = off + _HEAD
                if data + rw * th * 2 > cap:
                    # The rest goes in the next message.
                    self._cursor = (ty, t)
                    return off - _WS_ROOM
                raw = rw * th * 2
                n = _rle(fb, stride, x, y0, rw, th, buf, data, raw - 4)
                enc = 1
                # A few colours that don't run (text, icons) pack smaller as
                # a palette; skip the try when runs already did well.
                if n < 0 or n > raw >> 3:
                    k = _pal(fb, stride, x, y0, rw, th, buf, data, (n if n > 0 else raw) - 2, self._scratch)
                    if k > 0:
                        n = k
                        enc = 3
                if n < 0:
                    n = _raw(fb, stride, x, y0, rw, th, buf, data)
                    enc = 0
                _put_head(buf, off, x, y0, rw, th, enc, n)
                off = data + n
                t = t1
            ty += 1
            t = tx0
        self._range = None
        self._fb = None
        return off - _WS_ROOM

    def _jpeg_for_changes(self):
        if self._jpeg_engine is None:
            self._jpeg_engine = False
            if self.jpeg_changes is not False:
                try:
                    import jpegio

                    hw = None if self.jpeg_changes else True
                    self._jpeg_engine = jpegio.JpegEncoder(quality=self.quality, hardware=hw, exact=False)
                except (ImportError, OSError, ValueError, TypeError):
                    pass
        return self._jpeg_engine

    def _send_jpeg(self, fb, stride, tiles):
        """Send the changed tiles' bounds as one JPEG. False when it can't."""
        enc = self._jpeg_for_changes()
        if not enc:
            return False
        flags = self._flags
        cols = (self._w + _TW - 1) // _TW
        tx0, ty0, tx1, ty1 = tiles
        bx0, by0, bx1, by1 = tx1, ty1, tx0, ty0
        for ty in range(ty0, ty1):
            ti = ty * cols
            for tx in range(tx0, tx1):
                if flags[ti + tx]:
                    bx0 = min(bx0, tx)
                    bx1 = max(bx1, tx + 1)
                    by0 = min(by0, ty)
                    by1 = max(by1, ty + 1)
        if bx1 <= bx0:
            return False
        x = bx0 * _TW
        y = by0 * _TH
        rw = min(bx1 * _TW, self._w) - x
        rh = min(by1 * _TH, self._h) - y
        try:
            jpeg = enc.encode(
                memoryview(fb)[(y * stride + x) * 2 :],
                rw,
                rh,
                stride=stride * 2,
                swap=bool(self.display.requires_byteswap),
            )
        except (OSError, ValueError, MemoryError):
            self._jpeg_engine = False
            return False
        lossy = self._lossy
        for ty in range(by0, by1):
            for tx in range(bx0, bx1):
                if not lossy[ty * cols + tx]:
                    lossy[ty * cols + tx] = 1
                    self._nlossy += 1
        n = len(jpeg)
        pad = n & 1
        size = _HEAD + n + pad
        if size < 65536:
            ws = bytes((0x82, 126, size >> 8, size & 0xFF))
        else:
            ws = bytes((0x82, 127)) + size.to_bytes(8, "big")
        head = bytearray(len(ws) + _HEAD)
        head[: len(ws)] = ws
        _put_head(head, len(ws), x, y, rw, rh, 2, n)
        self._out = memoryview(head)
        self._next = [jpeg, b"\0"] if pad else [jpeg]
        self.sent += size
        self.frames += 1
        self._flush_frame()
        return True

    def _send_frame(self, n):
        buf = self._buf
        # Write the WebSocket header just in front of the payload.
        if n < 126:
            head = bytes((0x82, n))
        elif n < 65536:
            head = bytes((0x82, 126, n >> 8, n & 0xFF))
        else:
            head = bytes((0x82, 127)) + n.to_bytes(8, "big")
        start = _WS_ROOM - len(head)
        buf[start:_WS_ROOM] = head
        self._out = memoryview(buf)[start : _WS_ROOM + n]
        self.sent += n
        self.frames += 1
        self._flush_frame()

    def _flush_frame(self):
        """Send more of the frame. True while some of it is still waiting."""
        out = self._out
        view = self._view
        while out is not None and len(out):
            try:
                k = view.sock.send(out)
            except OSError as e:
                if _again(e):
                    break
                self._drop_view()
                return False
            if not k:
                break
            out = out[k:]
            if not len(out) and self._next:
                out = memoryview(self._next.pop(0))
        if out is not None and not len(out):
            out = None
        self._out = out
        return out is not None

    # -- the network --

    def poll(self, _timer=None):
        """Accept browsers, read their input and send what changed.

        The server's own timer calls this; you don't need to.
        """
        self._accept()
        if self._view is not None:
            self._read_view()
        if self._view is None:
            return
        if self._view.out:
            if not self._view.flush():
                self._drop_view()
            return
        if self._out is not None and self._flush_frame():
            return
        if self._view is None:
            return
        if self._mjpeg:
            self._stream()
            return
        n = self._encode()
        if n:
            self._send_frame(n)

    def _accept(self):
        while True:
            try:
                sock, _addr = self._listener.accept()
            except OSError as e:
                if _again(e):
                    break
                raise
            self._pending.append(_Conn(sock))
        if not self._pending:
            return
        keep = []
        for conn in self._pending:
            state = self._serve(conn)
            if state == "keep":
                keep.append(conn)
            elif state == "close":
                conn.close()
        self._pending = keep

    def _serve(self, conn):
        """Answer one request. "keep", "close", or "view" when it took the display."""
        if conn.asked:
            return self._check_password(conn)
        if conn.out or conn.done:
            if not conn.flush():
                return "close"
            return "keep" if conn.out else "close"
        try:
            data = conn.sock.recv(1024)
        except OSError as e:
            return "keep" if _again(e) else "close"
        if not data:
            return "close"
        conn.inbuf += data
        end = conn.inbuf.find(b"\r\n\r\n")
        if end < 0:
            return "keep" if len(conn.inbuf) < _MAX_HEADER else "close"
        lines = conn.inbuf[:end].decode().split("\r\n")
        conn.inbuf = conn.inbuf[end + 4 :]
        parts = lines[0].split(" ")
        target = parts[1].split("?")[0] if len(parts) > 1 else "/"
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()
        key = headers.get("sec-websocket-key")
        if key and target == "/ws":
            self._handshake(conn, key)
            if self._password is None:
                self._take_view(conn)
                return "view"
            # The display stays with whoever has it until this one gives
            # the password: a stranger can't even take it away.
            conn.out += _ws_text(b'{"auth":1}')
            conn.asked = True
            conn.flush()
            return "keep"
        if target == "/stream.mjpg":
            if self._password is not None and not self._basic_ok(headers.get("authorization", "")):
                conn.out = (
                    b"HTTP/1.1 401 Unauthorized\r\nWWW-Authenticate: Basic realm=\"display\"\r\n"
                    b"Content-Length: 0\r\nConnection: close\r\n\r\n"
                )
                conn.done = True
                conn.flush()
                return "keep" if conn.out else "close"
            return self._take_stream(conn)
        if target in ("/", "/index.html"):
            conn.out = (
                "HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n"
                "Cache-Control: no-cache\r\nConnection: close\r\nContent-Length: %d\r\n\r\n" % len(self._page)
            ).encode() + self._page
        else:
            conn.out = b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
        conn.done = True
        conn.flush()
        return "keep" if conn.out else "close"

    def _let_go(self):
        # The newest viewer wins: a forgotten tab can't lock you out.
        old = self._view
        if old is None:
            return
        self._out = None
        if not self._mjpeg:
            self._send_ws(b'{"bye":"taken"}', 1)
            old.flush()
        self._drop_view()

    def _handshake(self, conn, key):
        import binascii

        accept = binascii.b2a_base64(_sha1(key.encode() + _WS_GUID)).strip()
        conn.out = (
            b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n"
            b"Connection: Upgrade\r\nSec-WebSocket-Accept: " + accept + b"\r\n\r\n"
        )

    def _check_password(self, conn):
        # The page's first message is ["p", password].
        if conn.out and not conn.flush():
            return "close"
        if conn.done:
            return "keep" if conn.out else "close"
        try:
            data = conn.sock.recv(1024)
        except OSError as e:
            return "keep" if _again(e) else "close"
        if not data:
            return "close"
        conn.inbuf += data
        got = _ws_frame(conn)
        if got is False:
            return "close"
        if got is None:
            return "keep" if len(conn.inbuf) < _MAX_HEADER else "close"
        opcode, payload = got
        given = None
        if opcode == 1:
            try:
                msg = json.loads(payload)
                if msg[0] == "p":
                    given = msg[1]
            except (ValueError, IndexError, TypeError, KeyError):
                pass
        if given is None or given != self._password:
            conn.out += _ws_text(b'{"bye":"password"}')
            conn.done = True
            conn.flush()
            return "keep" if conn.out else "close"
        conn.asked = False
        self._take_view(conn)
        return "view"

    def _basic_ok(self, value):
        # HTTP Basic: any user name, the password after the colon.
        import binascii

        if not value.startswith("Basic "):
            return False
        try:
            pair = binascii.a2b_base64(value[6:].strip()).decode()
        except (ValueError, UnicodeError):
            return False
        return pair.partition(":")[2] == self._password

    def _take_view(self, conn):
        self._let_go()
        self._view = conn
        self._pressed = set()
        self._start_view()
        conn.flush()

    def _take_stream(self, conn):
        # A video player such as VLC gets the frame as Motion JPEG: a JPEG
        # each time it changes, and every two seconds anyway so a player
        # that joins late has a picture.
        if self._jpeg is None:
            try:
                import jpegio
            except ImportError:
                conn.out = b"HTTP/1.1 501 Not Implemented\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
                conn.done = True
                conn.flush()
                return "keep" if conn.out else "close"
            # exact=False lets the ESP32-P4's engine read the frame in place.
            self._jpeg = jpegio.JpegEncoder(quality=self.quality, exact=False)
        self._let_go()
        conn.out = (
            b"HTTP/1.1 200 OK\r\nContent-Type: multipart/x-mixed-replace; boundary=frame\r\n"
            b"Cache-Control: no-cache\r\nConnection: close\r\n\r\n"
        )
        self._view = conn
        self._mjpeg = True
        self._full = True
        self._force = True
        conn.flush()
        return "view"

    def _stream(self):
        """Encode the frame as the next JPEG when it changed."""
        now = ticks_ms()
        since = ticks_diff(now, self._last_jpeg)
        if since < self._jpeg_gap:
            return
        due = since >= self._sweep_ms
        tiles = self._tiles()
        fb, stride = self._frame()
        changed = 0
        if tiles is not None:
            changed = _diff(fb, self._hashes, stride, self._w, self._h, self._flags, *tiles)
        if self._force:
            self._force = False
            changed = 1
        if not (changed or due):
            return
        self._last_jpeg = now
        jpeg = self._jpeg.encode(
            fb, self._w, self._h, stride=stride * 2, swap=bool(self.display.requires_byteswap)
        )
        # A software encoder holds the app for as long as it takes (about
        # half a second for 800x480 on an ESP32-S3), so wait four times that
        # before the next: the app keeps most of the board.
        self._jpeg_gap = 4 * ticks_diff(ticks_ms(), now)
        # The CRLF in front ends the previous part.
        head = "\r\n--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n" % len(jpeg)
        self._out = memoryview(head.encode())
        self._next = [jpeg]
        self.sent += len(jpeg)
        self.frames += 1
        self._flush_frame()

    def _drop_view(self):
        view = self._view
        self._view = None
        self._out = None
        self._next = []
        self._mjpeg = False
        self._range = None
        self._fb = None
        if view is not None:
            view.close()

    def _send_ws(self, payload, opcode):
        n = len(payload)
        if n < 126:
            head = bytes((0x80 | opcode, n))
        else:
            head = bytes((0x80 | opcode, 126, n >> 8, n & 0xFF))
        self._view.out += head + payload

    def _read_view(self):
        view = self._view
        try:
            data = view.sock.recv(1024)
        except OSError as e:
            if not _again(e):
                self._drop_view()
            return
        if not data:
            self._drop_view()
            return
        if self._mjpeg:
            return  # a player sends nothing that matters
        view.inbuf += data
        while self._view is view:
            msg = self._ws_message(view)
            if msg is None:
                break
            if msg:
                self._on_input(msg)

    def _ws_message(self, view):
        got = _ws_frame(view)
        if got is None:
            return None
        if got is False:
            self._drop_view()  # nothing the page sends is that big
            return None
        opcode, payload = got
        if opcode == 8:
            self._drop_view()
            return None
        if opcode == 9:
            self._send_ws(payload, 10)
            return b""
        return payload if opcode == 1 else b""

    # -- input --

    def _on_input(self, msg):
        try:
            a = json.loads(msg)
            kind = a[0]
        except (ValueError, IndexError, TypeError):
            return
        q = self._events
        if kind in ("d", "u"):
            _, x, y, button, touch, finger = a
            pos = (x, y)
            self._last_pos = pos
            down = kind == "d"
            if touch:
                q.append(events.Finger(events.FINGERDOWN if down else events.FINGERUP, pos, finger, None))
            q.append(
                events.Button(
                    events.MOUSEBUTTONDOWN if down else events.MOUSEBUTTONUP, pos, button, bool(touch), None
                )
            )
        elif kind == "m":
            _, x, y, buttons, touch, finger = a
            pos = (x, y)
            old = self._last_pos
            self._last_pos = pos
            if touch:
                q.append(events.Finger(events.FINGERMOTION, pos, finger, None))
            q.append(
                events.Motion(
                    events.MOUSEMOTION,
                    pos,
                    (x - old[0], y - old[1]),
                    _buttons_tuple(buttons),
                    bool(touch),
                    None,
                )
            )
        elif kind == "w":
            _, dx, dy = a
            q.append(events.Wheel(events.MOUSEWHEEL, False, dx, dy, dx, dy, False, None))
        elif kind == "k":
            _, down, key, location, ctrl, shift, alt, meta = a
            code = key_to_keycode(key, location)
            if down:
                self._pressed.add(code)
            else:
                self._pressed.discard(code)
            mod = enrich_mod(mod_mask(ctrl, shift, alt, meta), self._pressed) | _caps(key, shift)
            import keys

            q.append(
                events.Key(events.KEYDOWN if down else events.KEYUP, keys.keyname(code), code, mod, 0, None)
            )

    def read(self):
        """The browser's input since the last call, as ``events`` records.

        Give it to the app as the board's ``host_read``.
        """
        if not self._events:
            return []
        out = self._events
        self._events = []
        return out

    @property
    def connected(self):
        """True while a browser is showing the display."""
        return self._view is not None

    def close(self):
        """Stop serving and let the browser go."""
        if self._unwatch is not None:
            self._unwatch()
            self._unwatch = None
        if self._timer is not None:
            self._timer.deinit()
            self._timer = None
        self._drop_view()
        for conn in self._pending:
            conn.close()
        self._pending = []
        try:
            self._listener.close()
        except OSError:
            pass


def _ws_text(payload):
    # A short text message from the server: unmasked, under 126 bytes.
    return bytes((0x81, len(payload))) + payload


def _ws_frame(conn):
    """The next WebSocket message in ``conn.inbuf`` as (opcode, payload).

    None while it is incomplete; False for one too big to be the page's.
    """
    buf = conn.inbuf
    if len(buf) < 2:
        return None
    opcode = buf[0] & 0x0F
    masked = buf[1] & 0x80
    n = buf[1] & 0x7F
    pos = 2
    if n == 126:
        if len(buf) < 4:
            return None
        n = (buf[2] << 8) | buf[3]
        pos = 4
    elif n == 127:
        return False
    mask = None
    if masked:
        if len(buf) < pos + 4:
            return None
        mask = buf[pos : pos + 4]
        pos += 4
    if len(buf) < pos + n:
        return None
    payload = bytearray(buf[pos : pos + n])
    conn.inbuf = buf[pos + n :]
    if mask:
        for i in range(n):
            payload[i] ^= mask[i & 3]
    return opcode, bytes(payload)


def _put_head(buf, off, x, y, w, h, enc, n):
    for i, v in enumerate((x, y, w, h, enc, 0)):
        buf[off + 2 * i] = v & 0xFF
        buf[off + 2 * i + 1] = v >> 8
    buf[off + 12] = n & 0xFF
    buf[off + 13] = (n >> 8) & 0xFF
    buf[off + 14] = (n >> 16) & 0xFF
    buf[off + 15] = n >> 24


def _board_name():
    """The board's name from `boarddev`, for the page's title; None without it."""
    try:
        import boarddev

        return boarddev.name() or None
    except (ImportError, AttributeError, OSError, ValueError):
        return None


def _titled(page, name):
    """The page with the board's name as its title, so a browser tab says which board it shows."""
    if not name:
        return page
    safe = name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return page.replace(b"<title>Display</title>", b"<title>" + safe.encode() + b"</title>", 1)


def _own_name():
    """The host name mDNS answers to on a board, without ``.local``; None on a desktop."""
    try:
        import network

        return network.hostname() or None
    except (ImportError, AttributeError, OSError):
        pass
    try:
        import wifi

        return wifi.radio.hostname or None
    except (ImportError, AttributeError):
        return None


def _own_address():
    try:
        import network

        return network.WLAN(network.STA_IF).ifconfig()[0]
    except (ImportError, AttributeError, OSError):
        pass
    try:
        import wifi

        return str(wifi.radio.ipv4_address)
    except (ImportError, AttributeError):
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(socket.getaddrinfo("10.255.255.255", 1)[0][-1])
            return s.getsockname()[0]
        finally:
            s.close()
    except (OSError, AttributeError, TypeError, IndexError):
        return "localhost"


def mirror(display, port=80, period_ms=40, sweep_ms=2000, password=None):
    """Show ``display``'s panel in a browser as well.

    ``display`` must keep its whole frame in memory: an `FBDisplay`
    (MIPI DSI, RGB, DVI panels). Give the returned server's ``read`` to the
    app as ``host_read`` so the browser's clicks and keys reach it.

    Args:
        display: The panel's display driver.
        port (int): The TCP port. Default 80.
        period_ms (int): How often to send changes. Default 40.
        sweep_ms (int): How often to compare the whole frame, for drawing
            that bypassed the display's methods. Default 2000.
        password (str): Asked for before a browser sees or uses the
            display. Default None: anyone on the network can.

    Returns:
        RemoteServer: The server. ``close()`` stops it.
    """
    if display.framebuffers() is None:
        raise ValueError("%s keeps no frame in memory; mirror needs an FBDisplay" % type(display).__name__)
    server = RemoteServer(display, port=port, period_ms=period_ms, sweep_ms=sweep_ms, password=password)
    _watch(display, server)
    return server


def _watch(display, server):
    # Tell the server where the display draws, by wrapping this display's
    # own methods. Drawing still goes straight to the panel. Closing the
    # server puts the methods back, or, when something wrapped them since,
    # stops noting.
    note = server.note
    blit_rect = display.blit_rect
    fill_rect = display.fill_rect
    flush_rect = display.flush_rect
    live = [True]

    def blit(buf, x, y, w, h):
        if live[0]:
            note(x, y, w, h)
        return blit_rect(buf, x, y, w, h)

    def fill(x, y, w, h, c):
        if live[0]:
            note(x, y, w, h)
        return fill_rect(x, y, w, h, c)

    def flush(x, y, w, h):
        if live[0]:
            note(x, y, w, h)
        return flush_rect(x, y, w, h)

    def unwatch():
        live[0] = False
        if display.blit_rect is blit and display.fill_rect is fill and display.flush_rect is flush:
            display.blit_rect = blit_rect
            display.fill_rect = fill_rect
            display.flush_rect = flush_rect

    display.blit_rect = blit
    display.fill_rect = fill
    display.flush_rect = flush
    server._unwatch = unwatch


class RemoteDisplay(FBDisplay):
    """A display with no panel: you see and use it in a web browser.

    The frame lives in RAM (PSRAM on boards that have it): ``width * height
    * 2`` bytes. Give ``get_events`` to the app as ``host_read``.

    Args:
        width (int): Width in pixels. Default 480.
        height (int): Height in pixels. Default 320.
        port (int): The TCP port for the page. Default 80.
        period_ms (int): How often to send changes. Default 40.
        sweep_ms (int): How often to compare the whole frame. Default 2000.
        password (str): Asked for before a browser sees or uses the
            display. Default None: anyone on the network can.

    Attributes:
        server (RemoteServer): Serves the page and the frame.
    """

    server = None

    def __init__(self, width=480, height=320, port=80, period_ms=40, sweep_ms=2000, *, password=None, quiet=False):
        super().__init__(alloc_buffer(width * height * 2), width, height, quiet=quiet)
        self.server = RemoteServer(self, port=port, period_ms=period_ms, sweep_ms=sweep_ms, password=password)

    def get_events(self):
        """The browser's input since the last call: give it to the app as ``host_read``."""
        return self.server.read()

    @property
    def needs_refresh(self):
        """False: the server sends changes on its own timer."""
        return False

    def show(self, _timer=None):
        """Have the next update compare the whole frame.

        Nothing needs presenting: the server sends the frame as it changes.
        A program that paints ``framebuffers()`` directly calls this when it
        has finished a frame, as it would on a panel.
        """
        if self.server is not None:
            self.server._full = True

    def blit_rect(self, buf, x, y, w, h):
        if self.server is not None:
            self.server.note(x, y, w, h)
        return super().blit_rect(buf, x, y, w, h)

    def fill_rect(self, x, y, w, h, c):
        if self.server is not None:
            self.server.note(x, y, w, h)
        return super().fill_rect(x, y, w, h, c)

    def flush_rect(self, x, y, w, h):
        """Note an area painted straight into the frame. Returns True."""
        if self.server is not None:
            self.server.note(x, y, w, h)
        return True

    def _deinit(self):
        self.server.close()
