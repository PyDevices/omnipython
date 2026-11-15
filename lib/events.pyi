# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""SDL2/PyGame-style event types and namedtuple event classes."""

from typing import NamedTuple

QUIT: int
KEYDOWN: int
KEYUP: int
MOUSEMOTION: int
MOUSEBUTTONDOWN: int
MOUSEBUTTONUP: int
MOUSEWHEEL: int
JOYAXISMOTION: int
JOYBALLMOTION: int
JOYHATMOTION: int
JOYBUTTONDOWN: int
JOYBUTTONUP: int
FINGERDOWN: int
FINGERUP: int
FINGERMOTION: int
filter: list[int]

class Unknown(NamedTuple):
    type: int

class Motion(NamedTuple):
    type: int
    pos: tuple[int, int]
    rel: tuple[int, int]
    buttons: tuple[int, int, int]
    touch: bool
    window: int | None

class Button(NamedTuple):
    type: int
    pos: tuple[int, int]
    button: int
    touch: bool
    window: int | None

class Wheel(NamedTuple):
    type: int
    flipped: bool
    x: int
    y: int
    precise_x: float
    precise_y: float
    touch: bool
    window: int | None

class Key(NamedTuple):
    type: int
    name: str
    key: int
    mod: int
    scancode: int
    window: int | None

class Quit(NamedTuple):
    type: int

class Any(NamedTuple):
    type: int

class JoyAxisMotion(NamedTuple):
    type: int
    instance_id: int
    axis: int
    value: float

class JoyButtonUp(NamedTuple):
    type: int
    instance_id: int
    button: int

class JoyButtonDown(NamedTuple):
    type: int
    instance_id: int
    button: int

class JoyHatMotion(NamedTuple):
    type: int
    instance_id: int
    hat: int
    value: tuple[int, int]

class JoyBallMotion(NamedTuple):
    type: int
    instance_id: int
    ball: int
    rel: tuple[int, int]

class Finger(NamedTuple):
    type: int
    pos: tuple[float, float]
    finger_id: int
    window: int | None

def register_event(
    name: str | None = None,
    value: int | None = None,
    *,
    fields: str | None = None,
    types: dict[str, int] | list[tuple[str, int]] | None = None,
    classes: dict[str, str] | None = None,
) -> None:
    """Register custom event type(s) and optional namedtuple class(es)."""
