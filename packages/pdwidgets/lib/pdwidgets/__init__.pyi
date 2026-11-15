# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Widget toolkit for displays on microcontrollers and desktops.

Core names are always imported; widget classes load on first access.
"""

import events as events
from collections.abc import Iterator
from palettes import get_palette as get_palette
from typing import Any
from collections.abc import Callable

from . import pct as pct
from .display import Display as Display, tick as tick
from .screen import Screen as Screen
from .task import Task as Task
from .widget import Widget as Widget
from .widgets.accordion import Accordion as Accordion
from .widgets.app_bar import AppBar as AppBar
from .widgets.badge import Badge as Badge
from .widgets.bottom_sheet import BottomSheet as BottomSheet
from .widgets.button import Button as Button
from .widgets.card import Card as Card
from .widgets.chart import Chart as Chart
from .widgets.check_box import CheckBox as CheckBox
from .widgets.chip import Chip as Chip
from .widgets.color_picker import ColorPicker as ColorPicker
from .widgets.column import Column as Column
from .widgets.date_picker import DatePicker as DatePicker
from .widgets.dialog import Dialog as Dialog
from .widgets.digital_clock import DigitalClock as DigitalClock
from .widgets.divider import Divider as Divider
from .widgets.drawer import Drawer as Drawer
from .widgets.dropdown import Dropdown as Dropdown
from .widgets.form import Form as Form
from .widgets.form_row import FormRow as FormRow
from .widgets.gauge import Gauge as Gauge
from .widgets.grid import Grid as Grid
from .widgets.icon import Icon as Icon
from .widgets.icon_button import IconButton as IconButton
from .widgets.image import Image as Image
from .widgets.keyboard import Keyboard as Keyboard
from .widgets.label import Label as Label
from .widgets.list_view import ListView as ListView
from .widgets.menu import Menu as Menu
from .widgets.navigator import Navigator as Navigator
from .widgets.number_stepper import NumberStepper as NumberStepper
from .widgets.page import Page as Page
from .widgets.password_field import PasswordField as PasswordField
from .widgets.pin_pad import PinPad as PinPad
from .widgets.progress_bar import ProgressBar as ProgressBar
from .widgets.radio_button import RadioButton as RadioButton
from .widgets.radio_group import RadioGroup as RadioGroup
from .widgets.row import Row as Row
from .widgets.scroll_bar import ScrollBar as ScrollBar
from .widgets.scroll_view import ScrollView as ScrollView
from .widgets.segmented_control import SegmentedControl as SegmentedControl
from .widgets.slider import Slider as Slider
from .widgets.spinner import Spinner as Spinner
from .widgets.switch import Switch as Switch
from .widgets.tab_view import TabView as TabView
from .widgets.text_box import TextBox as TextBox
from .widgets.text_input import TextInput as TextInput
from .widgets.toast import Toast as Toast
from .widgets.toggle import Toggle as Toggle
from .widgets.toggle_button import ToggleButton as ToggleButton

DEBUG: bool
MARK_UPDATES: bool
PAD: int
TEXT_WIDTH: int
DEFAULT_PADDING: tuple[int, int, int, int]

class Area:
    """Integer rectangle `(x, y, w, h)` in display coordinates."""

    x: int
    y: int
    w: int
    h: int
    def __init__(self, *args: Any) -> None: ...
    def __iter__(self) -> Iterator[int]: ...
    def __add__(self, other: Area | tuple[int, int, int, int]) -> Area: ...
    def clip(self, other: Area | tuple[int, int, int, int]) -> Area: ...
    def inset(self, *args: int) -> Area: ...
    def offset(self, *args: int) -> Area: ...
    def shift(self, *args: int) -> Area: ...
    def contains(self, point: Any) -> bool: ...
    def contains_area(self, other: Area | tuple[int, int, int, int]) -> bool: ...
    def intersects(self, other: Area | tuple[int, int, int, int]) -> bool: ...
    def touches_or_intersects(self, other: Area | tuple[int, int, int, int]) -> bool: ...

class _IconSize:
    SMALL: int
    MEDIUM: int
    LARGE: int
    XLARGE: int
    def __contains__(self, item: object) -> bool: ...
    def __iter__(self) -> Iterator[int]: ...

class _TextSize:
    SMALL: int
    MEDIUM: int
    LARGE: int
    def __contains__(self, item: object) -> bool: ...
    def __iter__(self) -> Iterator[int]: ...

class _Position:
    LEFT: int
    RIGHT: int
    TOP: int
    BOTTOM: int
    OUTER: int
    def __contains__(self, item: object) -> bool: ...
    def __iter__(self) -> Iterator[int]: ...

class _Align:
    CENTER: int
    TOP_LEFT: int
    TOP: int
    TOP_RIGHT: int
    LEFT: int
    RIGHT: int
    BOTTOM_LEFT: int
    BOTTOM: int
    BOTTOM_RIGHT: int
    OUTER_TOP_LEFT: int
    OUTER_TOP: int
    OUTER_TOP_RIGHT: int
    OUTER_LEFT: int
    OUTER_RIGHT: int
    OUTER_BOTTOM_LEFT: int
    OUTER_BOTTOM: int
    OUTER_BOTTOM_RIGHT: int
    def __contains__(self, item: object) -> bool: ...
    def __iter__(self) -> Iterator[int]: ...

ICON_SIZE: _IconSize
TEXT_SIZE: _TextSize
POSITION: _Position
ALIGN: _Align

class IconTheme:
    """Resolve shipped icon assets as importable `pdwidgets.icons.*` modules."""

    def __init__(self, path: str | None = None) -> None: ...
    def __getattr__(self, name: str) -> Callable[[int], str]: ...

icon_theme: IconTheme

class ColorTheme:
    """Semantic color slots (RGB565 values) used by the widgets."""

    background: int
    on_background: int
    surface: int
    on_surface: int
    surface_variant: int
    outline: int
    shadow: int
    primary: int
    on_primary: int
    primary_variant: int
    secondary: int
    on_secondary: int
    secondary_variant: int
    tertiary: int
    on_tertiary: int
    tertiary_variant: int
    error: int
    on_error: int
    success: int
    on_success: int
    chip: int
    chip_selected: int
    on_chip: int
    on_chip_selected: int
    sheet_scrim: int
    menu_surface: int
    on_menu: int
    segment: int
    segment_selected: int
    on_segment: int
    on_segment_selected: int
    transparent: bool
    def __init__(self, pal: Any) -> None: ...
