# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""Play to Bluetooth headphones or a speaker, as a board's audio output.

On firmware with btclassic, register the provider, and the speakers a scan
finds are listed under ``audio.out``. Choosing one connects to it, and once
its link is up, a routed ``audio_out`` plays there (see
`audiodev.endpoints.route`)::

    import board_peripherals
    import endpointkit
    from audiodev import bt_audio, endpoints

    endpoints.route(board_peripherals)
    bt_audio.register()
    endpointkit.refresh("audio.out")    # turns the radio on and looks
    # ... endpointkit.poll() until the speaker is listed ...
    endpointkit.select("audio.out", "bt-out:a1b2c3d4e5f6")

Nothing touches the radio until something asks for a scan (a picker's Scan
button, or `endpointkit.refresh`): registering lists what's already known
and nothing more. A speaker found once is listed until the board restarts.

The board talks A2DP as a phone does, through ``btclassic.AudioSource``:
the stack codes the audio as SBC. A board runs one A2DP role at a time, so
choosing a speaker fails, with the reason on the endpoint, while the board
is itself a Bluetooth speaker (an ``AudioSink`` runs).

`SourceOutput` is the same source as an audiodev ``PCMOutput``, for a
program that writes PCM itself.
"""

import btclassic
import endpointkit
from audiodev import AudioFormat, PCMOutput, check_latency
from audiodev.sample_out import AudioOut

#: How long a scan looks for speakers, in milliseconds (1280 to 61440, in steps of 1280).
INQUIRY_MS = 10240

# The major device class of headphones, speakers and car stereos (bits 8 to 12).
_AUDIO_VIDEO = 4

_CHUNK_MS = 40
# What open_out() keeps queued for each latency profile, as usb.host.audio does.
_LOOKAHEAD_MS = {None: 80, "low": 80, "buffered": 300}


def _hex(addr):
    return "".join("%02x" % b for b in addr)


def _colons(addr):
    return ":".join("%02x" % b for b in addr)


class SourceOutput(PCMOutput):
    """A Bluetooth A2DP source as an audiodev ``PCMOutput``.

    It writes 16-bit PCM at *format*'s rate and channels, which the source
    converts to the stream's own. Volume is applied here, in software, so
    the speaker's own volume stays where it was.

    Until the speaker's stream runs, the source holds what fits in its
    buffer and plays it first when the stream starts. What doesn't fit is
    dropped and counted in ``dropped``: a speaker that isn't listening yet
    plays nothing, as a radio does.

    Args:
        source: a ``btclassic.AudioSource``, connected or connecting.
        format (AudioFormat): what will be written: 16-bit, 1 or 2
            channels, 8000 to 48000 Hz.

    Raises:
        ValueError: *format* isn't 16-bit, or has more than two channels.
    """

    def __init__(self, source, format, **kwargs):
        if format.bits != 16:
            raise ValueError("a Bluetooth speaker takes 16-bit PCM, not %d-bit" % format.bits)
        if format.channels not in (1, 2):
            raise ValueError("a Bluetooth speaker takes 1 or 2 channels, not %d" % format.channels)
        PCMOutput.__init__(self, format, **kwargs)
        self.source = source
        self.dropped = 0

    def _open(self):
        self.source.rate = self.format.rate
        self.source.channels = self.format.channels
        self.source.status = "playing"

    def _close(self):
        self.source.status = "stopped"

    def _write(self, buf):
        taken = self.source.write(buf)
        if taken == 0 and not self.source.streaming:
            self.dropped += len(buf)
            return len(buf)
        return taken

    def stats(self):
        """The source's counters (``buffered``, ``capacity``, ``underruns``
        and the rest, in frames) and ``dropped``, in bytes."""
        out = dict(self.source.stats())
        out["dropped"] = self.dropped
        return out


class BluetoothOut(endpointkit.Provider):
    """Bluetooth headphones and speakers, under ``audio.out``.

    Each endpoint's id is ``bt-out:`` and the speaker's address in hex. It
    is connected while its link is up. Every endpoint takes the resource
    ``"bt.a2dp"``: one speaker plays at a time.

    Args:
        module: what stands for ``btclassic``; btclassic itself when None.
        inquiry_ms (int): how long a scan looks.
    """

    def __init__(self, module=None, inquiry_ms=INQUIRY_MS):
        endpointkit.Provider.__init__(self, "audio.out", "bt-out", ("bt.a2dp",))
        self.bc = module or btclassic
        self.inquiry_ms = inquiry_ms
        self.bt = None
        self.source = None
        self.known = []          # [address, name] of each speaker found, in the order found
        self._scans = 0
        self._looking = False
        self._seen = None

    def _radio(self):
        if self.bt is None:
            self.bt = self.bc.Bluetooth()
        if not self.bt.active():
            self.bt.active(True)
        return self.bt

    def _learn(self, addr, name):
        for row in self.known:
            if row[0] == addr:
                if name and row[1] != name:
                    row[1] = name
                return
        self.known.append([addr, name])

    def _endpoints(self):
        src = self.source
        peer = bytes(src.peer) if src is not None and src.connected and src.peer else None
        if peer is not None:
            self._learn(peer, src.peer_name)
        found = []
        for addr, name in self.known:
            state = endpointkit.CONNECTED if peer == addr else endpointkit.AVAILABLE
            found.append(self.endpoint(_hex(addr), name or "Bluetooth audio " + _colons(addr), state,
                                       caps={"address": _colons(addr)}))
        self._seen = [(ep.id, ep.label, ep.state) for ep in found]
        return found

    def scan(self):
        # The first scan is the one register() makes: it lists what's known
        # and leaves the radio as it is. Every later one looks.
        self._scans += 1
        if self._scans > 1:
            self._radio().inquiry(self.inquiry_ms)
            self._looking = True
        return self._endpoints()

    def poll(self):
        if self._looking:
            for addr, name, cod, _rssi in self.bt.found():
                if (cod >> 8) & 0x1F == _AUDIO_VIDEO:
                    self._learn(bytes(addr), name)
            self._looking = self.bt.inquiring()
        before = self._seen
        found = self._endpoints()
        return found if self._seen != before else None

    def apply(self, endpoint, chosen):
        if chosen:
            if self.source is None:
                self.source = self.bc.AudioSource(self._radio())
            self.source.connect(bytes.fromhex(endpoint.local_id))
            return
        if self.source is not None:
            self.source.deinit()
            self.source = None
        endpoint.state = endpointkit.AVAILABLE

    def open_out(self, endpoint, format=None, *, latency=None, **kwargs):
        """The chosen speaker as an ``audiodev.AudioOut``, the player a
        board's ``audio_out`` returns.

        *format* defaults to 44.1 kHz stereo, the stream's own rate. The
        graph is pulled on the interpreter thread: the audio pump has no way
        to write to the source yet. ``latency="buffered"`` keeps 300 ms
        queued, which carries a song through a garbage collection; the
        source's own buffer holds more again. ``chunk_ms``,
        ``lookahead_chunks`` and ``max_catchup_chunks`` go to ``AudioOut``.

        Raises:
            OSError: the speaker's link isn't up.
        """
        check_latency(latency)
        src = self.source
        if src is None or not src.connected or not src.peer or _hex(src.peer) != endpoint.local_id:
            raise OSError("%s isn't connected" % endpoint.label)
        chunk_ms = kwargs.pop("chunk_ms", _CHUNK_MS)
        lookahead = kwargs.pop("lookahead_chunks", max(1, -(-_LOOKAHEAD_MS[latency] // chunk_ms)))
        catchup = kwargs.pop("max_catchup_chunks", 5)
        pcm = SourceOutput(src, format or AudioFormat(44100, 2, 16), **kwargs)
        return AudioOut(pcm, pump=False, chunk_ms=chunk_ms, lookahead_chunks=lookahead,
                        max_catchup_chunks=catchup)

    def stop(self):
        if self.source is not None:
            self.source.deinit()
            self.source = None


_registered = []


def register(registry=None):
    """Register the Bluetooth speaker provider, once; returns it.

    Raises:
        OSError: this firmware's btclassic has no A2DP source.
    """
    if _registered:
        return _registered[0]
    if not hasattr(btclassic, "AudioSource"):
        raise OSError("this firmware's btclassic can't send audio (no AudioSource)")
    provider = BluetoothOut()
    (registry or endpointkit.registry).register(provider)
    _registered.append(provider)
    return provider
