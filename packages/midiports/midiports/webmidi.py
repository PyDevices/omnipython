# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""MIDI in a browser, through Web MIDI, for Python running in Pyodide or MicroPython.

Web MIDI (``navigator.requestMIDIAccess``) exists only on a page's main
thread, never in a Web Worker, so there are two ways in.

On the page, with Pyodide on the main thread (PyScript, for one)::

    from midiports import webmidi

    midi_in, midi_out = await webmidi.open("keystation")

``name`` matches part of a port's name, ignoring case. The default, ``""``,
merges every input and sends to the first output. The browser asks the
person for permission the first time. A device plugged in later, or
unplugged and plugged back in, is picked up while the ports are open. If
your code already holds a ``MIDIAccess``, ``ports(access, name)`` does the
same without awaiting.

In a worker, a few lines of JavaScript on the page relay MIDI over a
``MessagePort``, and the worker opens ports on it::

    midi_in, midi_out = webmidi.relay_ports(port)

The relay's messages are plain objects:

- page to worker: ``{data: Uint8Array, timeStamp: number}``, one whole MIDI
  message per post, with ``timeStamp`` taken from the ``MIDIMessageEvent``.
- worker to page: ``{data: Uint8Array}``, whole messages for the page to
  ``send()`` to its output.

In MicroPython's WebAssembly port, open an input or an output without
awaiting::

    midi_in = webmidi.page_in("keystation")
    midi_out = webmidi.page_out("synth")

They read and write as any other ports do, with no timestamps. Asking for
MIDI happens in the background, so ``midi_in.names`` and ``midi_out.names``
are empty and ``midi_out.name`` is ``None`` until the person has said yes,
and ``why`` says why if the answer was no. ``midi_out.names`` lists every
output that matches, so a program can offer them; ``midi_out.name`` is the
one it sends to. Until an output is there, writes are dropped
and counted in ``midi_out.dropped``.

To choose ports one by one, in a picker or with ``endpointkit``,
``midiports.endpoints.register()`` lists the page's ports there: `available`
and `open_port` are its backend in a browser, `state` says whether the
person has allowed MIDI yet, and `request` asks them.

Timestamps
----------
Each input keeps the time every message arrived, as the package's contract
describes: whole microseconds, here on the page's ``performance.now()``
clock (the time Web MIDI stamps each event with, times 1000), which is also
what ``midiports.ticks_us()`` reads in Pyodide. ``take_timestamp()`` pops the
oldest one not yet taken, or returns ``None`` when there is none. Call it
once for each message ``adafruit_midi.MIDI.receive()`` hands you and you get
that message's time::

    msg = midi.receive()
    if msg is not None:
        when = midi_in.take_timestamp()

These are the browser's own times for each message, as fine as Web MIDI
makes them, so they don't depend on how often you poll. A relay message
without a ``timeStamp`` is stamped when it reaches the worker. A worker's
``performance.now()`` starts from the worker's own origin, not the page's,
so in a worker compare stamps with times the page sends, not with
``ticks_us()``.

That pairing holds because Web MIDI delivers whole messages, one timestamp
each. A message dropped because the input was full takes its timestamp with
it. If you never call ``take_timestamp()``, old timestamps are discarded and
nothing else changes.

Received bytes wait in a ring (``ring`` bytes, 1024 by default). If you don't
read for long enough to fill it, whole messages are dropped and counted in
``midi_in.overflows``. Writes are sent a whole message at a time, as Web MIDI
requires; with no output connected they are dropped and counted in
``midi_out.dropped``. Sending SysEx on the page needs ``open(sysex=True)``.

