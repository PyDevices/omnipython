# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
import keys
from _typeshed import Incomplete

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

class HIDParseError(ValueError): ...

class Field:
    kind: Incomplete
    report_id: Incomplete
    offset: Incomplete
    size: Incomplete
    count: Incomplete
    flags: Incomplete
    usages: Incomplete
    logical_min: Incomplete
    logical_max: Incomplete
    physical_min: Incomplete
    physical_max: Incomplete
    unit: Incomplete
    unit_exponent: Incomplete
    application: Incomplete
    def __init__(self, kind, report_id, offset, size, count, flags, usages, logical_min, logical_max, physical_min, physical_max, unit, unit_exponent, application) -> None: ...
    @property
    def constant(self): ...
    @property
    def variable(self): ...
    @property
    def relative(self): ...
    def usage(self, n): ...
    def raw(self, data, n: int = 0): ...
    def values(self, data): ...

class Report:
    kind: Incomplete
    report_id: Incomplete
    fields: Incomplete
    bits: int
    def __init__(self, kind, report_id) -> None: ...
    @property
    def size(self): ...

class ReportMap:
    descriptor: Incomplete
    reports: Incomplete
    numbered: bool
    applications: Incomplete
    def __init__(self, descriptor) -> None: ...
    def report(self, kind, report_id: int = 0): ...
    def inputs(self): ...
keycode = keys.hid_keycode
modifier_mask = keys.hid_modifiers

def consumer_keycode(usage): ...

class Decoder:
    map: Incomplete
    instance_id: Incomplete
    bounds: Incomplete
    num_axes: Incomplete
    num_hats: Incomplete
    num_buttons: int
    def __init__(self, report_map, instance_id: int = 0, bounds=None) -> None: ...
    @property
    def held(self): ...
    @property
    def modifiers(self): ...
    def axis(self, n): ...
    def button(self, n): ...
    def hat(self, n): ...
    def feed(self, data, report_id=None): ...
    @property
    def pointer(self): ...
