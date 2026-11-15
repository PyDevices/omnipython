# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Form binder: named fields, validate / values / commit (no chrome of its own)."""

from typing import Any, Callable, Protocol, TypeVar

class _HasValue(Protocol):
    @property
    def value(self) -> Any: ...

class _HasStrValue(Protocol):
    @property
    def value(self) -> Any: ...
    @value.setter
    def value(self, value: str) -> None: ...

_W = TypeVar("_W", bound=_HasValue)

class Form:
    """Register named field widgets and collect/validate their values."""

    on_commit: Callable[[dict[str, Any]], None] | None
    error_label: _HasStrValue | None
    def __init__(
        self,
        on_commit: Callable[[dict[str, Any]], None] | None = None,
        error_label: _HasStrValue | None = None,
    ) -> None:
        """Create a form binder."""
    def add(self, name: str, widget: _W, validator: Callable[[Any], str | None] | None = None) -> _W:
        """Bind `widget` under `name`; optional `validator(value)` returns an error string or `None`."""
    def get(self, name: str) -> _HasValue | None:
        """Return the widget registered as `name`, or `None`."""
    def values(self) -> dict[str, Any]:
        """Return `{name: widget.value}` for all registered fields."""
    def validate(self) -> dict[str, str]:
        """Run validators; return `{name: error}` (empty if ok)."""
    def commit(self) -> bool:
        """Validate then invoke `on_commit(values)` when valid; return `True` if it passed."""
