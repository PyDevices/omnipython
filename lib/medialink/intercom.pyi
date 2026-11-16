# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Half-duplex voice over a `Link`: press to talk."""

from audiodev import PCMInput, PCMOutput
from medialink.codec import _Codec
from medialink.link import IDLE as IDLE, LISTENING as LISTENING, Link, PeerUnreachable as PeerUnreachable, TALKING as TALKING
from medialink.voice import _VoiceGate

class Intercom:
    """Joins a microphone and a speaker to a link."""

    link: Link
    mic: PCMInput | None
    speaker: PCMOutput | None
    rate: int
    channels: int
    frame_bytes: int
    frame_ms: int
    codec: _Codec
    prebuffer: int
    target_ms: int
    catch_up_ms: int | None
    voice: _VoiceGate | None
    stats: dict[str, int | None]
    def __init__(
        self,
        link: Link,
        mic: PCMInput | None,
        speaker: PCMOutput | None,
        *,
        frame_ms: int = 20,
        codec: _Codec | None = None,
        prebuffer: int = 5,
        voice: _VoiceGate | None = None,
        preroll_ms: int = 120,
        target_ms: int | None = None,
        catch_up_ms: int | None = 2000,
        settle_ms: int = 60,
    ) -> None: ...
    @property
    def talking(self) -> bool: ...
    def press(self) -> bool:
        """Take the floor and start sending. `False` when the peer is talking."""
    def release(self) -> None:
        """Send what is left, mark the end of the spurt, and let go."""
    def service(self) -> None:
        """Move one step: capture and send while talking, play while not."""
    def play(self, pcm: bytes | bytearray | memoryview) -> None:
        """Play a sound of this side's own at the intercom's format."""
    def close(self) -> None: ...
