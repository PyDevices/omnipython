# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""A browser page's speakers and microphones as endpointkit endpoints.

In MicroPython's WebAssembly port, `audiodev.endpoints.register` lists the
devices the browser reports (``navigator.mediaDevices``) under ``audio.out``
and ``audio.in`` with these providers. Choosing one moves the page's sound
there: every program that plays goes to the chosen speaker, and the
microphone the runtime records from is the chosen one, without opening
anything again::

    import endpointkit
    from audiodev import endpoints

    endpoints.register()
    endpointkit.select("audio.out", "page-out:Headphones")

"System default" is always there and follows the browser's default. A
browser names its devices only once the person has let the page use the
microphone; until then they're "Speaker 1", "Microphone 1" and so on. One
that can't send a page's sound to a chosen speaker (no
``AudioContext.setSinkId``) lists the default alone for ``audio.out``.

The routing is the runtime's (``Module.omnipythonBridge.route``); a runtime
from before it lists the default alone.
"""

import endpointkit

#: The local id of the endpoint that follows the browser's default device.
DEFAULT = "default"

_DEVICES = """(kind) => {
    const media = globalThis.navigator && navigator.mediaDevices;
    const has = !!(media && media.enumerateDevices);
    let text = '', changes = 0;
    const refresh = () => media.enumerateDevices().then((found) => {
        const lines = [];
        for (const device of found) {
            // The browser's own aliases for its default: "System default" stands for them.
            if (device.kind !== kind || device.deviceId === 'default' || device.deviceId === 'communications') continue;
            lines.push(device.deviceId + '\\t' + (device.label || '').replace(/[\\t\\n]/g, ' '));
        }
        const next = lines.join('\\n');
        if (next !== text) { text = next; changes++; }
    }, () => {});
    if (has) {
        refresh();
        if (media.addEventListener) media.addEventListener('devicechange', refresh);
    }
    return {has: () => has, list: () => text, changes: () => changes, refresh};
}"""

_SINKS = """() => typeof AudioContext !== 'undefined' && 'setSinkId' in AudioContext.prototype"""

_BRIDGE = """() => { const b = globalThis.Module && globalThis.Module.omnipythonBridge; return b && b.route ? b : null; }"""


def _js():
    import js

    return js


class PageAudio(endpointkit.Provider):
    """The page's speakers (``capture`` False) or microphones (True).

    Args:
        capture (bool): microphones when True, speakers when False.
        devices (object): what lists the devices, with ``has()``, ``list()``
            (lines of "id<TAB>label") and ``changes()``; the page's own when
            None.
        bridge (object): what routes the page's sound, with ``route(way,
            device_id)`` and ``routeError(way)`` (the last routing's error,
            once, or null); the runtime's when None.
        sinks (bool): whether a speaker can be chosen; asked of the browser
            when None.
    """

    def __init__(self, capture=False, devices=None, bridge=None, sinks=None):
        way = "in" if capture else "out"
        endpointkit.Provider.__init__(self, "audio." + way, "page-" + way)
        self.way = way
        self.capture = capture
        if devices is None:
            devices = _js().eval(_DEVICES)("audioinput" if capture else "audiooutput")
        if bridge is None:
            bridge = _js().eval(_BRIDGE)()
        if sinks is None:
            sinks = capture or bool(_js().eval(_SINKS)())
        self.devices = devices
        self.bridge = bridge
        self.sinks = sinks
        self._ids = {}  # local id -> the browser's deviceId
        self.chosen = []  # local ids, in the order chosen
        self._changes = None
        self._seen = None

    def _why(self):
        """Why only the default is listed, or None when devices can be chosen."""
        if not self.devices.has():
            return "This browser lists no devices"
        if self.bridge is None:
            return "This page's runtime can't route sound"
        if not self.sinks:
            return "This browser plays to its default speaker only"
        return None

    def scan(self):
        self._changes = self.devices.changes()
        found = [self.endpoint(DEFAULT, "System default", caps={"device": None})]
        ids = {}
        if self._why() is None:
            text = str(self.devices.list())
            n = 0
            for line in text.split("\n") if text else ():
                device_id, label = line.split("\t", 1)
                n += 1
                if not label:
                    label = "%s %d" % ("Microphone" if self.capture else "Speaker", n)
                local = label
                k = 2
                while local in ids:  # two of the same device
                    local = "%s #%d" % (label, k)
                    k += 1
                ids[local] = device_id
                found.append(self.endpoint(local, local, caps={"device": device_id}))
        else:
            found[0].caps["why"] = self._why()
        self._ids = ids
        self._seen = [ep.id for ep in found]
        return found

    def poll(self):
        if self.devices.changes() == self._changes:
            error = self.bridge.routeError(self.way) if self.bridge is not None else None
            if error:
                print("audiodev.page_devices: %s" % (error,))
            return None
        before = self._seen
        found = self.scan()
        return found if self._seen != before else None

    def apply(self, endpoint, chosen):
        local = endpoint.local_id
        if chosen and local != DEFAULT and local not in self._ids:
            raise OSError(self._why() or "%s isn't listed now" % endpoint.label)
        if chosen and local not in self.chosen:
            self.chosen.append(local)
        elif not chosen and local in self.chosen:
            self.chosen.remove(local)
        endpoint.state = endpointkit.CONNECTED if chosen else endpointkit.AVAILABLE
        if self.bridge is not None:
            # A page has one speaker and one microphone at a time: the first chosen.
            first = self.chosen[0] if self.chosen else DEFAULT
            self.bridge.route(self.way, self._ids.get(first, ""))
