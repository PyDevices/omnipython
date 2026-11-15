# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""A link to one peer: media frames, a reliable control channel, the floor."""

from typing import Any

from medialink.transport import Transport

IDLE: int
TALKING: int
LISTENING: int
FLOOR_NAMES: tuple[str, str, str]

class PeerUnreachable(OSError):
    """A control message went unanswered after every retry."""

class Frame:
    """One media frame as it arrived."""

    kind: int
    codec: int
    seq: int
    stamp: int
    flags: int
    payload: bytes | bytearray
    age: int | None
    arrived: int | None
    def __init__(
        self,
        kind: int,
        codec: int,
        seq: int,
        stamp: int,
        flags: int,
        payload: bytes | bytearray,
        age: int | None,
        arrived: int | None = None,
    ) -> None: ...

class Link:
    """A transport tied to one peer."""

    transport: Transport
    retries: int
    ack_timeout_ms: int
    keepalive_ms: int
    dead_ms: int
    floor_timeout_ms: int
    token: int
    peer: Any
    peer_token: int | None
    floor: int
    rtt_ms: int | None
    best_rtt_ms: int | None
    stats: dict[str, int]
    def __init__(
        self,
        transport: Transport,
        peer: Any = None,
        *,
        retries: int = 0,
        ack_timeout_ms: int = 300,
        keepalive_ms: int = 1000,
        dead_ms: int = 3000,
        floor_timeout_ms: int = 1500,
        inbox: int = 32,
        video_inbox: int = 2,
    ) -> None: ...
    @property
    def alive(self) -> bool:
        """True while the peer has been heard from within `dead_ms`."""
    def connect(self, address: Any, retries: int | None = None) -> Link:
        """Say hello to the peer at `address` and wait for its answer."""
    def close(self) -> None:
        """Say goodbye, best effort, and close the transport."""
    def request_floor(self, retries: int | None = None) -> bool:
        """Ask to talk. `True` when granted, `False` when the peer has it."""
    def release_floor(self) -> None:
        """Stop talking. The peer hears it now, or times the floor out."""
    def send_event(self, data: str | bytes | bytearray | memoryview, retries: int | None = None) -> None:
        """Hand the peer a few bytes and wait for it to acknowledge them."""
    def events(self) -> list[bytes]:
        """The events that have arrived since the last call, oldest first."""
    def send_audio(
        self, payload: bytes | bytearray | memoryview, codec: int = 0, flags: int = 0, stamp: int | None = None
    ) -> int: ...
    def send_video(
        self, payload: bytes | bytearray | memoryview, codec: int = 0, flags: int = 0, stamp: int | None = None
    ) -> int: ...
    @property
    def room(self) -> int:
        """The most bytes of a frame that one datagram carries."""
    def frames(self, kind: int | None = None) -> list[Frame]:
        """The media frames that have arrived since the last call, in order."""
    def poll(self) -> None:
        """Read whatever has arrived, answer it, and keep the link alive."""
    @property
    def offset_ms(self) -> int | None:
        """The peer's clock minus ours, in ms, once a ping has measured it."""
