# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
from _typeshed import Incomplete

class PCM16:
    id: int
    name: str
    bits: int
    @staticmethod
    def encode(pcm, channels: int = 1): ...
    @staticmethod
    def decode(payload, channels: int = 1): ...

class ADPCM:
    id: int
    name: str
    bits: int
    def __init__(self) -> None: ...
    def encode(self, pcm, channels: int = 1): ...
    @staticmethod
    def decode(payload, channels: int = 1): ...

CODECS: Incomplete

def by_id(codec_id): ...
def choose(bandwidth, rate, channels: int = 1): ...
