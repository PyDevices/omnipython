# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""A registry of backends, so ``AutoDisplay`` and ``audiodev.auto`` can pick one you wrote."""

from collections.abc import Callable, Generator
from typing import Any

__all__ = ['Decline', 'register', 'names', 'spec', 'require', 'candidates', 'load']

class Decline(Exception):
    """Raised by a backend's factory to say "not on this machine"; the next one is tried."""

def register(kind: str, name: str, spec: str, probe: Callable[[], object] | None = None, _builtin: bool = False) -> None:
    """Make `name` a backend of `kind`; imports nothing."""

def names(kind: str) -> list[str]:
    """The registered backend names of `kind`, in registration order."""

def spec(kind: str, name: str) -> str | None:
    """The spec string `name` was registered with, or `None`."""

def require(kind: str, name: str, module: str | None = None) -> None:
    """Ask for backend `name` to be tried by ``auto``, ahead of the built-in ones."""

def candidates(kind: str, override: str | None = None) -> Generator[tuple[str, str, bool], None, None]:
    """Yield ``(name, spec, builtin)`` for each backend to try, in search order."""

def load(spec: str) -> Any:
    """Import and return what `spec` names: ``"module:Class"``, or a module."""
