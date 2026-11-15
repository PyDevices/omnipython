# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Optional backend selection."""
from . import UnsupportedError as UnsupportedError, BLE
from typing import Any

BACKENDS: dict[str, tuple[str, str]]

def backend_name() -> str | None:
    """The backend this host would get, or `None` if it has no BLE."""
def adapter(backend: str | None = None, **kwargs: Any) -> BLE:
    """Construct the adapter for this host (or for `backend`)."""
