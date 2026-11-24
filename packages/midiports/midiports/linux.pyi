# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""MIDI ports on Linux, over ALSA's raw MIDI devices and sequencer ports."""

from . import PortIn, PortInfo, PortOut, WholeMessages

PROC_ASOUND: str
DEV_SND: str
BAUDRATE: int
CLIENT_NAME: str

def available(proc: str = "/proc/asound") -> tuple[PortInfo, ...]:
    """Every raw MIDI and sequencer port the kernel offers."""

def find(name: str, direction: str | None = None, proc: str = "/proc/asound") -> tuple[PortInfo, ...]:
    """Ports whose name contains ``name``, case-insensitively."""

def ports(
    name: str = "", proc: str = "/proc/asound", dev: str = "/dev/snd"
) -> tuple[WholeMessages | None, LinuxMidiOut | None]:
    """``(midi_in, midi_out)`` for the first ports matching ``name``; ``None`` for a direction with no port."""

def serial_ports(path: str, baudrate: int = 31250) -> tuple[WholeMessages, LinuxMidiOut]:
    """``(midi_in, midi_out)`` over a serial port wired to MIDI jacks."""

def open_port(
    port: PortInfo | str, dev: str = "/dev/snd"
) -> LinuxMidiIn | LinuxMidiOut | LinuxSeqIn | LinuxSeqOut:
    """Open one port, given a ``PortInfo`` or an id string."""

class LinuxMidiIn(PortIn):
    def __init__(self, info: PortInfo, path: str, flags: int = 0) -> None: ...

class LinuxMidiOut(PortOut):
    def __init__(self, info: PortInfo, path: str, flags: int = 0) -> None: ...

def encode_message(message: bytes | bytearray, source: tuple[int, int] = (0, 0), dest: tuple[int, int] = (0, 0)) -> bytes:
    """The sequencer event for one whole MIDI message, or ``b""`` for one it has no event for."""

def decode_events(data: bytes | bytearray | memoryview, out: bytearray) -> int:
    """Append the MIDI bytes of the events in ``data`` to ``out``; how many bytes of ``data`` were whole events."""

class LinuxSeqIn(PortIn):
    READ_SIZE: int
    address: tuple[int, int]
    def __init__(self, info: PortInfo, path: str, address: tuple[int, int]) -> None: ...

class LinuxSeqOut(PortOut):
    address: tuple[int, int]
    def __init__(self, info: PortInfo, path: str, address: tuple[int, int]) -> None: ...
