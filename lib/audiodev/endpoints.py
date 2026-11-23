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

On a board, `route` lists the board's own output and makes its
``audio_out`` play wherever ``audio.out`` is chosen::

    import board_peripherals
    import endpointkit
    from audiodev import endpoints

    endpoints.route(board_peripherals)
    endpointkit.select("audio.out", "usb-audio-out:0d8c-0014-i1")
    out = board_peripherals.audio_out(fmt)  # plays on the USB sound card

``audio_out`` opens the first chosen endpoint that is connected, through
its provider's ``open_out``; the USB host's and the Bluetooth providers
(``usb.host.endpoints`` and `audiodev.bt_audio`) have one. With none
connected, it opens the board's own output, as it did before anything was
chosen. A program that plays follows ``audio.out`` and opens ``audio_out``
again when the choice moves.
"""

import time

import boarddev
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


class BoardAudio(endpointkit.Provider):
    """A board's own audio output, the one its ``audio_out`` role opens.

    Its one endpoint, ``board-out:main``, is what the board plays on when
    nothing else is chosen. It takes the board's I2S port as a resource
    (``"i2s.0"``) when the role's capability names one.

    Args:
        factory (callable): the board's ``audio_out`` role, before `route`
            replaces it.
        label (str): what a picker shows.
    """

    def __init__(self, factory, label="Built-in audio"):
        wire = getattr(getattr(factory, "capability", None), "wire", None)
        port = getattr(wire, "port", None)
        endpointkit.Provider.__init__(self, "audio.out", "board-out", () if port is None else ("i2s.%d" % port,))
        self.factory = factory
        self.label = label
        self.chosen = False

    def scan(self):
        state = endpointkit.CONNECTED if self.chosen else endpointkit.AVAILABLE
        return [self.endpoint("main", self.label, state)]

    def apply(self, endpoint, chosen):
        self.chosen = bool(chosen)
        endpoint.state = endpointkit.CONNECTED if chosen else endpointkit.AVAILABLE

    def open_out(self, endpoint, *args, **kwargs):
        """Open the board's own output, with the arguments ``audio_out`` was given."""
        return self.factory(*args, **kwargs)


class RoutedAudioOut:
    """A board's ``audio_out`` that opens whichever ``audio.out`` endpoint is chosen.

    `route` puts one in place of the board's role. It keeps the role's
    ``capability``, so code that asks what the board's own output takes
    still hears it.

    Args:
        board (BoardAudio): the board's own output, opened when no chosen
            endpoint is connected.
        registry (endpointkit.Registry): whose choice to follow.
        capability: what the board's own role says it takes.
    """

    def __init__(self, board, registry, capability=None):
        self.board = board
        self.registry = registry
        self.capability = capability

    def __call__(self, *args, **kwargs):
        ep = playing_on(self.registry)
        if ep is None:
            return self.board.factory(*args, **kwargs)
        return ep.provider.open_out(ep, *args, **kwargs)

    def __repr__(self):
        return "RoutedAudioOut(%r)" % (self.capability,)


def playing_on(registry=None):
    """The ``audio.out`` endpoint a routed ``audio_out`` opens now, or None
    for the board's own output.

    It's the first chosen endpoint that is connected. A chosen Bluetooth
    speaker counts once its link is up, and a USB sound card from when it's
    chosen until it's pulled out.

    Raises:
        ValueError: that endpoint's provider can't be opened on a board (it
            has no ``open_out``).
    """
    for ep in (registry or endpointkit.registry).selected("audio.out"):
        if ep.state != endpointkit.CONNECTED:
            continue
        if not hasattr(ep.provider, "open_out"):
            raise ValueError("%s (%s) is chosen, but a board can't open it as its audio out" % (ep.label, ep.id))
        return ep
    return None


_routes = []  # (registry, BoardAudio)


def route(peripherals, registry=None, label="Built-in audio"):
    """List the board's own output under ``audio.out``, and make its
    ``audio_out`` play wherever ``audio.out`` is chosen.

    Call it once, before anything opens ``audio_out``; again with the same
    registry, it returns the provider it made. `boarddev.replace_role`
    puts the routed role in place, so ``board_config.audio_out`` follows
    the choice too.

    Args:
        peripherals: the board's ``board_peripherals`` module.
        registry (endpointkit.Registry): endpointkit's own when None.
        label (str): what a picker calls the board's own output.

    Returns:
        BoardAudio: the board's own output's provider.

    Raises:
        ValueError: the board has no ``audio_out``, or it isn't a factory
            role (one called with a format, listed in ``FACTORY_ROLES``).
    """
    registry = registry or endpointkit.registry
    for reg, provider in _routes:
        if reg is registry:
            return provider
    own = getattr(peripherals, "audio_out", None)
    if own is None:
        raise ValueError("this board has no audio_out to route")
    if "audio_out" not in getattr(peripherals, "FACTORY_ROLES", ()):
        raise ValueError("this board's audio_out isn't a factory role, so it can't open a chosen output")
    if isinstance(own, RoutedAudioOut):
        own = own.board.factory
    capability = getattr(own, "capability", None) or getattr(peripherals, "AUDIO_OUT", None)
    board = BoardAudio(own, label)
    registry.register(board)
    boarddev.replace_role(peripherals, "audio_out", RoutedAudioOut(board, registry, capability))
    _routes.append((registry, board))
    return board
