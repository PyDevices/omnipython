# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""Give a board with no screen one in a web browser: the same config for every board.

The display is a `RemoteDisplay <displaydev.remotedisplay.RemoteDisplay>`,
480x320, served at ``http://<the board's address>/``. Apps draw on it and
read the browser's clicks and keys as they would a panel and its touch. It
names no pins, so one copy suits any board with a network and the RAM for
the frame (``width * height * 2`` bytes, 300 KB at 480x320).

Install it beside your board's own ``board_peripherals`` package, which
brings the audio, buttons, LEDs and radios. When you fit a real display
later, install that display's board config instead: it replaces this
``board_config.py``, and your apps stay as they are.

The browser asks for your WebREPL password (``webrepl_cfg.PASS``) before
it shows or takes input. Set these environment variables before the first
``import board_config`` to change the defaults:

    OMNIPYTHON_WIDTH            width in pixels, 480
    OMNIPYTHON_HEIGHT           height in pixels, 320
    OMNIPYTHON_REMOTE_PORT      the page's TCP port, 80
    OMNIPYTHON_REMOTE_PASSWORD  a password other than WebREPL's

There is no default without a password: with neither set, the import
raises, so the display is never left open to everyone on the network.

A board's buttons become ``keypad`` when its ``board_peripherals`` has a
``keypad()`` function. The board's Wi-Fi has to be up before a browser can
reach the page; the display works without it.
"""

import board_peripherals
from boarddev import env_get, env_int
from displaydev.remotedisplay import RemoteDisplay


def _password():
    password = env_get("OMNIPYTHON_REMOTE_PASSWORD")
    if password:
        return password
    try:
        import webrepl_cfg
    except ImportError:
        raise ImportError(
            "board_config: no password for the browser display; run webrepl_setup or set OMNIPYTHON_REMOTE_PASSWORD"
        ) from None
    return webrepl_cfg.PASS


display_drv = RemoteDisplay(
    env_int("OMNIPYTHON_WIDTH", 480),
    env_int("OMNIPYTHON_HEIGHT", 320),
    port=env_int("OMNIPYTHON_REMOTE_PORT", 80),
    password=_password(),
)
host_read = display_drv.get_events

# Buttons are UI, so they're built here, where a board with a panel builds
# its own; the board's package only says which pins they're on.
if hasattr(board_peripherals, "keypad"):
    keypad = board_peripherals.keypad()
    keypad_read = keypad.read

display_drv.fill(0)

from board_peripherals import PERIPHERALS, load_peripherals  # noqa: E402, F401  (re-exported for apps)

load_peripherals(globals())
