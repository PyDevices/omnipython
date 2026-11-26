# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
from collections.abc import Callable, Iterable, Sequence
from typing import Any

from appdev.app import App
from displaydev import DisplayDriver as _DisplayDriver
from multimer import Timer

app: App
display_drv: _DisplayDriver
LVGL_PERIOD_MS: int
LVGL_REFR_PERIOD_MS: int
HOST: int
POINTER: int
ENCODER: int
KEYPAD: int
JOYSTICK: int

class InputDevice:
    """Small input adapter used only by the LVGL bridge."""
    type: int
    responses: Sequence[int]
    def __init__(self, read: Callable[..., Any] | None = None, data: Any = None, read2: Callable[..., Any] | None = None, data2: Any = None) -> None: ...
    @property
    def app(self) -> App | None: ...
    @app.setter
    def app(self, value: App | None) -> None: ...
    @property
    def user_data(self) -> Any: ...
    @user_data.setter
    def user_data(self, value: Any) -> None: ...
    def subscribe(self, callback: Callable[..., Any], event_types: Iterable[int] | None = None) -> None: ...
    def unsubscribe(self, callback: Callable[..., Any], event_types: Iterable[int] | None = None) -> None: ...
    def poll(self, *args: Any) -> list[tuple[Any, ...]]: ...

class HostInput(InputDevice):
    """Adapt a host display's `get_events` callback for LVGL."""
    type: int
    scale: float
    def __init__(self, host_read: Callable[[], list[tuple[Any, ...]] | None], display: _DisplayDriver | None = None, event_filter: Sequence[int] | None = None) -> None: ...

class TouchInput(InputDevice):
    """Adapt a board touch callable to pointer events for LVGL."""
    type: int
    responses: Sequence[int]
    points: tuple[Any, ...]
    def __init__(self, read: Callable[[], Any], display: _DisplayDriver, rotation_table: Sequence[int] | None = None) -> None: ...
    @property
    def rotation(self) -> int: ...
    @rotation.setter
    def rotation(self, value: int) -> None: ...

class KeypadInput(InputDevice):
    """Adapt a pressed-key collection to KEYDOWN/KEYUP events."""
    type: int
    responses: Sequence[int]
    def __init__(self, read: Callable[[], Any]) -> None: ...

class EncoderInput(InputDevice):
    """Adapt an encoder position and optional button to LVGL events."""
    type: int
    responses: Sequence[int]
    def __init__(self, read: Callable[[], int], button_read: Callable[[], bool] | None = None, button: int = 2) -> None: ...

class VirtualDevices:
    """Fan one host input into LVGL pointer, encoder, and keypad inputs."""
    class VirtualDevice:
        type: int
        user_data: Any
        points: tuple[tuple[int, int, int], ...]
        def __init__(self, owner: VirtualDevices, device_type: int) -> None: ...
        def subscribe(self, callback: Callable[..., Any], event_types: Iterable[int] | None = None) -> None: ...
        def unsubscribe(self, callback: Callable[..., Any], event_types: Iterable[int] | None = None) -> None: ...
        @property
        def has_pending(self) -> bool: ...
        def poll(self, *args: Any) -> None: ...
        def add_event(self, event: tuple[Any, ...]) -> None: ...
    devices: list[VirtualDevices.VirtualDevice]
    def __init__(self, host_device: Any, window_id: int | None = None) -> None: ...
    def poll_host_device(self) -> None: ...

class event_loop:
    """The LVGL loop: one `multimer` timer that runs `lv.timer_handler`."""
    max_yield_ms: int
    delay: int
    refresh_cb: Callable[[], Any] | None
    exception_sink: Callable[[Exception], Any]
    passes: int
    slow_passes: int
    last_pass_ms: int
    def __init__(self, freq: int | None = None, max_scheduled: int = 2, refresh_cb: Callable[[], Any] | None = None, asynchronous: bool = False, exception_sink: Callable[[Exception], Any] | None = None, period_ms: int | None = None, max_yield_ms: int | None = None) -> None: ...
    @property
    def timer(self) -> Timer: ...
    def deinit(self) -> None: ...
    def disable(self) -> None: ...
    def enable(self) -> None: ...
    @staticmethod
    def is_running() -> bool: ...
    @staticmethod
    def current_instance() -> event_loop | None: ...
    def task_handler(self, _: Any = None) -> int | None: ...
    def tick(self) -> None: ...
    def default_exception_sink(self, e: BaseException) -> None: ...

def main() -> None:
    """Initialize LVGL, wire `DisplayDriver`, and enable the event loop."""
def attach(display: _DisplayDriver, devices: Iterable[Any] | None = None, *, color_format: int | None = None, blocking: bool = True) -> DisplayDriver:
    """Attach an additional displaydev panel as an LVGL display."""
def attach_devices(devs: Iterable[Any], lv_display: Any = None) -> list[Any]:
    """Register LVGL input devices as LVGL indevs without creating a display."""

SWIPE_PX: int
TWO_FINGER_SWIPE_PX: int

def set_wheel_mapping(adjust_axis: str | None = None, adjust_sign: int | None = None, navigate: bool | None = None, navigate_sign: int | None = None) -> None:
    """Configure how the two wheel/swipe axes map onto LVGL."""
def take_keys(callback: Callable[[Any], None]) -> bool:
    """Send the keys typed on the display itself to *callback* instead of LVGL."""
def give_back_keys(callback: Callable[[Any], None]) -> None:
    """Stop sending the display's keys to *callback* (from `take_keys`)."""
def create_devices(devs: Iterable[Any], lv_display: Any, virtual_devices: list[Any] | None = None, window_id: int | None = None) -> list[Any]:
    """Register LVGL input devices as LVGL indevs (pointer / encoder / keypad)."""

class DisplayDriver:
    """Bridge a displaydev driver to an LVGL display and input devices."""
    display_drv: _DisplayDriver
    presents: int
    lv_display: Any
    virtual_devices: list[Any]
    def __init__(self, display_drv: _DisplayDriver, devs: Iterable[Any] | None = None, color_format: Any = ..., blocking: bool = True) -> None: ...
    @property
    def frame_period_ms(self) -> int: ...
    def release_frame_clock(self) -> None: ...
