# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Serve a RemoteDisplay for test_remotedisplay.py, under MicroPython.

Usage: micropython remotedisplay_server.py PORT SECONDS

Draws a test picture, prints ``crc <hex>`` of its frame, then serves for
SECONDS and prints each click it gets as ``click X Y`` (and the new CRC
after it marks the spot).
"""

import binascii
import sys
import time

import events
from displaydev.remotedisplay import RemoteDisplay

W, H = 100, 60


def picture(d):
    d.fill(0)
    d.fill_rect(5, 5, 40, 20, 0xF800)
    d.fill_rect(50, 10, 30, 40, 0x07E0)
    # A noisy band, where runs would be larger than raw pixels.
    for y in range(H - 16, H):
        for x in range(W):
            d.pixel(x, y, (x * 409 + y * 7919) & 0xFFFF)


def main():
    port = int(sys.argv[1])
    secs = int(sys.argv[2])
    d = RemoteDisplay(W, H, port=port, quiet=True)
    picture(d)
    print("crc %08x" % (binascii.crc32(d._raw_buffer) & 0xFFFFFFFF))
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < secs * 1000:
        d.server.poll()
        for e in d.get_events():
            if e.type == events.MOUSEBUTTONDOWN:
                d.fill_rect(e.pos[0], e.pos[1], 3, 3, 0x001F)
                print("click %d %d" % e.pos)
                print("crc %08x" % (binascii.crc32(d._raw_buffer) & 0xFFFFFFFF))
        time.sleep_ms(5)
    d.deinit()


main()
