# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""A browser page's speakers and microphones as endpointkit endpoints."""

from typing import Any

import endpointkit

DEFAULT: str

class PageAudio(endpointkit.Provider):
    """The page's speakers (``capture`` False) or microphones (True)."""

    way: str
    capture: bool
    devices: Any
    bridge: Any
    sinks: bool
    chosen: list[str]
    def __init__(self, capture: bool = False, devices: Any = None, bridge: Any = None, sinks: bool | None = None) -> None: ...
    def scan(self) -> list[endpointkit.Endpoint]: ...
    def poll(self) -> list[endpointkit.Endpoint] | None: ...
    def apply(self, endpoint: endpointkit.Endpoint, chosen: bool) -> None: ...
