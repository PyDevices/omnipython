# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""The DEC line-drawing set: which cells it makes, and the lines they draw."""

from fakes import FakeDisplay
from vtterm import Terminal
from vtterm.parser import Parser
from vtterm.screen import Screen


def make(cols=12, rows=4):
    s = Screen(cols, rows)
    return s, Parser(s)


def test_g0_line_drawing_and_back():
    s, p = make()
    p.feed(b"\x1b(0lqk\x1b(Blqk")
    assert s.text(0)[:6] == "┌─┐lqk"
    assert bytes(s.lines[0][0][:6]) == b"\x0d\x12\x0clqk"


def test_every_line_character():
    s, p = make(32, 2)
    p.feed(b"\x1b(0jklmnopqrstuvwx`a~")
    assert s.text(0)[:18] == "┘┐┌└┼⎺⎻─⎼⎽├┤┴┬│◆▒·"


def test_symbols_without_a_glyph_are_ascii():
    s, p = make(32, 2)
    p.feed(b"\x1b(0_fgyz{|}AZ09")
    assert s.text(0)[:12] == " '#<>*!fAZ09"


def test_g1_shift_out_and_in():
    s, p = make()
    p.feed(b"\x1b)0q\x0eq\x0fq")
    assert s.text(0)[:3] == "q─q"


def test_designator_split_across_feeds():
    s, p = make()
    for b in b"\x1b(0x\x1b(Bx":
        p.feed(bytes([b]))
    assert s.text(0)[:2] == "│x"


def test_other_sets_are_ascii():
    s, p = make()
    p.feed(b"\x1b(0\x1b(Aq\x1b*0\x1b+0q")
    assert s.text(0)[:2] == "qq"


def test_save_and_restore_keep_the_set():
    s, p = make()
    p.feed(b"\x1b(0\x1b7\x1b(Bq\x1b8q")
    assert s.text(0)[0] == "─"
    p.feed(b"\x1b(B\x1b7\x1b(0\x1b8q")
    assert s.text(0)[1] == "q"


def test_reset_returns_to_ascii():
    s, p = make()
    p.feed(b"\x1b(0\x0e\x1b)0\x1bcq")
    assert s.text(0)[0] == "q"


def test_line_cells_wrap_and_take_the_pen():
    s, p = make(4, 2)
    p.feed(b"\x1b(0\x1b[31mqqqqqq")
    assert s.text(0) == "─" * 4
    assert s.text(1)[:2] == "─" * 2
    assert s.lines[1][1][1] == 1


def test_utf8_boxes_become_line_cells():
    s, p = make(16, 2)
    p.feed("┌─┬┐├┼┤└┴┘│".encode())
    assert s.text(0)[:11] == "┌─┬┐├┼┤└┴┘│"
    p.feed("\r\n┏━┓║╔╝╭╯┄┆◆".encode())
    assert s.text(1)[:11] == "┌─┐│┌┘┌┘─│◆"


def pixels(d, t, col, row):
    # The cell's pixels as rows of 0 and 1, 1 where the foreground is.
    r = t.renderer
    fg = r.palette[7]
    return [[1 if d.pixel(col * r.cw + x, row * r.ch + y) == fg else 0 for x in range(r.cw)] for y in range(r.ch)]


def test_lines_join_between_cells():
    d = FakeDisplay(80, 48)
    t = Terminal(d, font_height=16, hardware_scroll=False)
    t.write(b"\x1b[?25l\x1b(0lqk\r\nx x\r\nmqj")
    mid_y, mid_x = 8, 4
    # The horizontal line runs edge to edge at mid height, and nowhere else.
    across = pixels(d, t, 1, 0)
    assert across[mid_y] == [1] * 8
    assert sum(sum(r) for r in across) == 8
    # The vertical line runs top to bottom in the middle column.
    down = pixels(d, t, 0, 1)
    assert [r[mid_x] for r in down] == [1] * 16
    assert sum(sum(r) for r in down) == 16
    # Each corner reaches the two edges its neighbours are on, and not the others.
    tl, tr, bl, br = pixels(d, t, 0, 0), pixels(d, t, 2, 0), pixels(d, t, 0, 2), pixels(d, t, 2, 2)
    assert tl[mid_y][7] and tl[15][mid_x] and not tl[mid_y][0] and not tl[0][mid_x]
    assert tr[mid_y][0] and tr[15][mid_x] and not tr[mid_y][7] and not tr[0][mid_x]
    assert bl[mid_y][7] and bl[0][mid_x] and not bl[mid_y][0] and not bl[15][mid_x]
    assert br[mid_y][0] and br[0][mid_x] and not br[mid_y][7] and not br[15][mid_x]
    # The gap in the middle row stays empty.
    assert sum(sum(r) for r in pixels(d, t, 1, 1)) == 0


def test_tees_and_cross_have_their_arms():
    d = FakeDisplay(80, 48)
    t = Terminal(d, font_height=16, hardware_scroll=False)
    t.write(b"\x1b[?25l\x1b(0tuvwn")
    edges = []
    for col in range(5):
        c = pixels(d, t, col, 0)
        edges.append((c[0][4], c[15][4], c[8][0], c[8][7]))  # up, down, left, right
    assert edges == [(1, 1, 0, 1), (1, 1, 1, 0), (1, 0, 1, 1), (0, 1, 1, 1), (1, 1, 1, 1)]


def test_line_cells_use_cell_colors_and_cursor():
    d = FakeDisplay(80, 48)
    t = Terminal(d, font_height=16, hardware_scroll=False)
    t.write(b"\x1b[?25l\x1b(0\x1b[31;44mq\x1b[0mA")
    pal = t.renderer.palette
    r = t.renderer
    assert d.pixel(0, 8) == pal[1]
    assert d.pixel(0, 0) == pal[4]
    # A letter beside a line cell is still drawn from the font.
    assert any(d.pixel(r.cw + x, y) == pal[7] for x in range(8) for y in range(16))


def test_scan_lines_checkerboard_diamond_and_dot():
    d = FakeDisplay(80, 48)
    t = Terminal(d, font_height=16, hardware_scroll=False)
    t.write(b"\x1b[?25l\x1b(0opqrsa`~")
    heights = [[y for y in range(16) if pixels(d, t, col, 0)[y] == [1] * 8] for col in range(5)]
    assert heights == [[0], [4], [8], [12], [15]]
    checker = pixels(d, t, 5, 0)
    assert sum(sum(r) for r in checker) == 64
    assert checker[0][:2] == [1, 0] and checker[1][:2] == [0, 1]
    diamond = pixels(d, t, 6, 0)
    assert diamond[8][1:8] == [1] * 7 and sum(diamond[5]) == 1 and sum(diamond[4]) == 0
    assert sum(sum(r) for r in pixels(d, t, 7, 0)) == 4
