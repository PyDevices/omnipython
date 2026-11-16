# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""Make sure the MIDI loopback port exists, so MIDI needs no hardware.

Run it with desktop Python::

    python -m midiports.loopback            # create the port if it's missing
    python -m midiports.loopback --check    # only report; exit 1 if missing

On Windows the port is a Windows MIDI Services basic loopback named
`midiports.LOOPBACK`. A program writes notes to its output and another reads
them from its input. The command asks ``midi.exe`` (installed with Windows
MIDI Services) whether the port exists and creates it when it doesn't. It
exits 0 when the port is there, 1 when ``--check`` finds it missing, and 2
when it can't tell: ``midi.exe`` isn't installed, or this isn't Windows.

Windows saves the port to its configuration so it survives a restart. When
it prints "Saved to Config: No" there is no configuration yet: the port lasts
until the MIDI service restarts or the PC reboots, and the command says how to
make one (run Windows MIDI Services' settings app once as administrator).

Linux and macOS have their own loopbacks, and the command names them instead
of pretending to make one.
"""

import argparse
import os
import re
import subprocess
import sys

from . import LOOPBACK

EXIT_PRESENT = 0
EXIT_MISSING = 1
EXIT_CANNOT_TELL = 2

NOT_SAVED_HINT = (
    "Windows didn't save it because it has no MIDI configuration yet, so it lasts until the MIDI service "
    "restarts or Windows reboots. Run midisettings.exe once as administrator and finish its first-run "
    "setup, then run python -m midiports.loopback again."
)

NOT_WINDOWS = {
    "linux": (
        "{name} is a Windows port. On Linux, load the kernel's virtual MIDI cards "
        "with `sudo modprobe snd-virmidi`, or use ALSA's \"Midi Through\" port, "
        "and open it with midiports.linux.ports(\"Midi Through\")."
    ),
    "darwin": (
        "{name} is a Windows port. On macOS, turn on the IAC Driver bus in "
        "Audio MIDI Setup (Window > Show MIDI Studio > IAC Driver > Device is online)."
    ),
}


class LoopbackError(Exception):
    """The loopback can't be checked or made, and why."""


def midi_exe(program_files=None):
    """Where Windows MIDI Services puts ``midi.exe``.

    Args:
        program_files: the Program Files folder; Windows' own setting by default.

    Raises:
        LoopbackError: ``midi.exe`` isn't installed there.
    """
    base = program_files if program_files is not None else os.environ["ProgramFiles"]
    path = os.path.join(base, "Windows MIDI Services", "Tools", "midi.exe")
    if not os.path.isfile(path):
        raise LoopbackError(
            "midi.exe isn't at {}. Install Windows MIDI Services from https://aka.ms/midi "
            "(Windows 11), then run this again.".format(path)
        )
    return path


def _run(exe, *args):
    # Start in midi.exe's own folder: a console started from a network share
    # as the working directory can't launch it.
    done = subprocess.run(
        [exe, *args], cwd=os.path.dirname(exe), capture_output=True, check=False,
    )
    text = done.stdout.decode("utf-8", errors="replace")
    if done.returncode != 0:
        raise LoopbackError(
            "midi.exe {} failed ({}): {}".format(
                " ".join(args), done.returncode,
                (text + done.stderr.decode("utf-8", errors="replace")).strip(),
            )
        )
    return text


def listed_names(text):
    """The names in the table ``midi basic-loopback list`` prints."""
    names = []
    column = None
    for line in text.splitlines():
        if "│" not in line:
            continue
        cells = [c.strip() for c in line.strip().strip("│").split("│")]
        if column is None:
            if "Name" in cells:
                column = cells.index("Name")
            continue
        if len(cells) > column:
            names.append(cells[column])
    return names


def exists(exe, name=LOOPBACK):
    """True when a basic loopback called ``name`` exists right now."""
    return name in listed_names(_run(exe, "basic-loopback", "list"))


def create(exe, name=LOOPBACK):
    """Create the loopback, asking for it to be saved.

    Returns:
        bool: whether Windows saved it to the configuration.
    """
    text = _run(exe, "basic-loopback", "create", "--name", name, "--save-to-config")
    if not exists(exe, name):
        raise LoopbackError("midi.exe created {!r} but it isn't in its list: {}".format(name, text.strip()))
    return re.search(r"Saved to Config\s+No\b", text) is None


def run(check=False, platform=None, program_files=None, out=print):
    """Do what the command line does. Returns the exit status."""
    platform = sys.platform if platform is None else platform
    if platform != "win32":
        for key, message in NOT_WINDOWS.items():
            if platform.startswith(key):
                out(message.format(name=LOOPBACK))
                return EXIT_CANNOT_TELL
        out("{} is a Windows port; this system has no loopback command here.".format(LOOPBACK))
        return EXIT_CANNOT_TELL
    try:
        exe = midi_exe(program_files)
        if exists(exe):
            out("{}: present".format(LOOPBACK))
            return EXIT_PRESENT
        if check:
            out("{}: missing. Run python -m midiports.loopback to create it.".format(LOOPBACK))
            return EXIT_MISSING
        saved = create(exe)
    except LoopbackError as error:
        out(str(error))
        return EXIT_CANNOT_TELL
    out("{}: created".format(LOOPBACK))
    if not saved:
        out(NOT_SAVED_HINT)
    return EXIT_PRESENT


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m midiports.loopback",
        description="Make sure the MIDI loopback port {!r} exists.".format(LOOPBACK),
    )
    parser.add_argument("--check", action="store_true",
                        help="only report; exit 1 when the port is missing")
    args = parser.parse_args(argv)
    return run(check=args.check)


if __name__ == "__main__":
    sys.exit(main())
