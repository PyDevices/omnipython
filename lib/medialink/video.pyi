# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Pictures over a `Link`: a camera on one side, a screen on the other."""

from typing import Protocol

from medialink.link import Frame, Link

JPEG: int

class _Display(Protocol):
    """A displaydev driver: a pixel surface with a size."""

    @property
    def width(self) -> int: ...
    @property
    def height(self) -> int: ...
    def fill_rect(self, x: int, y: int, w: int, h: int, color: int) -> object: ...
    def blit_rect(self, buf: bytearray | memoryview, x: int, y: int, w: int, h: int) -> object: ...

class Video:
    """Send and receive pictures over `link`."""

    link: Link
    burst: int
    stats: dict[str, int | None]
    def __init__(self, link: Link, *, bandwidth: int | None = None, burst: int = 4) -> None: ...
    @property
    def ready(self) -> bool:
        """True when the last picture has gone, so a new one can be taken."""
    def send(self, jpeg: bytes | bytearray | memoryview, stamp: int | None = None, codec: int = ...) -> bool:
        """Start sending one picture; `service()` sends the rest."""
    def service(self) -> None:
        """Send what the pace allows of the picture in flight."""
    def receive(self) -> Frame | None:
        """The newest whole picture that has arrived, or `None`."""

class Screen:
    """Show JPEG pictures on `display`, each fitted inside it and centred."""

    display: _Display
    background: int
    rect: tuple[int, int, int, int]
    errors: int
    last_error: BaseException | None
    def __init__(
        self, display: _Display, background: int = 0, rect: tuple[int, int, int, int] | None = None
    ) -> None: ...
    def show(self, jpeg: bytes | bytearray | memoryview) -> tuple[int, int] | None:
        """Decode `jpeg` and put it on the display. Returns its size there, or `None`."""

class FileCamera:
    """A camera made of the JPEG files in `folder`, in name order."""

    paths: list[str]
    def __init__(self, folder: str) -> None: ...
    def take(self) -> bytes:
        """The next file's bytes; starts over after the last."""
    def capture_jpeg(self, quality: int | None = None) -> bytes: ...
    def deinit(self) -> None: ...
