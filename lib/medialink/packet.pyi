# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
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

def pack_into(buf, kind, sub, flags, frag, frags, seq, stamp) -> None: ...
def pack(kind, sub, flags, frag, frags, seq, stamp, payload: bytes = b''): ...
def unpack(buf, count): ...
