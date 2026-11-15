# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
from _typeshed import Incomplete

INDEX: str
ADAFRUIT: str
UPSTREAM: str
TIMEOUT: int

class _Plan:
    channel: Incomplete
    target: Incomplete
    libs: Incomplete
    force: Incomplete
    url_base: Incomplete
    seen: Incomplete
    roots: Incomplete
    files: Incomplete
    def __init__(self, channel, target, force, url_base=None) -> None: ...
    def folder(self, root): ...

def connect(prompt: bool = True, timeout: int = 30): ...
def search(*words, index=None, prompt: bool = True) -> None: ...
def install(package, index=None, target=None, version=None, mpy: bool = True, prompt: bool = True, force: bool = False, url_base=None): ...
