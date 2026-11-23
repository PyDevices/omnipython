# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""A page's serial port or Bluetooth link, for Python running in the browser.

``hmilink.js``, beside this package, opens a port on the page: a board on
USB through WebSerial, or one advertising the Nordic UART service (`hmilink.ble`)
through Web Bluetooth. Python in MicroPython's WebAssembly build, or in
Pyodide, then runs a device or a panel over it with `hmilink.stream`::

    // on the page, from a click: the browser asks which device
    import { openSerial, openBluetooth } from "./hmilink.js";
    globalThis.hmilinkPort = await openBluetooth({ name: "rack" });

    # in Python
    import js
    from hmilink import stream, web
    panel = hmilink.Panel(stream.link(web.stream(js.hmilinkPort)))

The page holds what arrives until Python asks for it, so nothing runs
Python from a browser callback. A port that closes, because the board went
away or the page closed it, closes the link.
"""


def _bytes(data):
    to_bytes = getattr(data, "to_bytes", None)  # Pyodide's JsProxy
    return to_bytes() if to_bytes is not None else bytes(data)


class Stream:
    """``read`` and ``write`` over a port from ``hmilink.js``, for `hmilink.stream.link`.

    Any object with the same three members works too: ``read(n)`` returning
    up to ``n`` bytes as a ``Uint8Array`` (empty or ``null`` when nothing
    waits), ``write(text)`` returning how many bytes it took, all or none, and
    ``closed``.
    """

    def __init__(self, port):
        self.port = port

    def read(self, n):
        data = self.port.read(n)
        if data is not None and data.length:
            return _bytes(data)
        if self.port.closed:
            raise OSError("the page's port closed")
        return None

    def write(self, data):
        if self.port.closed:
            raise OSError("the page's port closed")
        # Frames are JSON, so UTF-8 text; a string crosses into JavaScript
        # on every runtime, and the link only ever offers whole frames.
        return self.port.write(bytes(data).decode())


def stream(port):
    """A stream over ``port`` (a port from ``hmilink.js``) for `hmilink.stream.link`."""
    return Stream(port)
