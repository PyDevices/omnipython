# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""A browser page's serial ports, through Web Serial, as endpointkit ``serial`` endpoints."""

from typing import Any

import endpointkit

KIND: str
ASK: str
ASK_LABEL: str
VENDORS: dict[int, str]

def label(code: int) -> str:
    """What a port is called, from its USB vendor and product IDs as one number."""

class Port:
    """One open serial port. Nothing blocks: `read` hands out what has arrived."""

    name: str
    baudrate: int
    def __init__(self, page: Any, index: int, name: str, baudrate: int) -> None: ...
    @property
    def error(self) -> str | None: ...
    def is_open(self) -> bool:
        """True once the browser has opened the port."""
    def any(self) -> int:
        """How many bytes are waiting."""
    def read(self, nbytes: int | None = None) -> bytes | None:
        """What has arrived, up to *nbytes*; None when nothing has."""
    def readinto(self, buf: bytearray | memoryview, nbytes: int | None = None) -> int | None: ...
    def write(self, buf: bytes | bytearray | memoryview) -> int | None:
        """Send *buf*; its length, or None while the port isn't open yet."""
    def close(self) -> None:
        """Close the port, so another program, or another page, can open it."""
    def deinit(self) -> None: ...
    def __enter__(self) -> Port: ...
    def __exit__(self, *exc: object) -> None: ...

class Ports(endpointkit.Provider):
    """The serial ports the person has let this page use, under ``serial``."""

    page: Any
    def __init__(self, page: Any = None) -> None: ...
    def open(self, endpoint: endpointkit.Endpoint, baudrate: int = 115200) -> Port:
        """Open the port behind *endpoint* at *baudrate*."""

def register(registry: endpointkit.Registry | None = None, page: Any = None) -> Ports:
    """Add the ``serial`` kind if it's new, and register the page's ports."""

def open(endpoint: endpointkit.Endpoint, baudrate: int = 115200) -> Port:
    """Open a chosen ``serial`` endpoint of this page's, at *baudrate*."""
