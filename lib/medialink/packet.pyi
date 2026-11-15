# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""The 14-byte header every medialink datagram starts with."""

MAGIC: int
VERSION: int
HEADER: str
HEADER_SIZE: int
AUDIO: int
VIDEO: int
CONTROL: int
ACK: int
PING: int
START: int
END: int
HELLO: int
BYE: int
TAKE: int
RELEASE: int
EVENT: int
PING_ASK: int
PING_ANSWER: int

def pack_into(
    buf: bytearray | memoryview, kind: int, sub: int, flags: int, frag: int, frags: int, seq: int, stamp: int
) -> None: ...
def pack(
    kind: int, sub: int, flags: int, frag: int, frags: int, seq: int, stamp: int,
    payload: bytes | bytearray | memoryview = b"",
) -> bytearray: ...
def unpack(buf: bytes | bytearray | memoryview, count: int) -> tuple[int, int, int, int, int, int, int] | None:
    """`(kind, sub, flags, frag, frags, seq, stamp)`, or `None` if not ours."""
