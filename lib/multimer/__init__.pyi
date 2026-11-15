# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""multimer: one Timer, one clock, one dispatcher, on every PyDevices host."""

from _typeshed import SupportsWrite
from collections.abc import Callable
from types import ModuleType
from typing import Any, Literal

__all__ = ['loop_running', 'Timer', 'alive', 'defer_while', 'hold', 'info', 'keepalive', 'pump', 'run_until', 'schedule', 'sleep_ms', 'stop_all', 'timers', 'monotonic', 'run_deadline_hook', 'set_deadline_hook', 'ticks_add', 'ticks_diff', 'ticks_less', 'ticks_ms', 'ticks_us', 'every', 'after', 'asleep_ms', 'strategy', 'repl', 'report']

__version__: str

# Set on first access: the asyncio module in use (None if there is none) and
# the name of the wake source in use (None before a timer was armed).
asyncio: ModuleType | None
source: str | None

class Timer:
    """A `machine.Timer`-shaped timer delivered by the dispatcher.

    `Timer(id=-1)` then `init`, or keyword arguments straight to the
    constructor as on a board.
    """

    ONE_SHOT: int
    PERIODIC: int
    yield_cap: int
    id: int
    name: str | None
    fired: int
    missed: int
    late_max: int
    last: int | None
    error: BaseException | None
    def __init__(
        self,
        id: int = -1,
        *,
        name: str | None = None,
        mode: int = 1,
        freq: float = -1,
        period: float = -1,
        callback: Callable[[Timer], Any] | None = None,
        hard: bool = False,
    ) -> None: ...
    def __enter__(self) -> Timer: ...
    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any) -> bool: ...
    def init(
        self,
        *,
        mode: int = 1,
        freq: float = -1,
        period: float = -1,
        callback: Callable[[Timer], Any] | None = None,
        hard: bool = False,
    ) -> None:
        """Arm or re-arm. `freq` in Hz wins over `period` in ms when positive."""
    def deinit(self) -> None:
        """Stop the timer. Safe to call twice, and from inside its own callback."""
    def cancel(self) -> None: ...
    def reschedule(self, delay_ms: float) -> None:
        """Move the next delivery to `delay_ms` from now."""
    @property
    def period(self) -> int: ...
    @property
    def mode(self) -> int | None: ...
    @property
    def callback(self) -> Callable[[Timer], Any] | None: ...
    @property
    def running(self) -> bool:
        """`True` while armed (the callback may or may not be executing now)."""
    @property
    def due_in(self) -> int | None:
        """Milliseconds until the next delivery, or `None` when not armed."""

class _Hold:
    def __enter__(self) -> _Hold: ...
    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any) -> bool: ...

def loop_running() -> bool:
    """`True` when a coroutine of a running event loop is currently executing."""

def alive() -> bool:
    """`True` while the exit-hook loop should keep the process running."""

def defer_while(check: Callable[[], object] | None) -> None:
    """Put off every delivery while `check()` returns true; `None` removes the check."""

def hold() -> _Hold:
    """Context manager: no callback is delivered inside; due work runs at exit."""

def info() -> dict[str, Any]:
    """The dispatcher's state: wake source, delivery counts, held, keepalive, next deadline."""

def keepalive(flag: bool = True) -> None:
    """Keep the process alive past the script's end while timers are armed."""

def pump() -> int | None:
    """Deliver what is due now. Returns ms until the next deadline, or `None`."""

def run_until(pred: Callable[[], object], tick_ms: int = 10) -> None:
    """Block, delivering, until `pred()` is true."""

def schedule(fn: Callable[[Any], object], arg: Any) -> None:
    """Run `fn(arg)` at the next safe point (`micropython.schedule`'s shape)."""

def sleep_ms(ms: float) -> None:
    """Sleep for `ms`, delivering timers that come due on the way."""

def stop_all() -> None:
    """Stop every armed timer."""

def timers() -> tuple[Timer, ...]: ...

def monotonic() -> float:
    """Return a monotonic clock in seconds."""

def run_deadline_hook() -> Any:
    """Invoke the registered deadline hook, if any; returns its result, or `False` when none (dev use)."""

def set_deadline_hook(hook: Callable[[], Any] | None) -> None:
    """Register or clear a cooperative deadline hook (dev use only)."""

def ticks_add(ticks: int, delta: int) -> int:
    """Add a delta to a ticks value with wraparound at `2**29` ms."""

def ticks_diff(ticks1: int, ticks2: int) -> int:
    """The signed difference `ticks1 - ticks2` in milliseconds, handling wraparound."""

def ticks_less(ticks1: int, ticks2: int) -> bool:
    """Return `True` if `ticks1` is before `ticks2`."""

def ticks_ms() -> int:
    """A wrapping millisecond tick counter (period `2**29` ms)."""

def ticks_us() -> int:
    """A wrapping microsecond tick counter."""

def every(ms: float, callback: Callable[[Timer], Any], *, name: str | None = None) -> Timer:
    """A periodic `Timer` firing `callback(timer)` every `ms`."""

def after(ms: float, callback: Callable[[Timer], Any], *, name: str | None = None) -> Timer:
    """A one-shot `Timer` firing `callback(timer)` once, after `ms`."""

async def asleep_ms(ms: float) -> None:
    """Coroutine sleep for async code; delivers due timers on hosts without a wake source."""

def strategy() -> Literal['ambient', 'exit_hook', 'none'] | None:
    """How the program stays alive past the script body, or `None` before a timer was armed."""

def repl(namespace: dict[str, Any] | None = None, prompt: str = '>>> ', tick_ms: int = 10) -> None:
    """A line REPL that keeps delivering timers while it reads (hosts with no prompt)."""

def report(file: SupportsWrite[str] | None = None) -> None:
    """Print the dispatcher's state and every live timer, for a person at a prompt."""
