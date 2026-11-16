# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Tell the program on a terminal where it was clicked or touched.

A full-screen program asks for mouse reports with an escape code, and from
then on a terminal sends it bytes for each press, release and drag. `Mouse`
makes those bytes from a touchscreen's points or a desktop's mouse events,
and returns ``None`` while no program has asked, so it's safe to feed all the
time.

What a program can ask for, each with ``ESC [ ? n h``:

* ``9``: presses only.
* ``1000``: presses and releases, and the wheel.
* ``1002``: the same, and movement while a button or finger is down.
* ``1003``: the same, and all movement.
* ``1006``: reports in the SGR form, ``ESC [ < b ; x ; y M``, which has no
  limit on the column and row. Without it reports are the three bytes after
  ``ESC [ M``, which stop at column and row 223.

Example:
    >>> from vtterm.mouse import Mouse
    >>> mouse = Mouse(terminal)
    >>> report = mouse.touch(120, 64, True)   # a finger lands
    >>> if report:
    ...     link.write(report)
"""

#: Button numbers in a report.
LEFT = 0
MIDDLE = 1
RIGHT = 2
#: No button: movement with nothing held.
NONE = 3
WHEEL_UP = 64
WHEEL_DOWN = 65

# Event types, the same values as OmniPython's events module.
_MOTION = 0x400
_DOWN = 0x401
_UP = 0x402
_WHEEL = 0x403


def mouse_bytes(screen, button, col, row, pressed=True, moved=False):
    """Return the report for one mouse event, or ``None`` if the program didn't ask for it.

    Args:
        screen (Screen): Its ``mouse`` and ``mouse_sgr`` modes pick what is
            reported and in which form.
        button (int): `LEFT`, `MIDDLE`, `RIGHT`, `WHEEL_UP`, `WHEEL_DOWN`, or
            `NONE` for movement with no button held.
        col (int): Column of the cell, from 0.
        row (int): Row of the cell, from 0.
        pressed (bool): ``False`` for a release.
        moved (bool): The pointer moved to this cell with ``button`` held.

    Returns:
        bytes: What to send the program, or ``None``.
    """
    mode = screen.mouse
    if not mode:
        return None
    if moved:
        if mode < 1002 or (mode == 1002 and button == NONE):
            return None
    elif button == NONE:
        return None
    elif mode == 9 and (not pressed or button > RIGHT):
        return None
    elif button >= WHEEL_UP and not pressed:
        return None
    col = max(0, min(screen.cols - 1, col)) + 1
    row = max(0, min(screen.rows - 1, row)) + 1
    code = button + 32 if moved else button
    if screen.mouse_sgr:
        return ("\x1b[<%d;%d;%d%s" % (code, col, row, "M" if pressed else "m")).encode()
    if col > 223 or row > 223:
        return None
    if not pressed:
        code = 3
    return b"\x1b[M" + bytes((32 + code, 32 + col, 32 + row))


class Mouse:
    """Turns touches and mouse events on a terminal's display into reports.

    Args:
        terminal (Terminal): The terminal that was touched.
        x (int): Left edge of the terminal's display, in the coordinates the
            touches and events use. ``0`` when it fills the panel.
        y (int): Top edge, the same way.

    Attributes:
        cell (tuple): The ``(col, row)`` last touched or pointed at.
    """

    def __init__(self, terminal, x=0, y=0):
        self.screen = terminal.screen
        self._cw = terminal.renderer.cw
        self._ch = terminal.renderer.ch
        self._x = x
        self._y = y
        self._held = NONE
        self.cell = (0, 0)

    def _at(self, pos):
        s = self.screen
        col = max(0, min(s.cols - 1, (pos[0] - self._x) // self._cw))
        row = max(0, min(s.rows - 1, (pos[1] - self._y) // self._ch))
        cell = (col, row)
        changed = cell != self.cell
        self.cell = cell
        return changed

    def _report(self, button, pressed=True, moved=False):
        return mouse_bytes(self.screen, button, self.cell[0], self.cell[1], pressed, moved)

    def touch(self, x, y, down):
        """Report a finger on the display, as the left button.

        Call it with each reading of the touchscreen. A finger landing is a
        press, moving to another cell is a drag, and lifting is a release.

        Args:
            x (int): Pixel column of the touch. Ignored when ``down`` is false.
            y (int): Pixel row of the touch.
            down (bool): Whether a finger is on the display.

        Returns:
            bytes: What to send the program, or ``None``.
        """
        if down:
            changed = self._at((x, y))
            if self._held == NONE:
                self._held = LEFT
                return self._report(LEFT)
            return self._report(LEFT, moved=True) if changed else None
        if self._held == NONE:
            return None
        self._held = NONE
        return self._report(LEFT, pressed=False)

    def event(self, e):
        """Report a mouse event from a display's ``get_events``.

        Args:
            e: An event with a ``type``. Button events have ``pos`` and
                ``button`` (1 left, 2 middle, 3 right), motion events have
                ``pos``, and wheel events have ``y``, positive away from you.

        Returns:
            bytes: What to send the program, or ``None``, also for an event
            that isn't from a mouse.
        """
        t = getattr(e, "type", None)
        if t == _DOWN or t == _UP:
            if not 1 <= e.button <= 3:
                return None
            self._at(e.pos)
            button = e.button - 1
            if t == _DOWN:
                self._held = button
                return self._report(button)
            self._held = NONE
            return self._report(button, pressed=False)
        if t == _MOTION:
            if self._at(e.pos):
                return self._report(self._held, moved=True)
        elif t == _WHEEL and e.y:
            return self._report(WHEEL_UP if e.y > 0 else WHEEL_DOWN)
        return None
