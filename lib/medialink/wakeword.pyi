# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
from _typeshed import Incomplete
from medialink.voice import VoiceActivity as VoiceActivity

class MicroWakeWord:
    name: Incomplete
    model: Incomplete
    frontend: Incomplete
    cutoff: Incomplete
    window: Incomplete
    stride: Incomplete
    warm_up: Incomplete
    def __init__(self, manifest, *, warm_up: int = 100, model=None, frontend=None) -> None: ...
    def reset(self) -> None: ...
    @property
    def probability(self): ...
    def feed(self, pcm, rate, channels): ...

class WakeWord:
    spotter: Incomplete
    voice: Incomplete
    rate: Incomplete
    channels: Incomplete
    listen_ms: Incomplete
    detector: Incomplete
    heard: int
    def __init__(self, manifest=None, rate: int = 16000, channels: int = 1, *, voice=None, listen_ms: int = 2000, spotter=None) -> None: ...
    @property
    def level(self): ...
    @property
    def speaking(self): ...
    def feed(self, pcm): ...
    def reset(self) -> None: ...
