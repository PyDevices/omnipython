# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""A browser page's camera, read the way cameraif reads a board's.

In MicroPython's WebAssembly port, `Camera` opens the camera the browser
gives the page (``getUserMedia``) and hands out its frames as cameraif's
``Camera`` does: `Camera.capture_scaled` scales the next one into a block of
an RGB565 picture, such as a preview's buffer, and `Camera.capture_jpeg`
encodes one. A board's ``board_peripherals.camera()`` is this in a browser,
so a camera app runs unchanged::

    from displaydev.page_camera import Camera

    cam = Camera()
    w, h = cam.size()[:2]
    buf = bytearray(160 * 120 * 2)
    cam.capture_scaled(buf, 160, 120)

`Cameras` lists the page's cameras under ``camera`` in endpointkit
(`displaydev.endpoints.register` adds it in a browser). The one chosen there
is the one a `Camera` opens, and choosing another while one is open moves it
there. A browser names its cameras only once the person has let the page use
one; until then they're "Camera 1", "Camera 2" and so on.

The frames come through the runtime's bridge (``_wasm_bridge``); a runtime
from before the camera has none, and `Camera` says so.
"""

import endpointkit

#: The local id of the endpoint that leaves the choice to the browser.
DEFAULT = "default"

#: How long, in milliseconds, `Camera` waits for the browser to open the
#: camera: the person may be answering the browser's question.
OPEN_MS = 30000

_STEP_MS = 5

#: How long, in milliseconds, `Camera` waits for the browser's list of
#: cameras, so a camera chosen before the page started is the one it opens.
LIST_MS = 2000

_listing = []  # every `Cameras` made, to wait for before a camera opens

# Why the camera didn't open, by the bridge's camera_state.
_WHY = {
    -1: "this page wasn't allowed to use the camera: allow it in the browser, then open the app again",
    -2: "the browser found no camera",
    -3: "this browser gives a page no camera",
    -4: "the camera wouldn't open",
}

_DEVICES = """() => {
    const media = globalThis.navigator && navigator.mediaDevices;
    const has = !!(media && media.enumerateDevices && media.getUserMedia);
    let text = '', changes = 0, listed = false;
    const refresh = () => media.enumerateDevices().then((found) => {
        listed = true;
        const lines = [];
        for (const device of found) {
            if (device.kind !== 'videoinput') continue;
            lines.push(device.deviceId + '\\t' + (device.label || '').replace(/[\\t\\n]/g, ' '));
        }
        const next = lines.join('\\n');
        if (next !== text) { text = next; changes++; }
    }, () => {});
    if (has) {
        refresh();
        if (media.addEventListener) media.addEventListener('devicechange', refresh);
    }
    return {has: () => has, list: () => text, changes: () => changes, listed: () => listed || !has, refresh};
}"""

_ROUTE = """() => { const b = globalThis.Module && globalThis.Module.omnipythonBridge; return b && b.route ? b : null; }"""


def _bridge():
    try:
        import _wasm_bridge
    except ImportError:
        return None
    return _wasm_bridge if hasattr(_wasm_bridge, "camera_open") else None


def _settle_choice(bridge, wait_ms=LIST_MS):
    """Wait for the browser to list its cameras, polling endpointkit so the
    camera chosen there (perhaps before the page started) is routed first."""
    if not _listing:
        return
    waited = 0
    while waited < wait_ms and any(not p.listed() for p in _listing):
        bridge.sleep_ms(20)
        waited += 20
    endpointkit.poll()


class Camera:
    """The page's camera, open: the one chosen in endpointkit, or the
    browser's choice.

    Waits up to `LIST_MS` for the browser's list of cameras, so the one
    chosen is routed first, then up to `OPEN_MS` for the browser to open it,
    since it may be asking the person.

    Args:
        format (object): taken for a board's camera mode, and ignored: the
            browser picks the camera's size.
        flip (bool): turn the picture upside down.
        mirror (bool): mirror it left to right.
        timeout (int): milliseconds to wait for the camera to open.
        bridge (object): the runtime's bridge; ``_wasm_bridge`` when None.

    Raises:
        OSError: the runtime has no camera, the browser has none, or the
            person didn't allow it; the message says which.
    """

    def __init__(self, format=None, flip=False, mirror=False, timeout=OPEN_MS, bridge=None):
        if bridge is None:
            bridge = _bridge()
        if bridge is None:
            raise OSError("this page's runtime has no camera")
        self._b = bridge
        self._flip = bool(flip)
        self._mirror = bool(mirror)
        self._open = False
        _settle_choice(bridge)
        bridge.camera_open()
        waited = 0
        while True:
            state = bridge.camera_state()
            if state == 1:
                break
            if state < 0:
                bridge.camera_close()
                raise OSError(_WHY.get(state, _WHY[-4]))
            if waited >= timeout:
                bridge.camera_close()
                raise OSError("the camera didn't open: allow it in the browser, then open the app again")
            bridge.sleep_ms(_STEP_MS * 10)
            waited += _STEP_MS * 10
        self._open = True

    def _flags(self, mirror=False):
        return (1 if self._flip else 0) | (2 if self._mirror != bool(mirror) else 0)

    def size(self):
        """``(width, height, bytes_per_frame)`` of the camera's picture, in RGB565."""
        w, h = self._b.camera_size()
        return (w, h, w * h * 2)

    def capture_scaled(self, dst, pic_w, pic_h, *, x=0, y=0, w=0, h=0, rotate=0, mirror=False, src_rect=None, swap=False, timeout=1000):
        """Scale the next frame into a block of a *pic_w* x *pic_h* RGB565 picture.

        Takes what cameraif's ``capture_scaled`` takes, but a browser's
        camera neither turns by 90 degrees nor crops.

        Args:
            dst: the picture's buffer.
            pic_w: its width.
            pic_h: its height.
            x: the block's left edge.
            y: its top edge.
            w: its width; 0 fills to the picture's edge.
            h: its height; 0 fills to the picture's edge.
            rotate: 0 or 180 degrees.
            mirror: mirror this frame, on top of the camera's mirror.
            src_rect: must be None.
            swap: swap each pixel's two bytes, for big-endian RGB565.
            timeout: milliseconds to wait for a new frame.

        Returns:
            The ``(width, height)`` written, or None when no frame came.
        """
        if rotate not in (0, 180) or src_rect is not None:
            raise ValueError("a browser camera turns by 180 degrees only, and doesn't crop")
        w = w or pic_w - x
        h = h or pic_h - y
        flags = self._flags(mirror) | (4 if swap else 0)
        if rotate == 180:
            flags ^= 3
        waited = 0
        while not self._b.camera_readinto(dst, pic_w, pic_h, x, y, w, h, flags):
            if waited >= timeout:
                return None
            self._b.sleep_ms(_STEP_MS)
            waited += _STEP_MS
        return (w, h)

    def capture_jpeg(self, quality=80, timeout=1000):
        """The current frame as a JPEG, at the camera's size; None when there's none.

        Args:
            quality: 1 to 100; higher is sharper and larger.
            timeout: milliseconds to wait for a frame.
        """
        waited = 0
        while True:
            jpeg = self._b.camera_jpeg(quality, self._flags())
            if jpeg is not None or waited >= timeout:
                return jpeg
            self._b.sleep_ms(_STEP_MS)
            waited += _STEP_MS

    def flip(self, on=None):
        """Read or set the upside-down turn."""
        if on is not None:
            self._flip = bool(on)
        return self._flip

    def mirror(self, on=None):
        """Read or set the left-to-right mirror."""
        if on is not None:
            self._mirror = bool(on)
        return self._mirror

    def exposure(self, pct=None, raw=False):
        """None: the browser keeps the camera's exposure to itself."""
        return None

    def gain(self, pct=None, raw=False):
        """None: the browser keeps the camera's gain to itself."""
        return None

    def reg(self, *args):
        """None: a browser camera has no sensor registers to write."""
        return None

    def close(self):
        """Let the camera go, so the browser stops showing it in use."""
        if self._open:
            self._open = False
            self._b.camera_close()

    deinit = close

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class Cameras(endpointkit.Provider):
    """The page's cameras under ``camera``.

    Args:
        devices (object): what lists the cameras, with ``has()``, ``list()``
            (lines of "id<TAB>label") and ``changes()``; the page's own when
            None.
        route (object): what moves the page's camera, with ``route(way,
            device_id)``; the runtime's when None.
        has_camera (bool): whether the runtime reads a camera; asked of it
            when None.
    """

    kind = "camera"
    name = "page-camera"

    def __init__(self, devices=None, route=None, has_camera=None):
        endpointkit.Provider.__init__(self)
        if devices is None or route is None:
            import js
        if devices is None:
            devices = js.eval(_DEVICES)()
        if route is None:
            route = js.eval(_ROUTE)()
        if has_camera is None:
            has_camera = _bridge() is not None
        self.devices = devices
        self.route = route
        self.has_camera = has_camera
        self._ids = {}  # local id -> the browser's deviceId
        self._changes = None
        self._seen = None
        _listing.append(self)

    def listed(self):
        """Whether the browser has answered with its cameras, so a choice
        made before the page started has been routed."""
        listed = getattr(self.devices, "listed", None)
        return listed() if listed is not None else self.devices.changes() > 0

    def _why(self):
        """Why only the browser's choice is listed, or None when cameras can be chosen."""
        if not self.has_camera or self.route is None:
            return "This page's runtime has no camera"
        if not self.devices.has():
            return "This browser gives a page no camera"
        return None

    def scan(self):
        self._changes = self.devices.changes()
        found = [self.endpoint(DEFAULT, "Browser's choice", caps={"page_device": ""})]
        ids = {}
        why = self._why()
        if why is None:
            text = str(self.devices.list())
            n = 0
            for line in text.split("\n") if text else ():
                device_id, label = line.split("\t", 1)
                n += 1
                label = label or "Camera %d" % n
                local = label
                k = 2
                while local in ids:  # two of the same camera
                    local = "%s #%d" % (label, k)
                    k += 1
                ids[local] = device_id
                found.append(self.endpoint(local, local, caps={"page_device": device_id}))
        else:
            found[0].caps["why"] = why
        self._ids = ids
        self._seen = [ep.id for ep in found]
        return found

    def poll(self):
        if self.devices.changes() == self._changes:
            return None
        before = self._seen
        found = self.scan()
        return found if self._seen != before else None

    def apply(self, endpoint, chosen):
        local = endpoint.local_id
        if chosen and local != DEFAULT and local not in self._ids:
            raise OSError(self._why() or "%s isn't listed now" % endpoint.label)
        endpoint.state = endpointkit.CONNECTED if chosen else endpointkit.AVAILABLE
        if self.route is not None:
            self.route.route("camera", self._ids.get(local, "") if chosen else "")
