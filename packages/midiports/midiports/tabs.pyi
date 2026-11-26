# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""MIDI between the tabs of one browser, as ports, over a BroadcastChannel."""

from typing import Callable

from . import PortIn, PortInfo, PortOut

CHANNEL: str
HERE_MS: int
GONE_MS: int
name_of: Callable[[], str] | None

def set_name(text: str) -> None:
    """What the other tabs call this one, without the "Tab: " in front."""

def changes() -> int:
    """A count that moves whenever a tab comes, goes or changes its name."""

def available() -> tuple[PortInfo, ...]:
    """Every other tab, both directions, named "Tab: " and what it calls itself."""

def open_port(info: PortInfo) -> PortIn | PortOut:
    """Open one of `available`'s ports: an input hears that tab, an output sends to it."""

def page_in() -> PortIn:
    """An input hearing every tab that sends this one anything. Never blocks."""
