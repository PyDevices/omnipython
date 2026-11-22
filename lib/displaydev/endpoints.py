# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""A desktop window's keyboard, mouse and gamepads as endpointkit endpoints.

Register them after the display is made, and ``keys``, ``pointer`` and
``gamepad`` list what the window takes input from::

    import endpointkit
    from displaydev import endpoints

    endpoints.register()
    print([ep.label for ep in endpointkit.endpoints("gamepad")])

The keyboard and the mouse are one endpoint each, always there. The gamepads
are the joysticks the SDL or pygame display opened when it started; both open
every joystick at start-up and see none plugged in later, so a gamepad
plugged in after the window opened appears only when the program restarts.
Choosing an endpoint changes nothing about which events arrive: a program
that reads one gamepad reads the chosen one.
"""

import sys
import time

import endpointkit

#: How often, in milliseconds, `endpointkit.poll` lists the gamepads again.
RESCAN_MS = 3000

_ticks_ms = getattr(time, "ticks_ms", None)
_ticks_diff = getattr(time, "ticks_diff", None)
if _ticks_ms is None:

    def _ticks_ms():
        return int(time.monotonic() * 1000)

    def _ticks_diff(a, b):
        return a - b


class Fixed(endpointkit.Provider):
    """One input that is always there: the computer's keyboard or its mouse."""

    def __init__(self, kind, name, local_id, label):
        endpointkit.Provider.__init__(self, kind, name)
        self._local = local_id
        self._label = label

    def scan(self):
        return [self.endpoint(self._local, self._label, endpointkit.CONNECTED)]


def joystick_names():
    """The names of the joysticks the running display opened, in its order."""
    pg = sys.modules.get("displaydev.pgdisplay")
    if pg is not None:
        out = []
        for js in getattr(pg, "_joysticks", ()):
            try:
                out.append(js.get_name())
            except Exception:  # noqa: BLE001 - a pad unplugged under pygame raises its own error
                pass
        return out
    sdl = sys.modules.get("displaydev.sdldisplay")
    if sdl is not None:
        handles = getattr(sdl, "_joysticks", {})
        try:
            import usdl2
        except ImportError:
            return ["Gamepad %d" % (i + 1) for i in range(len(handles))]
        name_of = getattr(usdl2, "SDL_JoystickName", None)
        out = []
        for i, key in enumerate(sorted(handles)):
            out.append((name_of(handles[key]) if name_of else None) or "Gamepad %d" % (i + 1))
        return out
    return []


class Gamepads(endpointkit.Provider):
    """The gamepads the display opened.

    Args:
        names (callable): returns the gamepads' names, to stand in for the
            display in a test; `joystick_names` when None.
        rescan_ms (int): how often `poll` lists them again.
    """

    kind = "gamepad"
    name = "host-gamepad"

    def __init__(self, names=None, rescan_ms=RESCAN_MS):
        endpointkit.Provider.__init__(self)
        self._names = names or joystick_names
        self.rescan_ms = rescan_ms
        self._last = _ticks_ms()
        self._seen = None

    def scan(self):
        self._last = _ticks_ms()
        found = []
        used = []
        for name in self._names():
            local = name
            n = 2
            while local in used:
                local = "%s #%d" % (name, n)
                n += 1
            used.append(local)
            found.append(self.endpoint(local, local, endpointkit.CONNECTED))
        self._seen = used
        return found

    def poll(self):
        if _ticks_diff(_ticks_ms(), self._last) < self.rescan_ms:
            return None
        before = self._seen
        found = self.scan()
        return found if self._seen != before else None


_providers = []


def register(registry=None):
    """Register the keyboard, the mouse and the gamepads; returns them as a list.

    Registering again returns the providers already registered.
    """
    if not _providers:
        registry = registry or endpointkit.registry
        _providers.append(registry.register(Fixed("keys", "host-keys", "keyboard", "Computer keyboard")))
        _providers.append(registry.register(Fixed("pointer", "host-pointer", "mouse", "Mouse or touchpad")))
        _providers.append(registry.register(Gamepads()))
    return list(_providers)