Inputs don't wrap themselves in ``WholeMessages``: Web MIDI already hands
over whole messages, never running status and never a clock byte inside a
note.
"""

from . import IN, OUT, PortIn, PortInfo, PortOut, Stamps, _count, _stamp, message_length, ticks_us

#: Longest unfinished message a write holds back, waiting for its end.
PENDING_LIMIT = 4096


# -- the browser's FFI, imported only when it's there ------------------------------


def _proxy(fn):
    """A JavaScript callable for ``fn`` that outlives this call."""
    try:
        from pyodide.ffi import create_proxy
    except ImportError:
        return fn
    return create_proxy(fn)


def _destroy(proxy):
    destroy = getattr(proxy, "destroy", None)
    if destroy is not None:
        destroy()


def _uint8(data):
    """``data`` as a JavaScript ``Uint8Array`` (plain ``bytes`` outside a browser)."""
    try:
        from js import Uint8Array
    except ImportError:
        return bytes(data)
    out = Uint8Array.new(len(data))
    try:
        out.assign(data)  # Pyodide's JsProxy copies in one call
    except AttributeError:  # MicroPython's has no assign: set each byte
        for i, b in enumerate(data):
            out[i] = b
    return out


def _object(**fields):
    """A plain JavaScript object (a ``dict`` outside a browser)."""
    try:
        from js import Object
        from pyodide.ffi import to_js
    except ImportError:
        return fields
    return to_js(fields, dict_converter=Object.fromEntries)


def _bytes(data):
    to_bytes = getattr(data, "to_bytes", None)
    return to_bytes() if to_bytes is not None else bytes(data)


def _us(stamp):
    """A Web MIDI ``timeStamp`` (ms) as whole microseconds; now if it has none."""
    try:
        return int(round(float(stamp) * 1000))
    except (TypeError, ValueError):
        return ticks_us()


def _matches(port, name):
    return not name or name.lower() in str(port.name).lower()


def _values(maplike):
    values = maplike.values()
    return list(values)


# -- input: a byte ring with a timestamp per message ---------------------------------


class _RingIn(PortIn):
    """Whole messages pushed in by the browser, read out like ``usb_midi``."""

    def __init__(self, ring=1024):
        PortIn.__init__(self)
        self._ring = bytearray(ring)
        self._head = 0
        self._tail = 0
        # One timestamp per message, oldest first. Room for one per byte of
        # the ring, plus some for messages already read whose timestamp
        # hasn't been taken yet.
        self._stamps = Stamps(ring + 64)
        self.overflows = 0
        self._closed = False

    def push(self, data, timestamp=None):
        """Queue one whole message that arrived at ``timestamp`` (us), or now."""
        if self._closed:
            return
        n = len(data)
        if not n:
            return
        ring = self._ring
        size = len(ring)
        head = self._head
        if (self._tail - head - 1) % size < n:
            self.overflows += 1
            return
        for i in range(n):
            ring[head] = data[i]
            head = (head + 1) % size
        self._head = head
        _stamp(self._stamps, data[0], ticks_us() if timestamp is None else timestamp)

    def any(self):
        if self._closed:
            raise OSError("MIDI input is closed")
        return (self._head - self._tail) % len(self._ring)

    def readinto(self, buf, nbytes=None):
        if self._closed:
            raise OSError("MIDI input is closed")
        nbytes = _count(buf, nbytes)
        ring = self._ring
        size = len(ring)
        tail = self._tail
        head = self._head
        i = 0
        while i < nbytes and tail != head:
            buf[i] = ring[tail]
            tail = (tail + 1) % size
            i += 1
        self._tail = tail
        return i or None

    def close(self):
        self._closed = True

    deinit = close


# -- output: whole messages only -----------------------------------------------------


class _WholeOut(PortOut):
    """Sends whole messages; a partial one waits for the rest of it.

    Web MIDI's ``send()`` refuses part of a message, so bytes that end
    mid-message are held until the write that finishes it. A data byte with
    no status before it can't be sent and is dropped.
    """

    def __init__(self):
        self._pending = bytearray()
        self.dropped = 0
        self._closed = False

    def _deliver(self, data):
        raise NotImplementedError

    def write(self, buf, nbytes=None):
        if self._closed:
            raise OSError("MIDI output is closed")
        n = _count(buf, nbytes)
        p = self._pending
        p.extend(memoryview(buf)[:n])
        size = len(p)
        out = bytearray()
        i = 0
        done = 0
        while i < size:
            b = p[i]
            if b < 0x80 or b == 0xF7:
                i += 1  # no status to belong to
            elif b >= 0xF8:
                out.append(b)
                i += 1
            elif b == 0xF0:
                j = i + 1
                while j < size and p[j] != 0xF7:
                    j += 1
                if j == size:
                    break
                out.extend(p[i:j + 1])
                i = j + 1
            else:
                end = i + 1 + message_length(b)
                if end > size:
                    break
                out.extend(p[i:end])
                i = end
            done = i
        if done:
            self._pending = p[done:]
        if len(self._pending) > PENDING_LIMIT:
            self._pending = bytearray()
            self.dropped += 1
        if out:
            self._deliver(out)
        return n

    def close(self):
        self._closed = True

    deinit = close


# -- on the page: a MIDIAccess -------------------------------------------------------


class _PageIn(_RingIn):
    def __init__(self, session, ring):
        _RingIn.__init__(self, ring)
        self._session = session

    @property
    def names(self):
        """The names of the inputs feeding this port right now."""
        return [port.name for port, _ in self._session.inputs.values()]

    def close(self):
        if not self._closed:
            _RingIn.close(self)
            self._session.closed_one()

    deinit = close


class _PageOut(_WholeOut):
    def __init__(self, session):
        _WholeOut.__init__(self)
        self._session = session

    @property
    def name(self):
        """The name of the output this port sends to, or ``None``."""
        output = self._session.output
        return None if output is None else output.name

    def _deliver(self, data):
        output = self._session.output
        if output is None:
            self.dropped += 1
            return
        output.send(_uint8(data))

    def close(self):
        if not self._closed:
            _WholeOut.close(self)
            self._session.closed_one()

    deinit = close


class _Session:
    """The inputs and output one ``ports()`` call holds, kept current."""

    def __init__(self, access, name, ring):
        self.access = access
        self.name = name
        self.inputs = {}  # id -> (MIDIInput, handler proxy)
        self.output = None
        self.open = 2
        self.midi_in = _PageIn(self, ring)
        self.midi_out = _PageOut(self)
        for port in _values(access.inputs):
            self.attach(port)
        for port in _values(access.outputs):
            self.adopt(port)
        self._on_state = _proxy(self.on_state)
        access.addEventListener("statechange", self._on_state)

    def attach(self, port):
        if port.id in self.inputs or not _matches(port, self.name):
            return
        midi_in = self.midi_in

        def on_message(event):
            midi_in.push(_bytes(event.data), _us(event.timeStamp))

        handler = _proxy(on_message)
        self.inputs[port.id] = (port, handler)
        port.onmidimessage = handler  # also opens the port

    def detach(self, port_id):
        entry = self.inputs.pop(port_id, None)
        if entry is not None:
            port, handler = entry
            port.onmidimessage = None
            _destroy(handler)

    def adopt(self, port):
        if self.output is None and _matches(port, self.name):
            self.output = port

    def on_state(self, event):
        port = event.port
        connected = port.state == "connected"
        if port.type == "input":
            if self.midi_in._closed:
                return
            if connected:
                self.attach(port)
            else:
                self.detach(port.id)
        elif port.type == "output":
            if self.midi_out._closed:
                return
            if connected:
                self.adopt(port)
            elif self.output is not None and self.output.id == port.id:
                self.output = None

    def closed_one(self):
        if self.midi_in._closed:
            for port_id in list(self.inputs):
                self.detach(port_id)
        if self.midi_out._closed:
            self.output = None
        self.open -= 1
        if not self.open:
            self.access.removeEventListener("statechange", self._on_state)
            _destroy(self._on_state)


def ports(access, name="", ring=1024):
    """``(midi_in, midi_out)`` over a ``MIDIAccess`` you already hold.

    ``name`` matches part of a port's name, ignoring case; ``""`` merges every
    input and sends to the first output. Ports that match later, plugged in
    or plugged back in, join while these are open. Closing both lets go of
    the browser's ports.
    """
    session = _Session(access, name, ring)
    return session.midi_in, session.midi_out


async def _request_access(sysex):
    from js import navigator

    if not hasattr(navigator, "requestMIDIAccess"):
        raise OSError(
            "this browser has no Web MIDI here (a worker never does: relay it from the page)"
        )
    return await navigator.requestMIDIAccess(_object(sysex=bool(sysex)))


async def open(name="", sysex=False, ring=1024):
    """Ask the browser for MIDI, then ``ports()`` on it. Awaitable.

    ``sysex=True`` asks for SysEx too, which browsers grant separately.
    Raises ``OSError`` where there is no Web MIDI, which includes any worker.
    """
    access = await _request_access(sysex)
    return ports(access, name, ring)


# -- MicroPython on the page: the bytes wait in JavaScript ---------------------------

#: The most bytes the page holds for a reader that has stopped reading.
PAGE_LIMIT = 4096

_PAGE_IN = """(name, limit) => {
    const bytes = [], inputs = new Map();
    let access = null, why = null, overflows = 0;
    name = name.toLowerCase();
    const update = (port) => {
        if (port.type !== 'input' || !String(port.name).toLowerCase().includes(name)) return;
        if (port.state !== 'connected') {
            inputs.delete(port.id);
            port.onmidimessage = null;
            return;
        }
        inputs.set(port.id, port);
        port.onmidimessage = (event) => {
            if (bytes.length + event.data.length > limit) overflows++;
            else bytes.push(...event.data);
        };
    };
    if (typeof navigator === 'undefined' || !navigator.requestMIDIAccess) {
        why = 'this browser has no Web MIDI here';
    } else {
        navigator.requestMIDIAccess().then((granted) => {
            access = granted;
            for (const port of access.inputs.values()) update(port);
            access.onstatechange = (event) => update(event.port);
        }, (error) => { why = String(error); });
    }
    return {
        any: () => bytes.length,
        next: () => bytes.shift(),
        names: () => Array.from(inputs.values(), (port) => port.name).join('\\n'),
        why: () => why,
        overflows: () => overflows,
        close: () => {
            if (access) access.onstatechange = null;
            for (const port of inputs.values()) port.onmidimessage = null;
            inputs.clear();
            bytes.length = 0;
        },
    };
}"""


class _PagePolledIn(PortIn):
    """An input the browser never calls into.

    MicroPython can be parked in a sleep when a message arrives, and running
    Python from the browser's callback then isn't safe. So JavaScript keeps
    the bytes until Python comes for them.
    """

    def __init__(self, name):
        PortIn.__init__(self)
        import js

        self._page = js.eval(_PAGE_IN)(name, PAGE_LIMIT)
        self._any = self._page.any
        self._next = self._page.next
        self._closed = False

    @property
    def names(self):
        """The names of the inputs feeding this port right now."""
        names = self._page.names()
        return names.split("\n") if names else []

    @property
    def why(self):
        """Why there's no MIDI, in a sentence, or ``None``."""
        return self._page.why()

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


