# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Tests for ``displaydev.remotedisplay``: a browser's view of the frame.

A client here speaks to the server as the page does: it fetches the page,
opens the WebSocket, rebuilds the frame from the rectangles it is sent, and
sends a click back. It runs against the server in CPython (plain-Python
comparisons, raw rectangles) and under unix MicroPython (viper, with runs).
"""

import base64
import binascii
import json
import os
import socket
import struct
import subprocess
import sys
import threading
import time
import types
import unittest
from unittest import mock

import _env
import _mprun
import events

try:
    import PIL

    _has_pil = True
except ImportError:
    _has_pil = False


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _connect(port, timeout=10):
    end = time.time() + timeout
    while True:
        try:
            return socket.create_connection(("127.0.0.1", port), timeout=5)
        except OSError:
            if time.time() > end:
                raise
            time.sleep(0.05)


class _Client:
    """The page's side of the WebSocket."""

    def __init__(self, port):
        self.sock = _connect(port)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall(
            (
                "GET /ws HTTP/1.1\r\nHost: x\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n" % key
            ).encode()
        )
        self.buf = b""
        head = self._until(b"\r\n\r\n")
        assert head.startswith(b"HTTP/1.1 101"), head
        self.frame = None
        self.w = self.h = 0
        self.encodings = set()

    def _fill(self):
        data = self.sock.recv(65536)
        if not data:
            raise ConnectionError("closed")
        self.buf += data

    def _until(self, mark):
        while mark not in self.buf:
            self._fill()
        i = self.buf.index(mark) + len(mark)
        out, self.buf = self.buf[:i], self.buf[i:]
        return out

    def _take(self, n):
        while len(self.buf) < n:
            self._fill()
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def message(self):
        """``(opcode, payload)`` of the next message from the server."""
        b0, b1 = self._take(2)
        n = b1 & 0x7F
        if n == 126:
            n = struct.unpack(">H", self._take(2))[0]
        elif n == 127:
            n = struct.unpack(">Q", self._take(8))[0]
        return b0 & 0x0F, self._take(n)

    def send(self, obj):
        payload = json.dumps(obj).encode()
        mask = os.urandom(4)
        masked = bytes(c ^ mask[i & 3] for i, c in enumerate(payload))
        self.sock.sendall(bytes((0x81, 0x80 | len(payload))) + mask + masked)

    def apply(self, payload):
        """Paint one update into ``frame``, as the page's paint() does."""
        o = 0
        while o + 16 <= len(payload):
            x, y, w, h, enc, _, n = struct.unpack_from("<6HI", payload, o)
            data = payload[o + 16 : o + 16 + n]
            o += 16 + n + (n & 1)
            self.encodings.add(enc)
            pixels = []
            if enc == 0:
                pixels = [data[i : i + 2] for i in range(0, n, 2)]
            elif enc == 2:
                from io import BytesIO

                from PIL import Image

                img = Image.open(BytesIO(data)).convert("RGB")
                assert img.size == (w, h), (img.size, w, h)
                for py in range(h):
                    for px in range(w):
                        r, g, b = img.getpixel((px, py))
                        v = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
                        pixels.append(struct.pack("<H", v))
            elif enc == 3:
                k = struct.unpack_from("<H", data, 0)[0]
                pal = [data[4 + 2 * i : 6 + 2 * i] for i in range(k)]
                q = 4 + 2 * k
                for i in range(w * h):
                    v = data[q + (i >> 1)]
                    pixels.append(pal[v & 15 if i & 1 else v >> 4])
            else:
                for i in range(0, n, 4):
                    count = struct.unpack_from("<H", data, i)[0]
                    pixels.extend([data[i + 2 : i + 4]] * count)
            assert len(pixels) == w * h, (len(pixels), w, h)
            for r in range(h):
                for c in range(w):
                    p = ((y + r) * self.w + x + c) * 2
                    self.frame[p : p + 2] = pixels[r * w + c]

    def until_crc(self, crc, timeout=10):
        """Apply updates until the rebuilt frame's CRC is ``crc``."""
        self.sock.settimeout(timeout)
        while binascii.crc32(bytes(self.frame)) != crc:
            op, payload = self.message()
            if op == 2:
                self.apply(payload)

    def hello(self):
        op, payload = self.message()
        assert op == 1, op
        msg = json.loads(payload)
        self.w, self.h = msg["w"], msg["h"]
        self.frame = bytearray(self.w * self.h * 2)
        return msg

    def close(self):
        self.sock.close()


