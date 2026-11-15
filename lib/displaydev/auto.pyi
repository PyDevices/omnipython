# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
__all__ = ['host_kind', 'AutoDisplay']

def host_kind(): ...
def AutoDisplay(width: int = 320, height: int = 240, rotation: int = 0, scale: float = 1.0, title: str = 'displaydev', canvas_id=None, *, quiet: bool = False, maximized: bool = False, **kwargs): ...
