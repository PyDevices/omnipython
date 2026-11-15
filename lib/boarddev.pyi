# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Lazy end-device binding for board_peripherals -> board_config, host-or-board audio, portable env helpers."""

from types import ModuleType
from typing import Any, overload

def bind_lazy(ns: dict[str, Any], peripherals_mod: ModuleType) -> None:
    """Install module `__getattr__` / `__dir__` on `ns` for lazy roles."""
    ...

def replace_role(peripherals_mod: ModuleType, name: str, role: Any) -> None:
    """Put `role` in place of the board's `name` role, for every caller."""
    ...

def audio_provider() -> ModuleType:
    """Return the module supplying this machine's audio factories."""
    ...

def pcm_out(format: Any = None, **kwargs: Any) -> Any:
    """Raw PCM output from board or host, same call."""
    ...

def pcm_in(format: Any = None, **kwargs: Any) -> Any:
    """Raw PCM input from board or host, same call."""
    ...

def audio_out(format: Any = None, **kwargs: Any) -> Any:
    """Sample player, board or host."""
    ...

def env_set(name: str, value: object) -> None:
    """Set an environment variable portably (CPython, MicroPython, CircuitPython)."""
    ...

def env_bool(name: str, default: bool = False) -> bool:
    """Read a truthy/falsey environment variable with a portable fallback chain."""
    ...

def env_get(name: str, default: str | None = None) -> str | None:
    """Read a string environment variable portably (honors `env_set` overrides)."""
    ...

def env_int(name: str, default: int = 0) -> int:
    """Read an integer environment variable portably."""
    ...

def env_float(name: str, default: float = 0.0) -> float:
    """Read a floating-point environment variable portably."""
    ...

NAME_KEY: str
NAME_PREFIX: str
NAME_MAX: int

@overload
def name() -> str: ...
@overload
def name(new: str | None) -> None:
    """The board's name, or give it a new one.

    With no argument, the name: a saved one, else `omnipython-` and the last
    three bytes of the unique ID on a board, the computer's name on a desktop,
    or `omnipython-` and six random hex digits in a browser. With a string,
    save it as the new name; with None, forget a saved one.

    Raises:
        ValueError: The new name isn't one label of letters, digits and hyphens, 1 to 20 characters.
        OSError: CircuitPython can't write settings.toml while CIRCUITPY is mounted.
    """
    ...

def check_name(text: object) -> None:
    """Raise `ValueError` unless `text` can be a board's name."""
    ...