def _get_page(port):
    s = _connect(port)
    s.sendall(b"GET / HTTP/1.1\r\nHost: x\r\n\r\n")
    data = b""
    while True:
        chunk = s.recv(65536)
        if not chunk:
            break
        data += chunk
    s.close()
    return data


class TestOnCPython(unittest.TestCase):
    def setUp(self):
        from displaydev.remotedisplay import RemoteDisplay

        self.port = _free_port()
        self.d = RemoteDisplay(70, 40, port=self.port, quiet=True)
        self.d.fill(0)
        self.d.fill_rect(3, 4, 20, 10, 0xF800)
        for i in range(70):
            self.d.pixel(i, 37, i * 409 & 0xFFFF)
        self._stop = False
        self._thread = threading.Thread(target=self._pump, daemon=True)
        self._thread.start()

    def _pump(self):
        while not self._stop:
            self.d.server.poll()
            time.sleep(0.005)

    def tearDown(self):
        self._stop = True
        self._thread.join()
        self.d.deinit()

    def _crc(self):
        return binascii.crc32(bytes(self.d._raw_buffer))

    def test_a_board_says_its_host_name_too(self):
        from displaydev import remotedisplay

        board = types.ModuleType("network")
        board.hostname = lambda: "omnipython-d0a23a"
        with mock.patch.dict(sys.modules, {"network": board}):
            self.assertEqual(remotedisplay._own_name(), "omnipython-d0a23a")
        self.assertIsNone(self.d.server.name_url, "a desktop has no host name of its own")

    def test_page(self):
        data = _get_page(self.port)
        self.assertTrue(data.startswith(b"HTTP/1.1 200"))
        self.assertIn(b'<canvas id="c"', data)

    def test_frame_click_and_takeover(self):
        a = _Client(self.port)
        self.assertEqual(a.hello(), {"w": 70, "h": 40, "swap": 0})
        a.until_crc(self._crc())

        # A click comes back as a button event at the frame's coordinates.
        a.send(["d", 12, 20, 1, 0, 1])
        deadline = time.time() + 5
        got = []
        while not got and time.time() < deadline:
            got = [e for e in self.d.get_events() if e.type == events.MOUSEBUTTONDOWN]
            time.sleep(0.01)
        self.assertEqual(got[0].pos, (12, 20))
        self.assertEqual(got[0].button, 1)

        # Drawing after the first update reaches the browser too.
        self.d.fill_rect(40, 2, 5, 5, 0x001F)
        a.until_crc(self._crc())

        # A second browser takes over; the first is told so.
        b = _Client(self.port)
        b.hello()
        b.until_crc(self._crc())
        a.sock.settimeout(5)
        op, payload = a.message()
        self.assertEqual((op, json.loads(payload)), (1, {"bye": "taken"}))
        a.close()
        b.close()


class TestPassword(unittest.TestCase):
    def setUp(self):
        from displaydev.remotedisplay import RemoteDisplay

        self.port = _free_port()
        self.d = RemoteDisplay(64, 32, port=self.port, password="sesame", quiet=True)
        self.d.fill_rect(2, 2, 10, 10, 0xF800)
        self._stop = False
        self._thread = threading.Thread(target=self._pump, daemon=True)
        self._thread.start()

    def _pump(self):
        while not self._stop:
            self.d.server.poll()
            time.sleep(0.005)

    def tearDown(self):
        self._stop = True
        self._thread.join()
        self.d.deinit()

    def _text(self, c):
        c.sock.settimeout(5)
        op, payload = c.message()
        self.assertEqual(op, 1)
        return json.loads(payload)

    def test_wrong_then_right(self):
        a = _Client(self.port)
        self.assertEqual(self._text(a), {"auth": 1})
        a.send(["p", "nope"])
        self.assertEqual(self._text(a), {"bye": "password"})
        a.close()

        b = _Client(self.port)
        self.assertEqual(self._text(b), {"auth": 1})
        b.send(["p", "sesame"])
        self.assertEqual(b.hello(), {"w": 64, "h": 32, "swap": 0})
        b.until_crc(binascii.crc32(bytes(self.d._raw_buffer)))

        # A stranger without the password doesn't take it away.
        c = _Client(self.port)
        self.assertEqual(self._text(c), {"auth": 1})
        c.send(["p", "guess"])
        self.assertEqual(self._text(c), {"bye": "password"})
        self.assertTrue(self.d.server.connected)
        self.d.fill_rect(30, 10, 5, 5, 0x07E0)
        b.until_crc(binascii.crc32(bytes(self.d._raw_buffer)))
        b.close()
        c.close()

    def test_video_player_needs_it(self):
        s = _connect(self.port)
        s.sendall(b"GET /stream.mjpg HTTP/1.1\r\nHost: x\r\n\r\n")
        s.settimeout(5)
        self.assertTrue(s.recv(100).startswith(b"HTTP/1.1 401"))
        s.close()


