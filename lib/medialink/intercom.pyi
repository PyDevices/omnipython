# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
from _typeshed import Incomplete
from medialink._compat import sleep_ms as sleep_ms, ticks_add as ticks_add, ticks_diff as ticks_diff, ticks_ms as ticks_ms
from medialink.link import IDLE as IDLE, LISTENING as LISTENING, PeerUnreachable as PeerUnreachable, TALKING as TALKING

class Intercom:
    link: Incomplete
    mic: Incomplete
    speaker: Incomplete
    rate: Incomplete
    channels: Incomplete
    frame_bytes: Incomplete
    frame_ms: Incomplete
    codec: Incomplete
    prebuffer: Incomplete
    target_ms: Incomplete
    catch_up_ms: Incomplete
    voice: Incomplete
    stats: Incomplete
    def __init__(self, link, mic, speaker, *, frame_ms: int = 20, codec=None, prebuffer: int = 5, voice=None, preroll_ms: int = 120, target_ms=None, catch_up_ms: int = 2000, settle_ms: int = 60) -> None: ...
    @property
    def talking(self): ...
    def press(self): ...
    def release(self) -> None: ...
    def service(self) -> None: ...
    def play(self, pcm) -> None: ...
    def close(self) -> None: ...