def page_in(name=""):
    """An input over every matching port, for MicroPython's WebAssembly port.

    ``name`` matches part of a port's name, ignoring case; ``""`` merges every
    input. Ports that match later join while it's open. Never blocks.
    """
    return _PagePolledIn(name)


_PAGE_OUT = """(name) => {
    const pending = [];
    let access = null, output = null, why = null;
    name = name.toLowerCase();
    const matches = (port) => port.type === 'output' && String(port.name).toLowerCase().includes(name);
    const update = (event) => {
        const port = event.port;
        if (!matches(port)) return;
        if (port.state === 'connected') {
            if (output === null) output = port;
        } else if (output !== null && output.id === port.id) {
            output = null;
            for (const other of access.outputs.values()) {
                if (other.state === 'connected' && matches(other)) { output = other; break; }
            }
        }
    };
    if (typeof navigator === 'undefined' || !navigator.requestMIDIAccess) {
        why = 'this browser has no Web MIDI here';
    } else {
        navigator.requestMIDIAccess().then((granted) => {
            access = granted;
            for (const port of access.outputs.values()) {
                if (matches(port)) { output = port; break; }
            }
            access.addEventListener('statechange', update);
        }, (error) => { why = String(error); });
    }
    return {
        put: (byte) => { pending.push(byte); },
        send: () => {
            const data = new Uint8Array(pending);
            pending.length = 0;
            if (output === null) return false;
            try {
                output.send(data);
            } catch (error) {
                why = String(error);
                return false;
            }
            return true;
        },
        name: () => (output === null ? null : output.name),
        names: () => (access === null ? '' : Array.from(access.outputs.values())
            .filter((port) => port.state === 'connected' && matches(port))
            .map((port) => port.name).join('\\n')),
        why: () => why,
        close: () => {
            if (access) access.removeEventListener('statechange', update);
            output = null;
            pending.length = 0;
        },
    };
}"""


