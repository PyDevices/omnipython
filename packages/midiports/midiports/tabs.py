# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""MIDI between the tabs of one browser, as ports, over a BroadcastChannel.

Every tab of the same page that runs this finds the others: each one is an
input (what that tab sends this one) and an output (what this one sends
it). In MicroPython's WebAssembly port, list and open them as you would a
computer's ports::

    from midiports import tabs

    for info in tabs.available():
        print(info.direction, info.name)      # "out Tab: Synth Station"
    out = tabs.open_port(info)                 # an output: send to that tab
    every = tabs.page_in()                     # what any tab sends this one

A tab is named by what it tells the others (`set_name`, or ``name_of``, a
function asked each time the list is read), so a person picks "Tab: Synth
Station" rather than an id. ``midiports.endpoints.register()`` lists the
other tabs in a browser beside Web MIDI's ports, so a picker chooses them
the same way. A tab that closes says so; one that stops answering is
dropped after `GONE_MS`.

Messages go to one tab at a time, never to every tab: a controller in one
tab plays the synth in the tab it chose. The synth hears it through the
input for that tab, or through `page_in`, which hears every tab.
"""

from . import IN, OUT, PortIn, PortInfo, _count
from .webmidi import PAGE_LIMIT, _WholeOut

#: The BroadcastChannel the tabs talk on.
CHANNEL = "omnipython-midi-tabs"
#: How often a tab says it's still there, in milliseconds.
HERE_MS = 1500
#: How long a tab may be silent before it's dropped, in milliseconds.
GONE_MS = 5000

#: A function returning this tab's name for the others, asked whenever the
#: list is read; None leaves the name `set_name` gave.
name_of = None

_TABS = """(channelName, limit, hereMs, goneMs) => {
    const has = typeof BroadcastChannel !== 'undefined';
    const me = Math.random().toString(36).slice(2, 10);
    const peers = new Map();
    const inputs = new Set();
    let name = '', changes = 0, channel = null;
    const post = (message) => { if (channel !== null) channel.postMessage(message); };
    const seen = (id, peerName) => {
        const peer = peers.get(id);
        if (!peer || peer.name !== peerName) changes++;
        peers.set(id, {name: peerName, at: Date.now()});
    };
    if (has) {
        channel = new BroadcastChannel(channelName);
        // Under node, a channel left open would keep the process running.
        if (channel.unref) channel.unref();
        channel.onmessage = (event) => {
            const m = event.data;
            if (!m || m.from === me) return;
            if (m.type === 'hello' || m.type === 'here') {
                seen(m.from, String(m.name || ''));
                if (m.type === 'hello') post({type: 'here', from: me, name});
            } else if (m.type === 'bye') {
                if (peers.delete(m.from)) changes++;
            } else if (m.type === 'midi' && m.to === me) {
                for (const input of inputs) {
                    if (input.from != null && input.from !== m.from) continue;
                    if (input.bytes.length + m.data.length > limit) input.overflows++;
                    else input.bytes.push(...m.data);
                }
            }
        };
        post({type: 'hello', from: me, name});
        var timer = setInterval(() => {
            post({type: 'here', from: me, name});
            const now = Date.now();
            for (const [id, peer] of peers) {
                if (now - peer.at > goneMs) { peers.delete(id); changes++; }
            }
        }, hereMs);
        if (timer && timer.unref) timer.unref();
        if (globalThis.addEventListener) globalThis.addEventListener('pagehide', () => post({type: 'bye', from: me}));
    }
    return {
        close: () => {
            if (channel === null) return;
            post({type: 'bye', from: me});
            clearInterval(timer);
            channel.close();
            channel = null;
            peers.clear();
            changes++;
        },
        has: () => has,
        me: () => me,
        changes: () => changes,
        setName: (text) => { if (text !== name) { name = text; post({type: 'here', from: me, name}); } },
        list: () => Array.from(peers, ([id, peer]) => id + '\\t' + peer.name.replace(/[\\t\\n]/g, ' ')).join('\\n'),
        openIn: (from) => {
            const input = {from, bytes: [], overflows: 0};
            inputs.add(input);
            return {
                any: () => input.bytes.length,
                next: () => input.bytes.shift(),
                overflows: () => input.overflows,
                close: () => { inputs.delete(input); input.bytes.length = 0; },
            };
        },
        openOut: (to) => {
            const pending = [];
            return {
                put: (byte) => { pending.push(byte); },
                send: () => {
                    const data = pending.slice();
                    pending.length = 0;
                    if (!peers.has(to)) return 'that tab has closed';
                    post({type: 'midi', from: me, to, data});
                    return null;
                },
                close: () => { pending.length = 0; },
            };
        },
    };
}"""

_page = []


def _tabs():
    """This tab's place on the channel, made the first time it's needed."""
    if not _page:
        import js

        _page.append(js.eval(_TABS)(CHANNEL, PAGE_LIMIT, HERE_MS, GONE_MS))
    return _page[0]


def set_name(text):
    """What the other tabs call this one, without the "Tab: " in front."""
    _tabs().setName(str(text))


def _named():
    page = _tabs()
    if name_of is not None:
        try:
            page.setName(str(name_of()))
        except Exception:  # noqa: BLE001 - a name that can't be read keeps the last one
            pass
    return page


def changes():
    """A count that moves whenever a tab comes, goes or changes its name."""
    return _named().changes()


def available():
    """Every other tab, both directions, as ``PortInfo``: ``name`` is
    "Tab: " and what that tab calls itself."""
    text = _named().list()
    found = []
    for line in text.split("\n") if text else ():
        tab_id, name = line.split("\t", 1)
        label = "Tab: %s" % (name or tab_id)
        found.append(PortInfo(id=tab_id, name=label, direction=IN))
        found.append(PortInfo(id=tab_id, name=label, direction=OUT))
    return tuple(found)


class _TabIn(PortIn):
    """What one tab (or any tab, ``from_id`` None) sends this one."""

    def __init__(self, from_id, name):
        PortIn.__init__(self)
        self.name = name
        self._every = from_id is None
        self._page = _tabs().openIn(from_id)
        self._any = self._page.any
        self._next = self._page.next
        self._closed = False

    @property
    def names(self):
        """The tabs it hears now: every other tab's name for `page_in`."""
        if self._every:
            return [info.name for info in available() if info.direction == IN]
        return [self.name]

    @property
    def overflows(self):
        """Messages dropped because nothing was reading."""
        return self._page.overflows()

    def any(self):
        if self._closed:
            raise OSError("MIDI input is closed")
        return self._any()

    def readinto(self, buf, nbytes=None):
        nbytes = min(_count(buf, nbytes), self.any())
        next_byte = self._next
        for i in range(nbytes):
            buf[i] = next_byte()
        return nbytes or None

    def close(self):
        if not self._closed:
            self._closed = True
            self._page.close()

    deinit = close


class _TabOut(_WholeOut):
    """Whole messages to one tab; ``dropped`` counts what went to a tab that closed."""

    def __init__(self, to_id, name):
        _WholeOut.__init__(self)
        self.name = name
        self.why = None
        self._page = _tabs().openOut(to_id)
        self._put = self._page.put
        self._send = self._page.send

    def _deliver(self, data):
        put = self._put
        for b in data:
            put(b)
        refused = self._send()
        if refused is not None:
            self.why = refused
            self.dropped += 1

    def close(self):
        if not self._closed:
            _WholeOut.close(self)
            self._page.close()

    deinit = close


def open_port(info):
    """Open one of `available`'s ports: an input hears that tab, an output sends to it."""
    if info.direction == IN:
        return _TabIn(info.id, info.name)
    return _TabOut(info.id, info.name)


def page_in():
    """An input hearing every tab that sends this one anything. Never blocks."""
    return _TabIn(None, "Other tabs")
