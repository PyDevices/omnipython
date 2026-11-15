# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Device adapters and input mappers for appdev."""

import events
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from typing import Any, Protocol, TypeAlias

from .app import App

HOST: int
POINTER: int
ENCODER: int
KEYPAD: int
JOYSTICK: int
SWAP_XY: int
REVERSE_X: int
REVERSE_Y: int

_Event: TypeAlias = (
    events.Motion
    | events.Button
    | events.Wheel
    | events.Key
    | events.Quit
    | events.Unknown
    | events.Any
    | events.JoyAxisMotion
    | events.JoyButtonUp
    | events.JoyButtonDown
    | events.JoyHatMotion
    | events.JoyBallMotion
    | events.Finger
)

# One touch sample: a single point (x, y, ...), several points, or nothing when untouched.
_TouchSample: TypeAlias = Sequence[int] | Sequence[Sequence[int]] | None

class _TouchDisplay(Protocol):
    """What `Touch` needs of a display: its size, and a place to register itself."""

    @property
    def width(self) -> int: ...
    @property
    def height(self) -> int: ...
    touch_device: Any

class _JoystickDriver(Protocol):
    """A pygame-style joystick."""

    def get_numaxes(self) -> int: ...
    def get_numbuttons(self) -> int: ...
    def get_numhats(self) -> int: ...
    def get_numballs(self) -> int: ...
    def get_axis(self, i: int) -> float: ...
    def get_button(self, i: int) -> bool: ...
    def get_hat(self, i: int) -> tuple[int, int]: ...
    def get_ball(self, i: int) -> tuple[int, int]: ...
    def get_instance_id(self) -> int: ...

class Device:
    """Base class for hardware input device adapters."""

    type: int
    app: App | None
    user_data: Any
    def __init__(self) -> None: ...
    def subscribe(self, callback: Callable[..., Any], event_types: Collection[int] | None = None) -> None: ...
    def unsubscribe(self, callback: Callable[..., Any], event_types: Collection[int] | None = None) -> None: ...

class Touch(Device):
    """Touchscreen adapter mapped to MOUSEMOTION and MOUSEBUTTONDOWN/UP events."""

    points: tuple[tuple[int, ...], ...]
    def __init__(
        self,
        read: Callable[[], _TouchSample],
        display: _TouchDisplay | None = None,
        rotation_table: Sequence[int] | None = None,
    ) -> None: ...
    @property
    def rotation(self) -> int: ...
    @rotation.setter
    def rotation(self, value: int) -> None: ...
    def inject_clear(self) -> None:
        """Drop pending synthetic samples."""
    def inject_point(self, xy: tuple[int, int] | None) -> None:
        """Queue one sample: (x, y) display coords, or `None` for release."""
    def inject_tap(self, x: float, y: float, hold_frames: int = 1) -> None:
        """Queue a press and release at display coordinates."""
    def poll(self, *args: Any) -> list[_Event]: ...

class Keypad(Device):
    """Keypad/keyboard adapter mapped to KEYDOWN and KEYUP events."""

    def __init__(self, read: Callable[[], Iterable[int] | None]) -> None: ...
    def poll(self, *args: Any) -> list[_Event]: ...

class Encoder(Device):
    """Rotary encoder and button adapter mapped to MOUSEWHEEL and MOUSEBUTTON* events."""

    def __init__(
        self,
        read: Callable[[], int | None],
        *,
        button_read: Callable[[], object] | None = None,
        button: int = 2,
    ) -> None: ...
    def poll(self, *args: Any) -> list[_Event]: ...

class Joystick(Device):
    """Joystick adapter mapped to SDL Joy* events."""

    driver: _JoystickDriver
    emulate_digital: Sequence[tuple[int, int]] | None
    digital_threshold: float
    def __init__(
        self,
        joystick_driver: _JoystickDriver,
        *,
        emulate_digital: Sequence[tuple[int, int]] | None = None,
        digital_threshold: float = 0.5,
    ) -> None: ...
    def poll(self, *args: Any) -> list[_Event]: ...

class HostEvents(Device):
    """Host event pump adapter for SDL2/PyGame and OS events."""

    scale: float
    def __init__(
        self,
        host_read: Callable[[], Iterable[_Event] | None],
        display: Any = None,
        event_filter: Collection[int] | None = None,
    ) -> None: ...
    def poll(self, *args: Any) -> list[_Event]: ...

class TouchGrid:
    """Maps a screen rectangle into a grid of app key IDs."""

    x: float
    y: float
    w: float
    h: float
    cols: int
    rows: int
    key_width: float
    key_height: float
    def __init__(
        self,
        app: App,
        x: float,
        y: float,
        w: float,
        h: float,
        cols: int = 3,
        rows: int = 3,
        keys: Sequence[int] | None = None,
        translate: Callable[[tuple[int, int]], tuple[float, float]] | None = None,
        on_press: Callable[[int], Any] | None = None,
        on_release: Callable[[int], Any] | None = None,
    ) -> None: ...
    def read(self) -> list[int] | None:
        """Return keys pressed since the last read (edge triggered), or `None`."""
    def read_held(self) -> list[int]:
        """Return keys currently held down (level triggered)."""

class JoyMap:
    """Maps joystick hat directions and buttons onto held key codes."""

    def __init__(
        self,
        app: App,
        joymap: Mapping[int, Mapping[str, Mapping[int, int | tuple[int, int, int, int]]]],
    ) -> None: ...
    def read(self) -> list[int]:
        """Return key codes currently held according to joymap."""
