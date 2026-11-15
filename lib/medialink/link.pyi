# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
from _typeshed import Incomplete
from medialink._compat import sleep_ms as sleep_ms, ticks_add as ticks_add, ticks_diff as ticks_diff, ticks_ms as ticks_ms, token as token

IDLE: int
TALKING: int
LISTENING: int
FLOOR_NAMES: Incomplete

class PeerUnreachable(OSError): ...

class Frame:
    kind: Incomplete
    codec: Incomplete
    seq: Incomplete
    stamp: Incomplete
    flags: Incomplete
    payload: Incomplete
    age: Incomplete
    arrived: Incomplete
    def __init__(self, kind, codec, seq, stamp, flags, payload, age, arrived=None) -> None: ...

class _Reassembly:
    seq: int
    seen: Incomplete
    buf: Incomplete
    room: int
    tail: Incomplete
    have: int
    def __init__(self) -> None: ...

class Link:
    transport: Incomplete
    retries: Incomplete
    ack_timeout_ms: Incomplete
    keepalive_ms: Incomplete
    dead_ms: Incomplete
    floor_timeout_ms: Incomplete
    token: Incomplete
    peer: Incomplete
    peer_token: Incomplete
    floor: Incomplete
    rtt_ms: Incomplete
    best_rtt_ms: Incomplete
    stats: Incomplete
    def __init__(self, transport, peer=None, *, retries: int = 0, ack_timeout_ms: int = 300, keepalive_ms: int = 1000, dead_ms: int = 3000, floor_timeout_ms: int = 1500, inbox: int = 32, video_inbox: int = 2) -> None: ...
    @property
    def alive(self): ...
    def connect(self, address, retries=None): ...
    def close(self) -> None: ...
    def request_floor(self, retries=None): ...
    def release_floor(self) -> None: ...
    def send_event(self, data, retries=None) -> None: ...
    def events(self): ...
    def send_audio(self, payload, codec: int = 0, flags: int = 0, stamp=None): ...
    def send_video(self, payload, codec: int = 0, flags: int = 0, stamp=None): ...
    @property
    def room(self): ...
    def frames(self, kind=None): ...
    def poll(self) -> None: ...
    @property
    def offset_ms(self): ...
