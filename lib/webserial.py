# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""A browser page's serial ports, through Web Serial, as endpointkit ``serial`` endpoints.

In MicroPython's WebAssembly port, register the provider and the serial
ports the person has let the page use appear under ``serial``, with one more
endpoint, "Choose a serial port". Pairing that one (a tap in appkit's
picker, or `endpointkit.pair`) opens the browser's chooser, and the port
picked joins the list. The browser remembers the ports it was given, so they
are listed again when the page reloads::

    import endpointkit
    import webserial

    webserial.register()
    ep = endpointkit.selected("serial")[0]
    port = webserial.open(ep, baudrate=115200)
    port.write(b"\\r\\n")
    data = port.read()                       # what has arrived, or None

A port is opened by the program that uses it, at the speed it wants, and
never blocks: `Port.read` hands out what has arrived. A board's USB serial
REPL, a USB serial adapter or a board's UART bridge all work.

It needs Chrome or Edge on a computer and a secure context; elsewhere the
endpoint is unavailable and says why. The chooser only opens from a tap or
a click.
"""

import endpointkit

#: The kind's name, how many can be chosen, what a person calls it, and its icon.
KIND = "serial"

#: The local id of the endpoint that opens the browser's chooser.
ASK = "ask"
#: What that endpoint says.
ASK_LABEL = "Choose a serial port"

#: The makers a port's USB vendor ID names, for its label.
VENDORS = {
    0x0403: "FTDI",
    0x10C4: "Silicon Labs",
    0x1A86: "WCH",
    0x239A: "Adafruit",
    0x2341: "Arduino",
    0x2E8A: "Raspberry Pi",
    0x303A: "Espressif",
    0x1915: "Nordic",
    0x0D28: "Arm mbed",
    0x16C0: "Teensy",
    0x1209: "pid.codes",
}

# Every call into the page goes through these few functions: strings,
# numbers and booleans across, and bytes as hex.
_PAGE = """() => {
  const serial = globalThis.navigator && navigator.serial;
  const ports = [];   // every port the page has been given, in the order it was
  const st = [];      // per port: {open, rx: [], error, gone}
  let changes = 0, asking = false, refused = '';
  const hex = (u) => { let s = ''; for (const b of u) s += (b < 16 ? '0' : '') + b.toString(16); return s; };
  const add = (port) => {
    if (ports.indexOf(port) < 0) { ports.push(port); st.push({open: false, rx: [], error: '', gone: false}); changes++; }
    else { st[ports.indexOf(port)].gone = false; changes++; }
  };
  if (serial) {
    serial.getPorts().then((found) => found.forEach(add), () => {});
    serial.addEventListener('connect', (e) => add(e.target || e.port));
    serial.addEventListener('disconnect', (e) => {
      const i = ports.indexOf(e.target || e.port);
      if (i >= 0) { st[i].gone = true; st[i].open = false; changes++; }
    });
  }
  const reading = async (i) => {
    const port = ports[i];
    while (st[i].open && port.readable) {
      const reader = port.readable.getReader();
      st[i].reader = reader;
      try {
        for (;;) {
          const {value, done} = await reader.read();
          if (done) break;
          if (value) st[i].rx.push(hex(value));
        }
      } catch (e) {
        if (st[i].open) st[i].error = String(e && e.message || e);
      } finally {
        reader.releaseLock();
      }
      if (st[i].error) break;
    }
  };
  return {
    has: () => !!serial,
    changes: () => changes,
    count: () => ports.length,
    gone: (i) => st[i].gone,
    info: (i) => { const f = ports[i].getInfo ? ports[i].getInfo() : {}; return (f.usbVendorId || 0) * 65536 + (f.usbProductId || 0); },
    asking: () => asking,
    refused: () => { const r = refused; refused = ''; return r; },
    request: () => {
      if (!serial || asking) return;
      asking = true; changes++;
      serial.requestPort().then((port) => { asking = false; add(port); },
        (e) => { asking = false; refused = String(e && e.message || e); changes++; });
    },
    open: (i, baud) => {
      if (st[i].open || st[i].opening) return;
      st[i].opening = true; st[i].error = '';
      ports[i].open({baudRate: baud}).then(() => { st[i].opening = false; st[i].open = true; changes++; reading(i); },
        (e) => { st[i].opening = false; st[i].error = String(e && e.message || e); changes++; });
    },
    state: (i) => st[i].open ? 1 : st[i].opening ? 0 : -1,
    error: (i) => st[i].error,
    take: (i) => { const r = st[i].rx.join(''); st[i].rx.length = 0; return r; },
    write: (i, h) => {
      if (!st[i].open || !ports[i].writable) return false;
      const a = new Uint8Array(h.length >> 1);
      for (let k = 0; k < a.length; k++) a[k] = parseInt(h.substr(k * 2, 2), 16);
      const w = ports[i].writable.getWriter();
      w.write(a).catch((e) => { st[i].error = String(e && e.message || e); }).finally(() => w.releaseLock());
      return true;
    },
    close: (i) => {
      if (!st[i].open) return;
      st[i].open = false;
      const r = st[i].reader;
      Promise.resolve(r && r.cancel()).catch(() => {}).then(() => ports[i].close()).catch(() => {});
      changes++;
    },
  };
}"""

_page = []


def _the_page():
    if not _page:
        import js

        _page.append(js.eval(_PAGE)())
    return _page[0]


def label(code):
    """What a port is called, from its USB vendor and product IDs as one number."""
    vid, pid = code >> 16, code & 0xFFFF
    if not vid:
        return "Serial port"
    maker = VENDORS.get(vid)
    ids = "%04x:%04x" % (vid, pid)
    return "%s (%s)" % (maker, ids) if maker else "USB serial (%s)" % ids


class Port:
    """One open serial port. Nothing blocks: `read` hands out what has arrived.

    ``name`` is the port's label, and ``error`` what stopped it, if
    something did.
    """

    def __init__(self, page, index, name, baudrate):
        self._page = page
        self._i = index
        self.name = name
        self.baudrate = baudrate
        self._rx = b""
        page.open(index, baudrate)

    @property
    def error(self):
        return str(self._page.error(self._i)) or None

    def is_open(self):
        """True once the browser has opened the port."""
        return self._page.state(self._i) == 1

    def _pull(self):
        got = str(self._page.take(self._i))
        if got:
            self._rx += bytes.fromhex(got)

    def any(self):
        """How many bytes are waiting."""
        self._pull()
        return len(self._rx)

    def read(self, nbytes=None):
        """What has arrived, up to *nbytes*, as ``bytes``; None when nothing has."""
        self._pull()
        if not self._rx:
            return None
        n = len(self._rx) if nbytes is None else min(nbytes, len(self._rx))
        out, self._rx = self._rx[:n], self._rx[n:]
        return out

    def readinto(self, buf, nbytes=None):
        data = self.read(len(buf) if nbytes is None else min(nbytes, len(buf)))
        if data is None:
            return None
        buf[: len(data)] = data
        return len(data)

    def write(self, buf):
        """Send *buf*; its length, or None while the port isn't open yet."""
        data = bytes(buf)
        if not data:
            return 0
        return len(data) if self._page.write(self._i, data.hex()) else None

    def close(self):
        """Close the port, so another program, or another page, can open it."""
        self._page.close(self._i)

    deinit = close

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class Ports(endpointkit.Provider):
    """The serial ports the person has let this page use, under ``serial``.

    Args:
        page (object): what reaches Web Serial; the page's own when None.
    """

    kind = KIND
    name = "webserial"

    def __init__(self, page=None):
        endpointkit.Provider.__init__(self)
        self.page = page if page is not None else _the_page()
        self._ids = {}  # local id -> the port's index in the page
        self._changes = None
        self._seen = None

    def _ask(self):
        if not self.page.has():
            return self.endpoint(ASK, ASK_LABEL, endpointkit.UNAVAILABLE,
                                 caps={"why": "This browser has no Web Serial: Chrome or Edge on a computer has"})
        refused = str(self.page.refused())
        if self.page.asking():
            why = "The browser is asking"
        elif refused:
            why = refused
        else:
            why = "Tap to have the browser ask"
        return self.endpoint(ASK, ASK_LABEL, endpointkit.NEEDS_PAIRING, caps={"why": why, "grant": True})

    def scan(self):
        self._changes = self.page.changes()
        found = []
        ids = {}
        if self.page.has():
            for i in range(self.page.count()):
                if self.page.gone(i):
                    continue
                name = label(self.page.info(i))
                local = name
                n = 2
                while local in ids:  # two of the same adapter
                    local = "%s #%d" % (name, n)
                    n += 1
                ids[local] = i
                found.append(self.endpoint(local, local, caps={"index": i}))
        found.append(self._ask())
        self._ids = ids
        self._seen = [(ep.id, ep.state, ep.caps.get("why")) for ep in found]
        return found

    def poll(self):
        if self.page.changes() == self._changes:
            return None
        before = self._seen
        found = self.scan()
        return found if self._seen != before else None

    def pair(self, endpoint, secret=None):
        """Have the browser open its chooser; the port picked follows from `poll`."""
        if endpoint.local_id != ASK:
            endpointkit.Provider.pair(self, endpoint, secret)
        self.page.request()

    def apply(self, endpoint, chosen):
        local = endpoint.local_id
        if chosen and local not in self._ids:
            raise OSError(endpoint.caps.get("why") if local == ASK else "%s isn't plugged in" % endpoint.label)
        endpoint.state = endpointkit.CONNECTED if chosen else endpointkit.AVAILABLE

    def open(self, endpoint, baudrate=115200):
        """Open the port behind *endpoint* at *baudrate*, as a `Port`."""
        index = self._ids.get(endpoint.local_id)
        if index is None:
            raise OSError("%s isn't plugged in" % endpoint.label)
        return Port(self.page, index, endpoint.label, baudrate)


_provider = []


def register(registry=None, page=None):
    """Add the ``serial`` kind if it's new, and register the page's ports; returns the provider."""
    if KIND not in endpointkit.KINDS:
        endpointkit.add_kind(KIND, endpointkit.MANY, "Serial ports", "usb")
    provider = Ports(page)
    (registry or endpointkit).register(provider)
    _provider[:] = [provider]
    return provider


def open(endpoint, baudrate=115200):
    """Open a chosen ``serial`` endpoint of this page's, at *baudrate*, as a `Port`."""
    for provider in _provider:
        if endpoint.id.startswith(provider.name + ":"):
            return provider.open(endpoint, baudrate)
    raise OSError("%s isn't one of this page's serial ports" % endpoint.label)
