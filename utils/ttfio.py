# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""ttfio on CPython: TrueType glyphs as coverage masks, the same API as
MicroPython's built-in ttfio (omnipython-builds' modules/ttfio), over FreeType.

    font = ttfio.Font(data)
    w, h, x, y, advance = font.glyph(0xE8B8, 20)
    mask = font.render(0xE8B8, 20)          # w*h bytes, 0..255

An app imports ttfio and doesn't care which runtime it's on. Glyphs are drawn
unhinted, as the C module draws them, so an icon looks the same on a desktop
as on a board: the same box, and ink within 2 %.
"""

import io

try:
    import freetype
except ImportError as e:  # pragma: no cover - the message is the point
    raise ImportError(
        "ttfio needs freetype-py on CPython. Install it with:  pip install freetype-py"
    ) from e

_FLAGS = freetype.FT_LOAD_RENDER | freetype.FT_LOAD_NO_HINTING


def _round(v):
    """Half away from zero, as the C module rounds."""
    return -int(0.5 - v) if v < 0 else int(v + 0.5)


def _codepoint(ch):
    if isinstance(ch, int) and not isinstance(ch, bool):
        if not 0 <= ch <= 0x10FFFF:
            raise ValueError("codepoint out of range")
        return ch
    if isinstance(ch, str) and len(ch) == 1:
        return ord(ch)
    raise TypeError("expected one character or a codepoint")


def _px(px):
    v = float(px)
    if not 0 < v <= 1024:
        raise ValueError("px must be above 0 and at most 1024")
    return v


class Font:
    """``Font(data, scratch=8192)``: a TrueType font from its bytes.

    ``scratch`` is checked as the C module checks it and otherwise unused:
    FreeType manages its own memory.
    """

    def __init__(self, data, scratch=8192):
        data = bytes(memoryview(data))
        if scratch < 256:
            raise ValueError("scratch must be at least 256 bytes")
        try:
            self._face = freetype.Face(io.BytesIO(data))
        except freetype.FT_Exception:
            raise ValueError("not a TrueType font") from None
        if not self._face.is_sfnt or not self._face.units_per_EM:
            raise ValueError("not a TrueType font")
        self._size = None

    @property
    def units_per_em(self):
        return self._face.units_per_EM

    def _index(self, ch):
        return self._face.get_char_index(_codepoint(ch))

    def _load(self, index, px):
        if self._size != px:
            self._face.set_char_size(int(round(px * 64)), 0, 72, 72)
            self._size = px
        self._face.load_glyph(index, _FLAGS)
        return self._face.glyph

    def has(self, ch):
        return self._index(ch) != 0

    def metrics(self, px):
        f = self._face
        s = _px(px) / f.units_per_EM
        hhea = (f.ascender, f.descender, f.height - f.ascender + f.descender)
        return tuple(_round(v * s) for v in hhea)

    def glyph(self, ch, px):
        index = self._index(ch)
        if not index:
            return None
        px = _px(px)
        g = self._load(index, px)
        adv = self._face.get_advance(index, freetype.FT_LOAD_NO_SCALE)
        return (g.bitmap.width, g.bitmap.rows, g.bitmap_left, -g.bitmap_top,
                _round(adv * px / self._face.units_per_EM))

    def render(self, ch, px, buf=None, *, stride=0):
        index = self._index(ch)
        if not index:
            raise KeyError("the font has no glyph for that character")
        g = self._load(index, _px(px))
        bm = g.bitmap
        w, h, pitch = bm.width, bm.rows, bm.pitch
        stride = stride or w
        if stride < w:
            raise ValueError("stride is narrower than the glyph")
        need = stride * (h - 1) + w if h else 0
        if buf is None:
            buf = bytearray(need)
        elif memoryview(buf).nbytes < need:
            raise ValueError("buf is too small for the glyph")
        out = memoryview(buf).cast("B")
        src = bytes(bm.buffer)
        for row in range(h):
            out[row * stride:row * stride + w] = src[row * pitch:row * pitch + w]
        return buf
