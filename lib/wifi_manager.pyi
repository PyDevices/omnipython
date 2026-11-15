# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Join a known Wi-Fi network, or ask for a new one on the screen."""

from typing import Any

AP_PREFIX: str
NVM_OFFSET: int
CACHE_FILE: str
JOIN_TIMEOUT_S: int
RESCAN_S: int

def connect(
    *,
    setup: bool = True,
    hostname: str | None = None,
    display_drv: Any = None,
    timeout: int = ...,
    wait: bool = True,
    ntp: bool = False,
    module: str = "secrets",
) -> str | None:
    """Join a known network, or run setup mode when none is in range.

    Args:
        setup: Start setup mode when no known network is in range. `False` returns `None` instead.
        hostname: Set before joining, so DHCP and mDNS see it.
        display_drv: Display for setup mode. Default: `board_config.display_drv` when there is one.
        timeout: Seconds to wait for each network.
        wait: `False` starts joining the first known network and returns `None` at once.
        ntp: Set the clock from NTP once a network is joined.
        module: The module holding `WIFI_SSID` and `WIFI_PASSWORD` (or `ssid` and `password`).

    Returns:
        The IPv4 address, or `None` when no network was joined (or, with `wait=False`, when one was started).
    """
    ...

def run(*, hostname: str | None = None, display_drv: Any = None, timeout: int = ...) -> str | None:
    """Start setup mode now, even when a known network is in range.

    Returns:
        The IPv4 address of the network joined, or `None` when `cancel()` ended it.
    """
    ...

def cancel() -> None:
    """End setup mode without a network."""
    ...

def networks() -> list[str]:
    """The SSIDs of the remembered networks."""
    ...

def forget(ssid: str | None = None) -> bool:
    """Forget one remembered network, or all of them when `ssid` is `None`."""
    ...