class _PageSentOut(_WholeOut):
    """An output that hands whole messages to the page, a byte at a time.

    Plain integers cross from MicroPython to JavaScript without a proxy, so
    the page builds each write's messages from them and sends them. A send the
    browser refuses (SysEx it wasn't granted, say) is dropped and counted,
    and ``why`` says what the browser said.
    """

    def __init__(self, name):
        _WholeOut.__init__(self)
        import js

        self._page = js.eval(_PAGE_OUT)(name)
        self._put = self._page.put
        self._send = self._page.send

    @property
    def name(self):
        """The name of the output this port sends to, or ``None``."""
        return self._page.name()

    @property
    def names(self):
        """Every connected output that matches, which this port could send to."""
        names = self._page.names()
        return names.split("\n") if names else []

    @property
    def why(self):
        """Why there's no MIDI, in a sentence, or ``None``."""
        return self._page.why()

    def _deliver(self, data):
        put = self._put
        for b in data:
            put(b)
        if not self._send():
            self.dropped += 1

    def close(self):
        if not self._closed:
            _WholeOut.close(self)
            self._page.close()

    deinit = close


def page_out(name=""):
    """An output to the first matching port, for MicroPython's WebAssembly port.

    ``name`` matches part of a port's name, ignoring case; ``""`` takes the
    first output. If that port goes away, another that matches takes its
    place, and one plugged in later is picked up. Never blocks.
    """
    return _PageSentOut(name)


