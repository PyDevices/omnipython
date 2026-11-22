# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Material Symbols icons at any size, drawn from a font that stays in flash.

``mask("home", 20)`` gives the antialiased shape of an icon as 8-bit alpha,
``size * size`` bytes, drawn by `ttfio` from a cut-down Material Symbols font
of 520 icons. Frozen into firmware, the font is read in place, so the icons
cost flash, not RAM; each mask you ask for is drawn once and kept in a small
cache. Draw a mask with `icons.gfx` in pygraphics or `icons.lvgl` in LVGL.
This module imports neither.

An app with icons of its own builds a font module with
``tools/make_icons.py`` and registers it with `add`.

Example::

    import icons
    data, w, h = icons.mask("wifi", 20)   # w * h alpha bytes, row by row
"""

import ttfio

from icons import _material

# Masks drawn so far, newest last: {(name, size): bytearray}. A mask is
# size * size bytes, 400 at 20 px, so 32 of them hold a screen's worth of
# icons in a few KB.
CACHE_SIZE = 32

# ttfio's working memory per font. 8 KB draws all but a few of the built-in
# icons at up to 48 px; a glyph that needs more doubles it, up to SCRATCH_MAX,
# and the font keeps the larger buffer from then on.
SCRATCH = 8192
SCRATCH_MAX = 65536

_fonts = [[_material, None, SCRATCH]]  # [module, ttfio.Font, its scratch]
_cache = {}
_order = []


def _find(name):
    key = name.encode()
    for entry in _fonts:
        table = entry[0].NAMES
        if table.startswith(key + b"\n"):
            pos = 0
        else:
            pos = table.find(b"\n" + key + b"\n")
            if pos < 0:
                continue
            pos += 1
        i = table.count(b"\n", 0, pos) * 3
        codes = entry[0].CODES
        if entry[1] is None:
            entry[1] = ttfio.Font(entry[0].FONT, SCRATCH)
        return entry, codes[i] << 16 | codes[i + 1] << 8 | codes[i + 2]
    raise ValueError(
        "no icon named %r; icons.names() lists the %d there are. Build it into a font module "
        "with tools/make_icons.py and register it with icons.add()." % (name, len(names()))
    )


def has(name):
    """Whether an icon named *name* is in the built-in font or one added with `add`."""
    try:
        _find(name)
    except ValueError:
        return False
    return True


def mask(name, size=24, buf=None):
    """The alpha mask of icon *name* at *size* pixels.

    The icon sits in a *size* by *size* square as Material Symbols designs it,
    with its padding, so icons of one size line up.

    Args:
        name (str): A Material Symbols name such as ``"home"``.
        size (int): The square's side in pixels, 8 to 256.
        buf (bytearray): Optional, ``size * size`` bytes to draw into. Without
            it the mask comes from the cache, drawn on first use; don't write
            into that one.

    Returns:
        ``(data, w, h)``: ``w * h`` alpha bytes, row by row, and the size.

    Raises:
        ValueError: There is no icon of that name, *size* is out of range, or
            *buf* is the wrong length.
    """
    if not 8 <= size <= 256:
        raise ValueError("size must be 8 to 256 px, not %r" % (size,))
    n = size * size
    if buf is None:
        key = (name, size)
        data = _cache.get(key)
        if data is not None:
            return memoryview(data), size, size
        data = _draw(name, size, bytearray(n))
        _cache[key] = data
        _order.append(key)
        while len(_order) > CACHE_SIZE:
            del _cache[_order.pop(0)]
        return memoryview(data), size, size
    if len(buf) != n:
        raise ValueError("buf is %d bytes; a %d px icon needs %d" % (len(buf), size, n))
    for i in range(n):
        buf[i] = 0
    return _draw(name, size, buf), size, size


def _render(entry, cp, size, buf=None, stride=0):
    while True:
        try:
            return entry[1].render(cp, size, buf, stride=stride)
        except MemoryError:
            if entry[2] >= SCRATCH_MAX:
                raise
            entry[2] *= 2
            entry[1] = ttfio.Font(entry[0].FONT, entry[2])


def _draw(name, size, buf):
    entry, cp = _find(name)
    w, h, x, y, _ = entry[1].glyph(cp, size)
    top = size + y  # Material Symbols' baseline is the square's bottom edge
    if x >= 0 and top >= 0 and x + w <= size and top + h <= size:
        _render(entry, cp, size, memoryview(buf)[top * size + x:], size)
        return buf
    # A glyph that spills out of its square: draw it alone, keep what fits.
    glyph = _render(entry, cp, size)
    for row in range(max(0, -top), min(h, size - top)):
        for col in range(max(0, -x), min(w, size - x)):
            buf[(top + row) * size + x + col] = glyph[row * w + col]
    return buf


def names():
    """Every icon name: the built-in font's, sorted, then each added font's."""
    out = []
    for entry in _fonts:
        out += entry[0].NAMES.decode().split("\n")[:-1]
    return out


def add(module):
    """Register a font module built by ``tools/make_icons.py``.

    Args:
        module: A module with ``FONT``, ``NAMES`` and ``CODES``.

    Raises:
        ValueError: A name is already taken, or ``CODES`` doesn't hold three
            bytes for each name.
    """
    count = module.NAMES.count(b"\n")
    if len(module.CODES) != 3 * count:
        raise ValueError(
            "icon module has %d bytes of CODES for %d names; it should have %d. "
            "Rebuild it with tools/make_icons.py." % (len(module.CODES), count, 3 * count)
        )
    taken = [n for n in module.NAMES.decode().split("\n")[:-1] if has(n)]
    if taken:
        raise ValueError("icon names already registered: %s" % ", ".join(taken))
    _fonts.append([module, None, SCRATCH])
