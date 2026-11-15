# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Draw a `Screen`'s changed rows on a display.

Each row is composed in a strip buffer with pygraphics, one fill and one text
call per run of cells that share colors, then sent with one ``blit_rect``.
Line-drawing cells aren't in the font: they're drawn as lines through the
middle of the cell, so boxes join from cell to cell at any font height.
When the display really scrolls (an SPI panel's scroll registers, or a desktop
window that copies them), a whole-screen scroll moves the picture and only the
new rows are drawn. Other displays redraw the rows that moved.
"""

from pygraphics import RGB565, FrameBuffer

from .screen import BOLD, REVERSE, UNDERLINE

# Which arms each line-drawing cell code from 11 to 25 has: 1 up, 2 down,
# 4 left, 8 right. The five horizontal scan lines have none.
_ARMS = b"\x05\x06\x0a\x09\x0f\x00\x00\x0c\x00\x00\x0b\x07\x0d\x0e\x03"


def scrolls_in_hardware(display):
    """Return ``True`` if setting ``display.vscroll`` moves the picture.

    The base display driver only stores the value. Drivers that act on it
    (SPI panels with scroll registers, the desktop and browser displays)
    override ``vscsad``.

    Args:
        display: A display driver.

    Returns:
        bool: Whether the driver scrolls.
    """
    try:
        from displaydev import DisplayDriver
    except ImportError:
        return False
    if not isinstance(display, DisplayDriver):
        return False
    return type(display).vscsad is not DisplayDriver.vscsad


class Renderer:
    """Draws a screen's dirty rows onto a display in RGB565.

    Args:
        display: A display driver with ``blit_rect`` and a 16-bit
            ``color_depth``.
        screen (Screen): The grid to draw.
        font (Font): A pygraphics font, 8 pixels wide.
        palette (Palette): Colors for the 256 ANSI indices, at 16 bits.
            Defaults to `AnsiPalette <palettes.ansi.AnsiPalette>`.
        hardware_scroll (bool): Use the display's scrolling. ``None`` (default)
            asks `scrolls_in_hardware`.

    Raises:
        ValueError: If the display isn't 16-bit, or the screen doesn't fit it.
    """

    def __init__(self, display, screen, font, palette=None, hardware_scroll=None):
        depth = getattr(display, "color_depth", 16)
        if depth != 16:
            raise ValueError("vtterm draws in RGB565; this display is %d-bit" % depth)
        self.display = display
        self.screen = screen
        self.font = font
        self.cw = font.width
        self.ch = font.height
        self.width = display.width
        if screen.cols * self.cw > self.width or screen.rows * self.ch > display.height:
            raise ValueError("a %dx%d screen doesn't fit a %dx%d display" % (screen.cols, screen.rows, self.width, display.height))
        if palette is None:
            from palettes.ansi import AnsiPalette

            palette = AnsiPalette(length=256, color_depth=16)
        self.palette = palette
        self._buf = bytearray(self.width * self.ch * 2)
        self._fb = FrameBuffer(self._buf, self.width, self.ch, RGB565)
        if hardware_scroll is None:
            hardware_scroll = scrolls_in_hardware(display)
        self.hardware_scroll = hardware_scroll
        self.offset = 0
        self._cursor = None
        if hardware_scroll:
            display.set_vscroll(0, display.height - screen.rows * self.ch)
            display.vscroll = 0

    def clear(self):
        """Fill the whole display with the default background and redraw every row."""
        if self.hardware_scroll:
            self.offset = 0
            self.display.vscroll = 0
        self.display.fill(self.palette[self.screen.default_bg])
        self._cursor = None
        self.screen.touch_all()

    def render(self):
        """Draw every row that changed since the last call, then show the display.

        Returns:
            int: How many rows were drawn.
        """
        s = self.screen
        rows = s.rows
        dirty = s.dirty
        n = s.scrolled
        if n:
            s.scrolled = 0
            if self.hardware_scroll and n < rows:
                self.offset = (self.offset + n) % rows
                self.display.vscroll = self.offset * self.ch
                if self._cursor is not None:
                    cy, cx = self._cursor
                    self._cursor = (cy - n, cx) if cy >= n else None
            else:
                s.touch_all()
        cursor = (s.y, s.x) if s.cursor_visible and not s.view else None
        if cursor != self._cursor:
            if self._cursor is not None:
                dirty[self._cursor[0]] = 1
            if cursor is not None:
                dirty[cursor[0]] = 1
        drawn = 0
        for y in range(rows):
            if dirty[y]:
                dirty[y] = 0
                self._row(y, cursor[1] if cursor is not None and cursor[0] == y else -1)
                drawn += 1
        self._cursor = cursor
        if drawn or n:
            self.display.show()
        return drawn

    def _glyph(self, code, px, color):
        # Draw one line-drawing cell into the strip at pixel column px.
        fb = self._fb
        cw = self.cw
        ch = self.ch
        cx = px + cw // 2
        cy = ch // 2
        if 11 <= code <= 25:
            arms = _ARMS[code - 11]
            if arms & 1:
                fb.vline(cx, 0, cy + 1, color)
            if arms & 2:
                fb.vline(cx, cy, ch - cy, color)
            if arms & 4:
                fb.hline(px, cy, cx - px + 1, color)
            if arms & 8:
                fb.hline(cx, cy, px + cw - cx, color)
            if not arms:
                # Scan lines 1, 3, 7 and 9; scan line 5 is the horizontal line.
                fb.hline(px, (0, ch // 4, 0, ch * 3 // 4, ch - 1)[code - 16], cw, color)
        elif code == 1:
            r = cw // 2 - 1
            for dy in range(-r, r + 1):
                w = r - abs(dy)
                fb.hline(cx - w, cy + dy, 2 * w + 1, color)
        elif code == 2:
            for y in range(ch):
                for x in range(px + (y & 1), px + cw, 2):
                    fb.pixel(x, y, color)
        elif code == 31:
            fb.fill_rect(cx - 1, cy - 1, 2, 2, color)

    def _row(self, y, cursor_x):
        s = self.screen
        chars, fgs, bgs, fls = s.visible(y)
        fb = self._fb
        pal = self.palette
        font = self.font
        cw = self.cw
        ch = self.ch
        cols = s.cols
        lines = min(chars) < 32
        x = 0
        while x < cols:
            fg = fgs[x]
            bg = bgs[x]
            fl = fls[x]
            end = x + 1
            if x != cursor_x:
                while end < cols and end != cursor_x and fgs[end] == fg and bgs[end] == bg and fls[end] == fl:
                    end += 1
            if fl & BOLD and fg < 8:
                fg += 8
            if fl & REVERSE:
                fg, bg = bg, fg
            if x == cursor_x:
                fg, bg = bg, fg
            fgc = pal[fg]
            px = x * cw
            w = (end - x) * cw
            fb.fill_rect(px, 0, w, ch, pal[bg])
            text = chars[x:end]
            if lines:
                for i in range(end - x):
                    c = text[i]
                    if c < 32:
                        text[i] = 32
                        self._glyph(c, px + i * cw, fgc)
            font.text(fb, bytes(text).decode(), px, 0, fgc)
            if fl & UNDERLINE:
                fb.hline(px, ch - 1, w, fgc)
            x = end
        if cols * cw < self.width:
            fb.fill_rect(cols * cw, 0, self.width - cols * cw, ch, pal[s.default_bg])
        py = ((y + self.offset) % s.rows) * ch
        self.display.blit_rect(self._buf, 0, py, self.width, ch)
