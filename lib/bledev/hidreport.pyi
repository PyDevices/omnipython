# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""HID report descriptors, and the reports they describe, as PyDevices events."""
import events
import keys
from collections.abc import Iterable
from typing import TypeAlias

_Event: TypeAlias = (
    events.Key
    | events.Motion
    | events.Button
    | events.Wheel
    | events.JoyAxisMotion
    | events.JoyHatMotion
    | events.JoyButtonDown
    | events.JoyButtonUp
)

INPUT: int
OUTPUT: int
FEATURE: int
CONSTANT: int
VARIABLE: int
RELATIVE: int
NULL_STATE: int
PAGE_DESKTOP: int
PAGE_SIMULATION: int
PAGE_KEYBOARD: int
PAGE_LED: int
PAGE_BUTTON: int
PAGE_CONSUMER: int
APP_POINTER: int
APP_MOUSE: int
APP_JOYSTICK: int
APP_GAMEPAD: int
APP_KEYBOARD: int
APP_KEYPAD: int
APP_MULTI_AXIS: int
APP_CONSUMER: int
ERROR_ROLLOVER: int

class HIDParseError(ValueError):
    """The descriptor is malformed: truncated, unbalanced, or impossible."""

class Field:
    """One main item: `count` values of `size` bits at bit `offset`."""

    kind: int
    report_id: int
    offset: int
    size: int
    count: int
    flags: int
    usages: list[int | tuple[int, int]]
    logical_min: int
    logical_max: int
    physical_min: int
    physical_max: int
    unit: int
    unit_exponent: int
    application: int
    def __init__(
        self,
        kind: int,
        report_id: int,
        offset: int,
        size: int,
        count: int,
        flags: int,
        usages: list[int | tuple[int, int]],
        logical_min: int,
        logical_max: int,
        physical_min: int,
        physical_max: int,
        unit: int,
        unit_exponent: int,
        application: int,
    ) -> None: ...
    @property
    def constant(self) -> bool: ...
    @property
    def variable(self) -> bool: ...
    @property
    def relative(self) -> bool: ...
    def usage(self, n: int) -> int | None:
        """The `n`-th usage in the list, ranges expanded; past the end, the last one."""
    def raw(self, data: bytes | bytearray | memoryview, n: int = 0) -> int:
        """Element `n`'s raw value from report `data` (without its ID), sign-extended if signed."""
    def values(self, data: bytes | bytearray | memoryview) -> list[int]:
        """Every element's raw value, as a list."""

class Report:
    """The fields of one report: its `kind`, its `report_id` (0 if unnumbered) and its size."""

    kind: int
    report_id: int
    fields: list[Field]
    bits: int
    def __init__(self, kind: int, report_id: int) -> None: ...
    @property
    def size(self) -> int:
        """Bytes, without the report ID."""

class ReportMap:
    """A parsed report descriptor."""

    descriptor: bytes
    reports: dict[tuple[int, int], Report]
    numbered: bool
    applications: list[int]
    def __init__(self, descriptor: bytes | bytearray | memoryview) -> None: ...
    def report(self, kind: int, report_id: int = 0) -> Report | None: ...
    def inputs(self) -> list[Report]:
        """The input reports, in report ID order."""

keycode = keys.hid_keycode
modifier_mask = keys.hid_modifiers

def consumer_keycode(usage: int) -> int | None:
    """The `keys.K_*` code for a consumer-page usage (`0xE9`, not extended), or `None`."""

class Decoder:
    """Turns one device's input reports into PyDevices events."""

    map: ReportMap
    instance_id: int
    bounds: tuple[int, int] | None
    num_axes: int
    num_hats: int
    num_buttons: int
    def __init__(self, report_map: ReportMap, instance_id: int = 0, bounds: tuple[int, int] | None = None) -> None: ...
    @property
    def held(self) -> frozenset[int]:
        """Keyboard usages held now."""
    @property
    def modifiers(self) -> int: ...
    def axis(self, n: int) -> float:
        """Axis `n`'s last value, -1.0..1.0 (0.0 before any report)."""
    def button(self, n: int) -> bool: ...
    def hat(self, n: int) -> tuple[int, int]: ...
    def feed(self, data: bytes | bytearray | memoryview | Iterable[int], report_id: int | None = None) -> tuple[_Event, ...]:
        """Decode one input report and return its events, as a tuple."""
    @property
    def pointer(self) -> tuple[int, int]:
        """Where the mouse pointer is, `(x, y)`: the sum of its motion, from (0, 0)."""
