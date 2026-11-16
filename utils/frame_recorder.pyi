# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Optional desktop-display video recording support."""

def ffmpeg_executable() -> str | None:
    """Return a system or `imageio-ffmpeg` executable, or `None`."""

class FFmpegFrameRecorder:
    """Pipe fixed-size RGB24 frames to ffmpeg as an MP4."""

    path: str
    width: int
    height: int
    fps: int | float
    def __init__(self, path: str, width: int, height: int, fps: int | float = 12) -> None: ...
    def write(self, rgb_bytes: bytes | bytearray | memoryview) -> bool:
        """Send one frame; `False` when it was dropped to hold `fps` or the recorder is closed."""
    def close(self) -> int:
        """Finish the file and return the number of frames written."""
