# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""The transport seam: how bytes reach a peer."""

import types
from typing import Any

from typing_extensions import Self

class Transport:
    """Open, send, receive, close, plus the link's MTU and bandwidth."""

    mtu: int
    bandwidth: int
    def open(self) -> Self: ...
    def close(self) -> None: ...
    def send(self, data: bytes | bytearray | memoryview, address: Any) -> None:
        """Send one datagram. `data` is reused by the link as soon as this returns."""
    def recv_into(self, buf: bytearray | memoryview) -> tuple[int, Any]:
        """Return `(count, address)`, or `(0, None)` when nothing has arrived."""
    def __enter__(self) -> Self: ...
    def __exit__(self, *exc: object) -> None: ...

class UDPTransport(Transport):
    """UDP over IP: Wi-Fi, Ethernet, or a computer's own network."""

    mtu: int
    bandwidth: int
    port: int
    def __init__(self, port: int = 0, *, interface: Any = None, power_save: bool = False) -> None: ...
    def open(self) -> Self: ...
    def close(self) -> None: ...
    def send(self, data: bytes | bytearray | memoryview, address: tuple[str, int]) -> None: ...  # type: ignore[override]
    def recv_into(self, buf: bytearray | memoryview) -> tuple[int, tuple[str, int] | None]: ...
