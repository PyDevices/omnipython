# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""Viper loops for `displaydev.remotedisplay`: hash tiles, pack runs.

A module of its own so a build without the native emitter fails to import
it, and remotedisplay uses its plain-Python versions instead.
"""

import sys

if sys.implementation.name != "micropython":
    raise ImportError("viper runs on MicroPython only")

import micropython


@micropython.viper
def _diff(fb, hashes, stride: int, w: int, h: int, flags, tx0: int, ty0: int, tx1: int, ty1: int) -> int:
    # Hash each 32x16 tile in columns tx0..tx1-1 and rows ty0..ty1-1, mark
    # the ones whose hash changed and keep the new hash. A hash per tile in
    # place of a copy of the frame halves what is read from PSRAM, and keeps
    # a frame-sized buffer out of the garbage collector's way.
    f = ptr8(flags)
    hs = ptr32(hashes)
    a2 = ptr16(fb)
    a4 = ptr32(fb)
    wide = (stride & 1) == 0 and (w & 1) == 0
    cols_t = (w + 31) >> 5
    n = 0
    ty = ty0
    while ty < ty1:
        y0 = ty << 4
        rows = h - y0
        if rows > 16:
            rows = 16
        tx = tx0
        while tx < tx1:
            x0 = tx << 5
            cols = w - x0
            if cols > 32:
                cols = 32
            hv = 0x1234567
            r = 0
            while r < rows:
                p = (y0 + r) * stride + x0
                c = 0
                if wide:
                    p >>= 1
                    k = cols >> 1
                    while c < k:
                        hv = (hv ^ a4[p + c]) * 16777619
                        c += 1
                else:
                    while c < cols:
                        hv = (hv ^ a2[p + c]) * 16777619
                        c += 1
                r += 1
            # The same width on a 32-bit board and a 64-bit host, where a
            # word holds more than the 32 bits kept in hashes.
            hv &= 0x3FFFFFFF
            i = ty * cols_t + tx
            if hs[i] != hv:
                hs[i] = hv
                f[i] = 1
                n += 1
            else:
                f[i] = 0
            tx += 1
        ty += 1
    return n


@micropython.viper
def _rle(fb, stride: int, x: int, y: int, w: int, h: int, dst, off: int, cap: int) -> int:
    # The rectangle as (count, pixel) pairs at dst[off:]; -1 when that would
    # take more than cap bytes.
    s = ptr16(fb)
    d = ptr16(dst)
    o = off >> 1
    lim = o + (cap >> 1)
    run = 0
    pv = 0
    r = 0
    while r < h:
        p = (y + r) * stride + x
        c = 0
        while c < w:
            v = s[p + c]
            if run != 0 and v == pv and run < 65535:
                run += 1
            else:
                if run:
                    if o + 2 > lim:
                        return -1
                    d[o] = run
                    d[o + 1] = pv
                    o += 2
                pv = v
                run = 1
            c += 1
        r += 1
    if run:
        if o + 2 > lim:
            return -1
        d[o] = run
        d[o + 1] = pv
        o += 2
    return (o << 1) - off


@micropython.viper
def _raw(fb, stride: int, x: int, y: int, w: int, h: int, dst, off: int) -> int:
    s = ptr16(fb)
    d = ptr16(dst)
    o = off >> 1
    r = 0
    while r < h:
        p = (y + r) * stride + x
        c = 0
        while c < w:
            d[o] = s[p + c]
            o += 1
            c += 1
        r += 1
    return w * h * 2


@micropython.viper
def _pal(fb, stride: int, x: int, y: int, w: int, h: int, dst, off: int, cap: int, scratch) -> int:
    # The rectangle as a palette of up to 16 colours and a 4-bit index per
    # pixel, high nibble first: u16 count, u16 0, the colours, the indices,
    # padded to an even length. -1 when it has more colours or would take
    # more than cap bytes. dst is written only once it fits.
    s = ptr16(fb)
    pal = ptr16(scratch)
    nc = 0
    r = 0
    while r < h:
        p = (y + r) * stride + x
        c = 0
        while c < w:
            v = s[p + c]
            k = 0
            while k < nc:
                if pal[k] == v:
                    break
                k += 1
            if k == nc:
                if nc == 16:
                    return -1
                pal[nc] = v
                nc += 1
            c += 1
        r += 1
    size = 4 + 2 * nc + ((w * h + 1) >> 1)
    size = (size + 1) & ~1
    if size > cap:
        return -1
    d = ptr16(dst)
    b = ptr8(dst)
    o = off >> 1
    d[o] = nc
    d[o + 1] = 0
    k = 0
    while k < nc:
        d[o + 2 + k] = pal[k]
        k += 1
    q = off + 4 + 2 * nc
    half = 0
    r = 0
    while r < h:
        p = (y + r) * stride + x
        c = 0
        while c < w:
            v = s[p + c]
            k = 0
            while pal[k] != v:
                k += 1
            if half:
                b[q] = b[q] | k
                q += 1
                half = 0
            else:
                b[q] = k << 4
                half = 1
            c += 1
        r += 1
    if half:
        q += 1
    if (q - off) & 1:
        b[q] = 0
        q += 1
    return q - off
