# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""MIDI ports on Linux, over ALSA's raw MIDI devices."""

from . import PortIn, PortInfo, PortOut, WholeMessages

PROC_ASOUND: str
DEV_SND: str
BAUDRATE: int

def available(proc: str = "/proc/asound") -> tuple[PortInfo, ...]:
    """Every raw MIDI port the kernel offers."""

def find(name: str, direction: str | None = None, proc: str = "/proc/asound") -> tuple[PortInfo, ...]:
    """Ports whose name contains ``name``, case-insensitively."""

def ports(
    name: str = "", proc: str = "/proc/asound", dev: str = "/dev/snd"
) -> tuple[WholeMessages | None, LinuxMidiOut | None]:
    """``(midi_in, midi_out)`` for the first ports matching ``name``; ``None`` for a direction with no port."""

def serial_ports(path: str, baudrate: int = 31250) -> tuple[WholeMessages, LinuxMidiOut]:
    """``(midi_in, midi_out)`` over a serial port wired to MIDI jacks."""

def open_port(port: PortInfo | str, dev: str = "/dev/snd") -> LinuxMidiIn | LinuxMidiOut:
    """Open one port, given a ``PortInfo`` or an id string."""

class LinuxMidiIn(PortIn):
    def __init__(self, info: PortInfo, path: str, flags: int = 0) -> None: ...

class LinuxMidiOut(PortOut):
    def __init__(self, info: PortInfo, path: str, flags: int = 0) -> None: ...