# -- the page's ports one at a time, for midiports.endpoints ------------------------

#: The most stamps an input keeps for messages whose time nobody took.
STAMP_LIMIT = 1024

_ACCESS = """(limit, stampLimit) => {
    const nav = globalThis.navigator;
    const has = !!(nav && nav.requestMIDIAccess);
    let access = null, state = has ? 'idle' : 'unsupported', why = has ? null : 'This browser has no Web MIDI', changes = 0;
    const watchers = new Set();
    const bump = () => { changes++; for (const watch of watchers) watch(); };
    const ask = () => {
        if (!has || state === 'asking' || state === 'granted') return;
        state = 'asking';
        why = null;
        bump();
        nav.requestMIDIAccess().then((granted) => {
            access = granted;
            state = 'granted';
            access.addEventListener('statechange', bump);
            bump();
        }, (error) => {
            state = 'denied';
            why = String((error && error.message) || error);
            bump();
        });
    };
    if (has && nav.permissions && nav.permissions.query) {
        // A page the person already allowed lists its ports without asking again.
        nav.permissions.query({name: 'midi'}).then((status) => {
            if (status.state === 'granted') ask();
            else if (status.state === 'denied' && state === 'idle') {
                state = 'denied';
                why = 'MIDI is blocked for this page in the browser\\'s site settings';
                bump();
            }
            // Allowed later, by a program's own request or the site settings: list the ports then.
            if ('onchange' in status) status.onchange = () => { if (status.state === 'granted' && state === 'idle') ask(); };
        }, () => {});
    }
    const ports = (kind) => (access === null ? [] : Array.from(kind === 'in' ? access.inputs.values() : access.outputs.values()));
    const list = () => ['in', 'out'].flatMap((kind) => ports(kind)
        .filter((port) => port.state === 'connected')
        .map((port) => kind + '\\t' + port.id + '\\t' + String(port.name).replace(/[\\t\\n]/g, ' '))).join('\\n');
    const find = (kind, id) => ports(kind).find((port) => port.id === id && port.state === 'connected') || null;
    const openIn = (id) => {
        const bytes = [], stamps = [];
        let port = null, overflows = 0;
        const heard = (event) => {
            if (bytes.length + event.data.length > limit) { overflows++; return; }
            bytes.push(...event.data);
            stamps.push(Math.round(event.timeStamp * 1000));
            if (stamps.length > stampLimit) stamps.shift();
        };
        const attach = () => {
            const found = find('in', id);
            if (found === port) return;
            if (port !== null) port.removeEventListener('midimessage', heard);
            port = found;
            if (port !== null) {
                port.addEventListener('midimessage', heard);
                port.open().catch(() => {});
            }
        };
        attach();
        watchers.add(attach);
        return {
            any: () => bytes.length,
            next: () => bytes.shift(),
            stamp: () => (stamps.length ? stamps.shift() : null),
            overflows: () => overflows,
            connected: () => port !== null,
            close: () => {
                watchers.delete(attach);
                if (port !== null) port.removeEventListener('midimessage', heard);
                port = null;
                bytes.length = 0;
                stamps.length = 0;
            },
        };
    };
    const openOut = (id) => {
        const pending = [];
        return {
            put: (byte) => { pending.push(byte); },
            send: () => {
                const data = new Uint8Array(pending);
                pending.length = 0;
                const port = find('out', id);
                if (port === null) return 'not connected';
                try { port.send(data); } catch (error) { return String(error); }
                return null;
            },
            connected: () => find('out', id) !== null,
            close: () => { pending.length = 0; },
        };
    };
    return {state: () => state, why: () => why, changes: () => changes, ask, list, openIn, openOut};
}"""

