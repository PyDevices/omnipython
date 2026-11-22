# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""A computer's sound devices as endpointkit endpoints, for ``audio.out`` and ``audio.in``.

Register the providers, and the outputs and inputs the host's audio backend
can open appear in every picker::

    import endpointkit
    from audiodev import auto, endpoints

    endpoints.register()
    endpointkit.select("audio.out", "win_audio-out:Speakers (USB Audio)")
    out = auto.pcm_out(fmt, device=endpoints.device("audio.out"))

Each endpoint's id holds the device's name, as the backend's ``device``
argument takes it, and its ``caps`` hold ``backend`` and ``device``. The
``default`` endpoint follows whatever the operating system's default is,
and is ``device=None``. Choosing an endpoint opens nothing: the program that
plays subscribes to ``audio.out`` and opens its stream on the chosen device.

Devices plugged in later are found by `endpointkit.poll`, which lists them
again every ``rescan_ms``.
"""

import time

import endpointkit

#: How often, in milliseconds, `endpointkit.poll` lists the devices again.
RESCAN_MS = 3000

_ticks_ms = getattr(time, "ticks_ms", None)
_ticks_diff = getattr(time, "ticks_diff", None)
if _ticks_ms is None:

    def _ticks_ms():
        return int(time.monotonic() * 1000)

    def _ticks_diff(a, b):
        return a - b


def _names(backend, capture):
    """The device names *backend* can open, for playback or capture."""
    if backend == "alsa_audio":
        from audiodev import alsa_audio

        way = "capture" if capture else "playback"
        return tuple(d["name"] for d in alsa_audio.devices() if d.get(way))
    if backend == "win_audio":
        from audiodev import win_audio

        return win_audio.list_audio_devices(capture)
    if backend == "sdl2_audio":
        from audiodev import sdl2_audio

        return sdl2_audio.list_audio_devices(capture)
    return ()


class HostAudio(endpointkit.Provider):
    """The host's playback or capture devices, through one audiodev backend.

    Args:
        capture (bool): inputs when True, outputs when False.
        backend (str): the audiodev backend whose devices to list, such as
            ``"win_audio"``; the one `audiodev.auto` would pick when None.
        names (callable): ``names(backend, capture)`` returning device names,
            to stand in for the backend in a test.
        rescan_ms (int): how often `poll` lists the devices again.
    """

    def __init__(self, capture=False, backend=None, names=None, rescan_ms=RESCAN_MS):
        if backend is None:
            from audiodev import auto

            backend = auto.select_backend()
        self.backend = backend
        self.capture = capture
        self._names = names or _names
        self.rescan_ms = rescan_ms
        way = "in" if capture else "out"
        endpointkit.Provider.__init__(self, "audio." + way, "%s-%s" % (backend, way))
        self._last = _ticks_ms()
        self._seen = None

    def scan(self):
        self._last = _ticks_ms()
        found = [self.endpoint("default", "System default", caps={"backend": self.backend, "device": None})]
        try:
            names = self._names(self.backend, self.capture)
        except OSError as exc:
            print("audiodev.endpoints: %s can't list devices: %s" % (self.backend, exc))
            names = ()
        for name in names:
            found.append(self.endpoint(name, name, caps={"backend": self.backend, "device": name}))
        self._seen = [ep.id for ep in found]
        return found

    def poll(self):
        if _ticks_diff(_ticks_ms(), self._last) < self.rescan_ms:
            return None
        before = self._seen
        found = self.scan()
        return found if [ep.id for ep in found] != before else None


_providers = []


def register(registry=None, backend=None):
    """Register the host's outputs and inputs; returns ``(outputs, inputs)``.

    Registering again returns the providers already registered.
    """
    if not _providers:
        registry = registry or endpointkit.registry
        _providers.append(registry.register(HostAudio(False, backend)))
        _providers.append(registry.register(HostAudio(True, backend)))
    return _providers[0], _providers[1]


def device(kind="audio.out", registry=None):
    """The device name to open for *kind*'s first chosen endpoint.

    None means the system default: nothing is chosen, the choice isn't found
    yet, or the ``default`` endpoint is chosen.
    """
    chosen = (registry or endpointkit.registry).selected(kind)
    return chosen[0].caps.get("device") if chosen else None


def devices(kind="audio.out", registry=None):
    """The device names of every chosen, found endpoint of *kind*, for a
    program that plays to several at once."""
    return [ep.caps.get("device") for ep in (registry or endpointkit.registry).selected(kind)]
