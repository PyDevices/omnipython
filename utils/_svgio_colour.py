# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""The colours svgio reads the same on every runtime.

``colour(text)`` gives ``(r, g, b)`` for a colour written as ``#rgb``,
``#rrggbb``, ``rgb()`` or one of the ten names MicroPython's svgio knows,
and None for anything else. Both of svgio's backends here use it, so
``decode(colors=)`` swaps the same colours on a desktop, in a browser and
on a board.
"""

import re

_HEX = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})$")
_RGB = re.compile(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)")
_RGB_PERCENT = re.compile(r"rgb\(\s*\+?(\d+(?:\.\d+)?)%\s*,\s*\+?(\d+(?:\.\d+)?)%\s*,\s*\+?(\d+(?:\.\d+)?)%\s*\)")
_NAMED = {
    "red": (255, 0, 0),
    "green": (0, 128, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "cyan": (0, 255, 255),
    "magenta": (255, 0, 255),
    "black": (0, 0, 0),
    "grey": (128, 128, 128),
    "gray": (128, 128, 128),
    "white": (255, 255, 255),
}


def colour(text):
    """``text`` as (r, g, b), or None when it isn't a colour every runtime reads."""
    text = text.strip()
    m = _HEX.match(text)
    if m:
        digits = m.group(1)
        if len(digits) == 3:
            digits = "".join(c * 2 for c in digits)
        return int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16)
    m = _RGB.match(text)
    if m:
        return tuple(min(255, int(v)) for v in m.groups())
    m = _RGB_PERCENT.match(text)
    if m:
        return tuple(min(255, int(float(v) * 255 / 100 + 0.5)) for v in m.groups())
    return _NAMED.get(text)
