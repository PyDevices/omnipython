# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Audio and video between boards, and between boards and computers."""

from medialink.codec import ADPCM as ADPCM, PCM16 as PCM16, choose as choose
from medialink.discovery import BLE as BLE, Hotspot as Hotspot, MDNS as MDNS
from medialink.intercom import Intercom as Intercom
from medialink.link import FLOOR_NAMES as FLOOR_NAMES, Frame as Frame, IDLE as IDLE, LISTENING as LISTENING, Link as Link, PeerUnreachable as PeerUnreachable, TALKING as TALKING
from medialink.transport import Transport as Transport, UDPTransport as UDPTransport
from medialink.video import FileCamera as FileCamera, JPEG as JPEG, Screen as Screen, Video as Video
from medialink.voice import VoiceActivity as VoiceActivity
from medialink.wakeword import MicroWakeWord as MicroWakeWord, WakeWord as WakeWord

__version__: str

def ticks_ms() -> int:
    """Milliseconds on a clock that wraps at 2**30, counted the same on every runtime."""
def sleep_ms(ms: int | float) -> None: ...
def ticks_add(ticks: int, delta: int) -> int: ...
def ticks_diff(end: int, start: int) -> int:
    """`end - start` in ms, right across a wrap."""

__all__ = [
    "ADPCM",
    "BLE",
    "FLOOR_NAMES",
    "FileCamera",
    "Frame",
    "Hotspot",
    "IDLE",
    "Intercom",
    "JPEG",
    "LISTENING",
    "Link",
    "MDNS",
    "MicroWakeWord",
    "PCM16",
    "PeerUnreachable",
    "Screen",
    "TALKING",
    "Transport",
    "UDPTransport",
    "Video",
    "VoiceActivity",
    "WakeWord",
    "choose",
    "sleep_ms",
    "ticks_add",
    "ticks_diff",
    "ticks_ms",
]
