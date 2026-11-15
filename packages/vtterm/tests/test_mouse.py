# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Mouse and touch reports: what a program asks for, and the bytes it gets."""

from fakes import FakeDisplay
from vtterm import Terminal
from vtterm.keys import KeyEvents
from vtterm.mouse import LEFT, NONE, RIGHT, WHEEL_DOWN, WHEEL_UP, Mouse, mouse_bytes
from vtterm.parser import Parser
from vtterm.screen import Screen

MOTION, DOWN, UP, WHEEL, KEYDOWN = 0x400, 0x401, 0x402, 0x403, 0x300


class Event:
    def __init__(self, type, **fields):  # noqa: A002 - the events' own field name
        self.type = type
        for k in fields:
            setattr(self, k, fields[k])


def asked(codes, cols=40, rows=10):
    s = Screen(cols, rows)
    Parser(s).feed(codes)
    return s


def test_modes_set_and_clear():
    s = asked(b"")
    p = Parser(s)
    assert (s.mouse, s.mouse_sgr) == (0, False)
    p.feed(b"\x1b[?1000;1006h")
    assert (s.mouse, s.mouse_sgr) == (1000, True)
    p.feed(b"\x1b[?1002h")
    assert s.mouse == 1002
    p.feed(b"\x1b[?1000l")  # turning off a mode that isn't the one in use changes nothing
    assert s.mouse == 1002
    p.feed(b"\x1b[?1002l\x1b[?1006l")
    assert (s.mouse, s.mouse_sgr) == (0, False)
    p.feed(b"\x1b[?1003h\x1b[?1006h\x1bc")
    assert (s.mouse, s.mouse_sgr) == (0, False)


def test_nothing_reported_until_asked():
    s = asked(b"")
    assert mouse_bytes(s, LEFT, 3, 2) is None
    assert mouse_bytes(s, LEFT, 3, 2, pressed=False) is None


def test_press_and_release_bytes():
    s = asked(b"\x1b[?1000h")
    assert mouse_bytes(s, LEFT, 0, 0) == b"\x1b[M !!"
    assert mouse_bytes(s, RIGHT, 4, 2) == b"\x1b[M\x22\x25\x23"
    assert mouse_bytes(s, LEFT, 4, 2, pressed=False) == b"\x1b[M\x23\x25\x23"
    assert mouse_bytes(s, WHEEL_UP, 0, 0) == b"\x1b[M`!!"
    assert mouse_bytes(s, WHEEL_DOWN, 0, 0) == b"\x1b[Ma!!"
    assert mouse_bytes(s, WHEEL_UP, 0, 0, pressed=False) is None


def test_sgr_bytes():
    s = asked(b"\x1b[?1000h\x1b[?1006h")
    assert mouse_bytes(s, LEFT, 0, 0) == b"\x1b[<0;1;1M"
    assert mouse_bytes(s, RIGHT, 38, 9, pressed=False) == b"\x1b[<2;39;10m"
    assert mouse_bytes(s, WHEEL_DOWN, 5, 5) == b"\x1b[<65;6;6M"


def test_motion_needs_its_mode():
    s = asked(b"\x1b[?1000h\x1b[?1006h")
    assert mouse_bytes(s, LEFT, 1, 1, moved=True) is None
    s = asked(b"\x1b[?1002h\x1b[?1006h")
    assert mouse_bytes(s, LEFT, 1, 1, moved=True) == b"\x1b[<32;2;2M"
    assert mouse_bytes(s, NONE, 1, 1, moved=True) is None
    s = asked(b"\x1b[?1003h")
    assert mouse_bytes(s, NONE, 1, 1, moved=True) == b"\x1b[M\x43\x22\x22"
    assert mouse_bytes(s, LEFT, 1, 1, moved=True) == b"\x1b[M\x40\x22\x22"


def test_presses_only_mode():
    s = asked(b"\x1b[?9h")
    assert mouse_bytes(s, LEFT, 0, 0) == b"\x1b[M !!"
    assert mouse_bytes(s, LEFT, 0, 0, pressed=False) is None
    assert mouse_bytes(s, WHEEL_UP, 0, 0) is None