def _line(proc, prefix):
    """The server's next output line that starts with ``prefix``."""
    while True:
        line = proc.stdout.readline()
        if not line:
            raise AssertionError("the server ended before printing %r" % prefix)
        if line.startswith(prefix):
            return line.strip()


class TestOnMicroPython(unittest.TestCase):
    def test_viper_runs_and_click(self):
        mp = _mprun.need_micropython(self)
        port = _free_port()
        env = dict(os.environ, MICROPYPATH=str(_mprun.LIB))
        proc = subprocess.Popen(
            [mp, str(_mprun.TESTS / "remotedisplay_server.py"), str(port), "8"],
            stdout=subprocess.PIPE,
            text=True,
            env=env,
        )
        try:
            crc = int(_line(proc, "crc").split()[1], 16)
            c = _Client(port)
            c.hello()
            c.until_crc(crc)
            # The picture's flat areas went as runs, the few-coloured
            # checks as a palette, and the varied rows raw.
            self.assertEqual(c.encodings, {0, 1, 3})
            c.send(["d", 60, 30, 1, 0, 1])
            self.assertEqual(_line(proc, "click"), "click 60 30")
            c.until_crc(int(_line(proc, "crc").split()[1], 16))
            c.close()
        finally:
            proc.kill()
            proc.wait()
            proc.stdout.close()

    @unittest.skipUnless(_has_pil, "Pillow decodes the JPEGs")
    def test_large_changes_as_jpeg_then_exact(self):
        mp = _mprun.need_micropython(self)
        port = _free_port()
        env = dict(os.environ, MICROPYPATH=str(_mprun.LIB))
        proc = subprocess.Popen(
            [mp, str(_mprun.TESTS / "remotedisplay_server.py"), str(port), "8", "jpeg"],
            stdout=subprocess.PIPE,
            text=True,
            env=env,
        )
        try:
            crc = int(_line(proc, "crc").split()[1], 16)
            c = _Client(port)
            c.hello()
            # The whole first picture is one JPEG, and once nothing changes
            # its tiles come again exactly.
            c.until_crc(crc)
            self.assertIn(2, c.encodings)
            c.close()
        finally:
            proc.kill()
            proc.wait()
            proc.stdout.close()

    @unittest.skipUnless(_has_pil, "Pillow decodes the stream's JPEGs")
    def test_video_player_gets_jpegs(self):
        mp = _mprun.need_micropython(self)
        port = _free_port()
        env = dict(os.environ, MICROPYPATH=str(_mprun.LIB))
        proc = subprocess.Popen(
            [mp, str(_mprun.TESTS / "remotedisplay_server.py"), str(port), "8"],
            stdout=subprocess.PIPE,
            text=True,
            env=env,
        )
        try:
            _line(proc, "crc")
            s = _connect(port)
            s.sendall(b"GET /stream.mjpg HTTP/1.1\r\nHost: x\r\n\r\n")
            s.settimeout(10)
            data = b""
            # The response's head, then the first part's.
            while data.count(b"\r\n\r\n") < 2:
                data += s.recv(65536)
            head, _, rest = data.partition(b"\r\n\r\n")
            self.assertTrue(head.startswith(b"HTTP/1.1 200"), head)
            self.assertIn(b"multipart/x-mixed-replace; boundary=frame", head)
            part, _, rest = rest.partition(b"\r\n\r\n")
            self.assertIn(b"--frame", part)
            n = int(part.split(b"Content-Length:")[1].split(b"\r\n")[0])
            while len(rest) < n:
                rest += s.recv(65536)
            s.close()
            from io import BytesIO

            from PIL import Image

            img = Image.open(BytesIO(rest[:n])).convert("RGB")
            self.assertEqual(img.size, (100, 60))
            # The red rectangle and the black around it survive the JPEG.
            r, g, b = img.getpixel((25, 15))
            self.assertTrue(r > 200 and g < 50 and b < 50, (r, g, b))
            self.assertTrue(max(img.getpixel((2, 40))) < 30)
        finally:
            proc.kill()
            proc.wait()
            proc.stdout.close()


if __name__ == "__main__":
    unittest.main()