_access = []


def _page_access():
    """The page's one MIDIAccess holder, made the first time it's needed."""
    if not _access:
        import js

        _access.append(js.eval(_ACCESS)(PAGE_LIMIT, STAMP_LIMIT))
    return _access[0]


def state():
    """Where the page stands with Web MIDI.

    ``"idle"`` until something asks (`request`), ``"asking"`` while the
    browser asks the person, ``"granted"``, ``"denied"``, or
    ``"unsupported"`` in a browser with no Web MIDI here (Safari, or any
    worker). A page the person already allowed is asked again at once,
    without a prompt, the first time this is called.
    """
    return _page_access().state()


def why():
    """Why there are no ports, in a sentence, or ``None``."""
    return _page_access().why()


def request():
    """Ask the browser for MIDI, in the background; `state` says how it went.

    Nothing happens once the page is granted or while the browser is asking.
    """
    _page_access().ask()


def changes():
    """A count that moves whenever the permission or a port's state changes."""
    return _page_access().changes()


def available():
    """Every connected port the page may use, both directions, as ``PortInfo``.

    Empty until the page is granted (`state`). This and `open_port` make
    this module a backend for ``midiports.endpoints``.
    """
    text = _page_access().list()
    found = []
    for line in text.split("\n") if text else ():
        kind, port_id, name = line.split("\t", 2)
        found.append(PortInfo(id=port_id, name=name, direction=IN if kind == "in" else OUT))
    return tuple(found)


class _PortPolledIn(PortIn):
    """One of the page's inputs, by id, polled as `page_in` is, with timestamps.

    The port keeps its place when the device is unplugged: plugged back in,
    it's read again.
    """

    def __init__(self, info):
        PortIn.__init__(self)
        self.info = info
        self.name = info.name
        self._page = _page_access().openIn(info.id)
        self._any = self._page.any
        self._next = self._page.next
        self._closed = False

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

    def take_timestamp(self):
        return self._page.stamp()

    def close(self):
        if not self._closed:
            self._closed = True
            self._page.close()

    deinit = close


class _PortSentOut(_WholeOut):
    """One of the page's outputs, by id. Writes while it's unplugged are
    dropped and counted in ``dropped``, and ``why`` says what the browser
    last refused."""

    def __init__(self, info):
        _WholeOut.__init__(self)
        self.info = info
        self.name = info.name
        self.why = None
        self._page = _page_access().openOut(info.id)
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
    """Open one of `available`'s ports: an input reads it alone, an output
    sends to it alone. Never blocks."""
    return _PortPolledIn(info) if info.direction == IN else _PortSentOut(info)


# -- in a worker: the page relays over a MessagePort ------------------------------


class _RelayIn(_RingIn):
    def __init__(self, port, ring):
        _RingIn.__init__(self, ring)
        self._port = port
        self._handler = _proxy(self._on_message)
        port.addEventListener("message", self._handler)
        start = getattr(port, "start", None)
        if start is not None:
            start()

    def _on_message(self, event):
        message = event.data
        data = getattr(message, "data", None)
        if data is None:
            return
        self.push(_bytes(data), _us(getattr(message, "timeStamp", None)))

    def close(self):
        if not self._closed:
            _RingIn.close(self)
            self._port.removeEventListener("message", self._handler)
            _destroy(self._handler)

    deinit = close


class _RelayOut(_WholeOut):
    def __init__(self, port):
        _WholeOut.__init__(self)
        self._port = port

    def _deliver(self, data):
        self._port.postMessage(_object(data=_uint8(data)))


def relay_ports(port, ring=1024):
    """``(midi_in, midi_out)`` over a ``MessagePort`` the page relays MIDI on.

    For a worker, where Web MIDI doesn't exist. The page posts
    ``{data, timeStamp}`` for each message it receives and sends the
    ``{data}`` this posts back. Closing the ports leaves ``port`` open.
    """
    return _RelayIn(port, ring), _RelayOut(port)