def test_far_cells_need_sgr():
    s = asked(b"\x1b[?1000h", cols=300, rows=4)
    assert mouse_bytes(s, LEFT, 222, 0) == b"\x1b[M \xff!"
    assert mouse_bytes(s, LEFT, 223, 0) is None
    s.mouse_sgr = True
    assert mouse_bytes(s, LEFT, 299, 3) == b"\x1b[<0;300;4M"
    assert mouse_bytes(s, LEFT, 900, 90) == b"\x1b[<0;300;4M"  # held to the grid


def terminal(codes):
    t = Terminal(FakeDisplay(80, 48), font_height=16, hardware_scroll=False)
    t.feed(codes)
    return t


def test_touch_is_press_drag_release():
    t = terminal(b"\x1b[?1002h\x1b[?1006h")
    m = Mouse(t)
    assert m.touch(20, 20, True) == b"\x1b[<0;3;2M"
    assert m.touch(22, 25, True) is None  # the same cell
    assert m.touch(40, 40, True) == b"\x1b[<32;6;3M"
    assert m.touch(0, 0, False) == b"\x1b[<0;6;3m"  # lifted where it last was
    assert m.touch(0, 0, False) is None


def test_touch_without_drag_mode_and_unasked():
    t = terminal(b"\x1b[?1000h")
    m = Mouse(t)
    assert m.touch(0, 0, True) == b"\x1b[M !!"
    assert m.touch(79, 47, True) is None
    assert m.touch(0, 0, False) == b"\x1b[M#*#"
    quiet = Mouse(terminal(b""))
    assert quiet.touch(5, 5, True) is None
    assert quiet.touch(5, 5, False) is None


def test_touch_offset_and_edges():
    t = terminal(b"\x1b[?1000h\x1b[?1006h")
    m = Mouse(t, x=100, y=50)
    assert m.touch(100 + 8, 50 + 16, True) == b"\x1b[<0;2;2M"
    m.touch(0, 0, False)
    assert m.touch(5, 5, True) == b"\x1b[<0;1;1M"  # outside, held to the nearest cell
    m.touch(0, 0, False)
    assert m.touch(9999, 9999, True) == b"\x1b[<0;10;3M"


def test_mouse_events():
    t = terminal(b"\x1b[?1003h\x1b[?1006h")
    m = Mouse(t)
    assert m.event(Event(MOTION, pos=(9, 17))) == b"\x1b[<35;2;2M"
    assert m.event(Event(MOTION, pos=(10, 18))) is None
    assert m.event(Event(DOWN, pos=(9, 17), button=3)) == b"\x1b[<2;2;2M"
    assert m.event(Event(MOTION, pos=(17, 17))) == b"\x1b[<34;3;2M"
    assert m.event(Event(UP, pos=(17, 17), button=3)) == b"\x1b[<2;3;2m"
    assert m.event(Event(WHEEL, y=1)) == b"\x1b[<64;3;2M"
    assert m.event(Event(WHEEL, y=-1)) == b"\x1b[<65;3;2M"
    assert m.event(Event(WHEEL, y=0)) is None
    assert m.event(Event(DOWN, pos=(0, 0), button=7)) is None
    assert m.event(Event(KEYDOWN, key=97, mod=0)) is None


def test_key_events_carry_mouse_reports_in_order():
    t = terminal(b"\x1b[?1000h\x1b[?1006h")
    queue = [[Event(KEYDOWN, key=97, mod=0), Event(DOWN, pos=(0, 0), button=1), Event(UP, pos=(0, 0), button=1), Event(KEYDOWN, key=98, mod=0)]]
    seen = []
    keys = KeyEvents(lambda: queue.pop() if queue else None, t.screen, other=seen.append, mouse=Mouse(t))
    assert keys.read() == b"a\x1b[<0;1;1M\x1b[<0;1;1mb"
    assert len(seen) == 2
    assert keys.read() is None
