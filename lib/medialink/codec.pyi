# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Audio codecs, and choosing one to fit a link."""

from typing import Protocol

class _Codec(Protocol):
    """A codec turns a frame of signed 16-bit little-endian PCM into a payload and back."""

    id: int
    name: str
    bits: int
    def encode(self, pcm: bytes | bytearray | memoryview, channels: int = 1) -> bytes | bytearray | memoryview: ...
    def decode(self, payload: bytes | bytearray | memoryview, channels: int = 1) -> bytes | bytearray | memoryview: ...

class _PCM16:
    """The samples as they are."""

    id: int
    name: str
    bits: int
    @staticmethod
    def encode(pcm: bytes | bytearray | memoryview, channels: int = 1) -> bytes | bytearray | memoryview: ...
    @staticmethod
    def decode(payload: bytes | bytearray | memoryview, channels: int = 1) -> bytes | bytearray | memoryview: ...

class _ADPCM:
    """IMA ADPCM, four bits a sample, mono only. Use one encoder a stream."""

    id: int
    name: str
    bits: int
    def __init__(self) -> None: ...
    def encode(self, pcm: bytes | bytearray | memoryview, channels: int = 1) -> bytes: ...
    @staticmethod
    def decode(payload: bytes | bytearray | memoryview, channels: int = 1) -> bytes: ...

PCM16: _PCM16
ADPCM: _ADPCM
CODECS: dict[int, _Codec]

def by_id(codec_id: int) -> _Codec:
    """The codec with this id. Raises `ValueError` for an unknown one."""

def choose(bandwidth: int, rate: int, channels: int = 1) -> _Codec:
    """The codec for a link of `bandwidth` bits a second."""
