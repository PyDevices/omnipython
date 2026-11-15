# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Android media session for `audiodev.PCMOutput`."""

from typing import Literal

__all__ = ["AndroidMediaSession", "get_session"]

class AndroidMediaSession:
    """Duck-typed `audiodev.AudioSession` for Android media hardening."""

    codec: None
    duplex: bool
    def __init__(self) -> None: ...
    def get_codec(self) -> None: ...
    def acquire(self, owner: object, direction: Literal["in", "out"]) -> None: ...
    def release(self, owner: object) -> None: ...

def get_session() -> AndroidMediaSession:
    """Return the process-wide Android media session (created once)."""
