# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Scheduled repeating tasks for `Display`."""

from collections.abc import Callable
from typing import Any

class Task:
    """A callback that runs every `delay` milliseconds."""

    callback: Callable[[], Any]
    delay: int
    next_run: int
    def __init__(self, callback: Callable[[], Any], delay: int) -> None: ...
    def run(self, t: int) -> None: ...
