# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
from _typeshed import Incomplete

__all__ = ['AndroidMediaSession', 'get_session', '_FocusListener@69']

class AndroidMediaSession:
    codec: Incomplete
    duplex: bool
    def __init__(self) -> None: ...
    def get_codec(self): ...
    def acquire(self, owner, direction): ...
    def release(self, owner) -> None: ...

def get_session(): ...

# Names in __all__ with no definition:
#   _FocusListener@69
