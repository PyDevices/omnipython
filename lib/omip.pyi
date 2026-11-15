# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Install an OmniPython package with one line, and everything it needs."""

INDEX: str
ADAFRUIT: str
UPSTREAM: str
TIMEOUT: int

def connect(prompt: bool = True, timeout: int = 30) -> bool:
    """Get the board online, if it isn't already. Returns whether it is online."""

def search(*words: str, index: str | None = None, prompt: bool = True) -> None:
    """Print the packages whose name or description has every one of the words."""

def install(
    package: str,
    index: str | None = None,
    target: str | None = None,
    version: str | None = None,
    mpy: bool = True,
    prompt: bool = True,
    force: bool = False,
    url_base: str | None = None,
) -> bool:
    """Install a package and everything it needs. Returns `True` once every file has landed."""
