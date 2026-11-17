# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Make sure Windows has the MIDI loopback port, from the command line."""

from collections.abc import Callable, Sequence

EXIT_PRESENT: int
EXIT_MISSING: int
EXIT_CANNOT_TELL: int
NOT_SAVED_HINT: str
NOT_WINDOWS: dict[str, str]

class LoopbackError(Exception):
    """The loopback can't be checked or made, and why."""

def midi_exe(program_files: str | None = None) -> str:
    """Where Windows MIDI Services puts ``midi.exe``."""

def listed_names(text: str) -> list[str]:
    """The names in the table ``midi basic-loopback list`` prints."""

def exists(exe: str, name: str = "PyDevices Loopback") -> bool:
    """True when a basic loopback called ``name`` exists right now."""

def create(exe: str, name: str = "PyDevices Loopback") -> bool:
    """Create the loopback, asking for it to be saved; False when Windows couldn't save it."""

def run(
    check: bool = False,
    platform: str | None = None,
    program_files: str | None = None,
    out: Callable[[str], object] = ...,
) -> int:
    """Do what the command line does. Returns the exit status."""

def main(argv: Sequence[str] | None = None) -> int: ...
