# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
from _typeshed import Incomplete
from medialink._compat import ticks_diff as ticks_diff, ticks_ms as ticks_ms

class VoiceActivity:
    rate: Incomplete
    channels: Incomplete
    hold_ms: Incomplete
    detector: Incomplete
    level: int
    def __init__(self, rate: int = 16000, channels: int = 1, *, hold_ms: int = 600, detector=None) -> None: ...
    @property
    def speaking(self): ...
    def feed(self, pcm): ...
    def reset(self) -> None: ...
