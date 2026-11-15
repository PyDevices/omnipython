# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""App: devices, events, display refresh and lifecycle, on multimer's timers."""

import types
from collections.abc import Callable, Coroutine, Iterable, Sequence
from typing import Any, TypeVar, overload

from multimer import Timer

from .devices import (
    ENCODER as ENCODER,
    HOST as HOST,
    JOYSTICK as JOYSTICK,
    KEYPAD as KEYPAD,
    POINTER as POINTER,
    Device,
    Encoder as Encoder,
    HostEvents as HostEvents,
    Joystick as Joystick,
    Keypad as Keypad,
    Touch as Touch,
    _Event,
    _JoystickDriver,
    _TouchDisplay,
    _TouchSample,
)

_CB = TypeVar('_CB', bound=Callable[..., Any])
_Q = TypeVar('_Q', bound=Callable[[], Any])

DEFAULT_REFRESH_MS: int
SERVICE_TICK_MS: int

class _RefreshClaim:
    def __init__(self, app: App) -> None: ...
    def release(self) -> None: ...

class _PollingClaim:
    def __init__(self, app: App) -> None: ...
    def release(self) -> None: ...

class _RefreshPaused:
    def __init__(self, app: App) -> None: ...
    def __enter__(self) -> _RefreshClaim: ...
    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: types.TracebackType | None) -> bool: ...

class App:
    """Application coordinator: devices, event dispatch, display refresh, lifecycle."""

    events: types.ModuleType
    keys: types.ModuleType
    HOST: int
    POINTER: int
    ENCODER: int
    KEYPAD: int
    JOYSTICK: int
    @classmethod
    def current(cls) -> App | None:
        """Return the currently active App instance, or `None`."""
    devices: list[Device]
    host_dev: HostEvents | None
    touch_dev: Touch | None
    keypad_dev: Keypad | None
    encoder_dev: Encoder | None
    joystick_dev: Joystick | None
    # board_config is a module or object whose attributes (display_drv, host_read,
    # touch_read, keypad_read, encoder_read, joystick_driver, ...) are all optional;
    # displays are duck-typed drivers (show, quit, needs_refresh and the like).
    def __init__(
        self,
        board_config: Any = None,
        *,
        displays: Iterable[Any] | None = None,
        host_read: Callable[[], Iterable[_Event] | None] | None = None,
        touch_read: Callable[[], _TouchSample] | None = None,
        touch_rotation_table: Sequence[int] | None = None,
        refresh_period: int | None = None,
    ) -> None: ...
    @property
    def strategy(self) -> str | None:
        """How the program stays alive past the script body (see `multimer.strategy`)."""
    @property
    def displays(self) -> tuple[Any, ...]: ...
    @property
    def primary(self) -> Any:
        """The first display, or `None` when there is none."""
    @property
    def quit_requested(self) -> bool: ...
    @property
    def before_quit(self) -> Callable[[], Any] | None: ...
    @before_quit.setter
    def before_quit(self, value: Callable[[], Any] | None) -> None: ...
    def on_quit(self, callback: _Q) -> _Q:
        """Call `callback()` at quit, after `before_quit`, in the order added. Returns `callback`."""
    @property
    def timers(self) -> tuple[Timer, ...]:
        """The App's own timers: service, refresh and `every` subscriptions."""
    def add_display(self, drv: Any) -> Any: ...
    def remove_display(self, drv: Any) -> None: ...
    def add_touch(self, read: Callable[[], _TouchSample], *, display: _TouchDisplay | None = None, rotation_table: Sequence[int] | None = None) -> Touch: ...
    def add_keypad(self, read: Callable[[], Iterable[int] | None]) -> Keypad: ...
    def add_encoder(self, read: Callable[[], int | None], *, button_read: Callable[[], object] | None = None, button: int = 2) -> Encoder: ...
    def add_joystick(self, joystick_driver: _JoystickDriver, *, emulate_digital: Sequence[tuple[int, int]] | None = None, digital_threshold: float = 0.5) -> Joystick: ...
    def register(self, dev: Device) -> None: ...
    def unregister(self, dev: Device) -> None: ...
    @overload
    def on(self, event_type_or_list: int | list[int] | tuple[int, ...] | set[int], callback: _CB) -> _CB: ...
    @overload
    def on(self, event_type_or_list: int | list[int] | tuple[int, ...] | set[int], callback: None = None) -> Callable[[_CB], _CB]: ...
    def off(self, event_type_or_list: int | list[int] | tuple[int, ...] | set[int], callback: Callable[..., Any]) -> None:
        """Unsubscribe callback from one or more event types."""
    @overload
    def every(self, ms: float, callback: Callable[[Timer], Any], *, period: None = None, name: str | None = None) -> Timer: ...
    @overload
    def every(self, ms: None, callback: Callable[[Timer], Any], *, period: float, name: str | None = None) -> Timer: ...
    @overload
    def every(self, ms: Callable[[Timer], Any], callback: None = None, *, period: float | None = None, name: str | None = None) -> Timer: ...
    @overload
    def every(self, ms: float | None = None, callback: None = None, *, period: float | None = None, name: str | None = None) -> Callable[[Callable[[Timer], Any]], Timer]: ...
    def on_tick(self, callback: Callable[[Timer], Any], period: float = 10, **_ignored: Any) -> Timer:
        """Schedule a periodic callback (alias of `every`)."""
    def stop_timers(self) -> None:
        """Stop the service tick, every refresh and every subscription."""
    stop_timer = stop_timers
    def pause_refresh(self) -> _RefreshClaim:
        """Pause display refresh while a GUI renders frames; `release()` the claim to resume."""
    def resume_refresh(self) -> None:
        """Resume display refresh after pausing."""
    def refresh_paused(self) -> _RefreshPaused:
        """Context manager to pause display refresh within a block."""
    def pause_polling(self) -> _PollingClaim:
        """Stop the service tick reading the devices: the caller reads them. `release()` the claim to resume."""
    def resume_polling(self) -> None: ...
    def poll(self) -> list[_Event]:
        """Poll registered devices and dispatch any pending events."""
    def run(self, tick_ms: int = 10) -> None:
        """Block until quit, delivering timers and events. Optional."""
    def run_async(self, coro_or_fn: Coroutine[Any, Any, Any] | Callable[[], Coroutine[Any, Any, Any]]) -> Any:
        """Run a coroutine (or a factory of one) under the host's asyncio loop; returns the task or its result."""
    def request_quit(self, code: int | None = None) -> None:
        """Request a clean application shutdown."""
