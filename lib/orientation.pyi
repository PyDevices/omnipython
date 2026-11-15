# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
from _typeshed import Incomplete

def sector(x, y, z, *, upright: float = 0.9): ...

class Orientation:
    offset: Incomplete
    stable: Incomplete
    upright: Incomplete
    rotation: Incomplete
    def __init__(self, *, offset: int = 0, stable: int = 2, upright: float = 0.9, rotation: int = 0) -> None: ...
    def update(self, x, y, z): ...
