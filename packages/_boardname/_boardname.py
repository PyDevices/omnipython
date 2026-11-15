# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""The board's name, ``boarddev.name()``, for a package that names something
after the board, with one plain error where the board's boarddev is too old
to have it.

A firmware frozen before ``boarddev.name()`` existed runs its own boarddev
ahead of any newer one in ``/lib``. usb_hid, midiports, castdisplay and
hmilink each require this package and call `name` instead of
``boarddev.name()``, so they all say the same thing there.
"""


def name(what, package, instead):
    """``boarddev.name()``, or AttributeError when this board's boarddev
    doesn't have it.

    *what* says what is named (``"usb_hid names the USB device"``),
    *package* is the package the firmware is older than, and *instead* says
    how to give a name without the board's (``"pass name= to enable()"``).
    """
    import boarddev

    board_name = getattr(boarddev, "name", None)
    if board_name is None:
        raise AttributeError(
            "%s after the board with boarddev.name(), which this board's "
            "boarddev doesn't have: its firmware is older than %s. Update the firmware, "
            'install pydevices again with target="/" so a newer boarddev runs ahead of '
            "the frozen one, or %s." % (what, package, instead)
        )
    return board_name()
