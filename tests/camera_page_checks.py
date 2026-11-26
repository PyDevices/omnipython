# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""A browser page's cameras in endpointkit, and the camera a program opens,
against a fake browser.

Runs on the MicroPython WebAssembly build under node (``wasm_node_run.mjs``),
where ``js`` is the real FFI and ``navigator.mediaDevices`` and the runtime's
``Module.omnipythonBridge`` are JavaScript stand-ins. The frames come from a
stand-in for the runtime's ``_wasm_bridge``.
"""

import sys

try:
    _here = __file__
except NameError:  # pragma: no cover
    _here = sys.argv[0]
_dir = _here.rsplit("/", 1)[0] if "/" in _here else "."
sys.path.insert(0, _dir + "/../packages/endpointkit")
sys.path.insert(0, _dir + "/../lib")

import asyncio

import js

import endpointkit
from displaydev import page_camera

TESTS = []


class Air:
    """Nothing: these checks need no radio."""


class Failed(Exception):
    pass


def check(fn):
    TESTS.append(fn)
    return fn


def expect(cond, message="expectation failed"):
    if not cond:
        raise Failed(message)


# A laptop's camera and a USB one, labelled or not, and a runtime that routes.
_FAKE = """(labels, media) => {
    const devices = [
        {kind: 'audioinput', deviceId: 'mic', label: 'Mic'},
        {kind: 'videoinput', deviceId: 'front', label: labels ? 'Integrated Camera' : ''},
        {kind: 'videoinput', deviceId: 'usb', label: labels ? 'USB Camera' : ''},
    ];
    const heard = new Set();
    const fake = {routes: []};
    fake.plug = (deviceId, label) => { devices.push({kind: 'videoinput', deviceId, label}); for (const fn of heard) fn(); };
    fake.unplug = (deviceId) => { devices.splice(devices.findIndex((d) => d.deviceId === deviceId), 1); for (const fn of heard) fn(); };
    const api = {
        enumerateDevices: () => Promise.resolve(devices.map((d) => Object.assign({}, d))),
        getUserMedia: () => Promise.reject(new Error('not in these checks')),
        addEventListener: (type, fn) => { if (type === 'devicechange') heard.add(fn); },
    };
    Object.defineProperty(globalThis, 'navigator', {value: media ? {mediaDevices: api} : {}, configurable: true, writable: true});
    fake.route = (way, id) => { fake.routes.push(way + ':' + id); };
    fake.routed = () => fake.routes.join(',');
    return fake;
}"""


class Bridge:
    """The runtime's camera: opens after *opening* polls, or fails with *fail*;
    a 4 x 2 picture, all red, a new frame every *every* reads."""

    def __init__(self, opening=2, fail=0, every=1):
        self.opening = opening
        self.fail = fail
        self.every = every
        self.reads = 0
        self.calls = []
        self.slept = 0

    def camera_open(self):
        self.calls.append("open")

    def camera_state(self):
        if self.fail:
            return self.fail
        if self.opening:
            self.opening -= 1
            return 0
        return 1

    def camera_close(self):
        self.calls.append("close")

    def camera_size(self):
        return (4, 2)

    def camera_readinto(self, buf, pic_w, pic_h, x, y, w, h, flags):
        self.reads += 1
        if self.reads % self.every:
            return 0
        self.calls.append("read %d,%d %d,%d %dx%d %d" % (pic_w, pic_h, x, y, w, h, flags))
        for row in range(y, y + h):
            for col in range(x, x + w):
                i = (row * pic_w + col) * 2
                buf[i], buf[i + 1] = 0x00, 0xF8
        return 1

    def camera_jpeg(self, quality, flags):
        self.calls.append("jpeg %d %d" % (quality, flags))
        return b"\xff\xd8jpeg"

    def sleep_ms(self, ms):
        self.slept += ms


def fresh(labels=True, media=True, has_camera=True):
    fake = js.eval(_FAKE)(labels, media)
    reg = endpointkit.Registry()
    reg.register(page_camera.Cameras(route=fake, has_camera=has_camera))
    return fake, reg


async def settle(reg, rounds=4):
    for _ in range(rounds):
        await asyncio.sleep(0.01)
        reg.poll()


def labels(reg):
    return [ep.label for ep in reg.endpoints("camera")]


@check
async def cameras_are_listed(air):
    fake, reg = fresh()
    await settle(reg)
    expect(labels(reg) == ["Browser's choice", "Integrated Camera", "USB Camera"], "cameras: %r" % labels(reg))


@check
async def unnamed_cameras_get_numbers(air):
    fake, reg = fresh(labels=False)
    await settle(reg)
    expect(labels(reg) == ["Browser's choice", "Camera 1", "Camera 2"], "cameras: %r" % labels(reg))


@check
async def choosing_a_camera_moves_the_page_there(air):
    fake, reg = fresh()
    await settle(reg)
    reg.select("camera", "page-camera:USB Camera")
    expect(fake.routed() == "camera:usb", "routes %s" % fake.routed())
    reg.select("camera", "page-camera:Integrated Camera")
    expect(fake.routed().endswith("camera:front"), "routes %s" % fake.routed())
    reg.select("camera", "page-camera:default")
    expect(fake.routed().endswith("camera:"), "back to the browser's choice: %s" % fake.routed())


@check
async def a_camera_plugged_in_later_appears(air):
    fake, reg = fresh()
    await settle(reg)
    fake.plug("cap", "Capture Card")
    await settle(reg)
    expect("Capture Card" in labels(reg), "cameras: %r" % labels(reg))
    fake.unplug("cap")
    await settle(reg)
    expect("Capture Card" not in labels(reg), "after unplugging: %r" % labels(reg))


@check
async def no_camera_runtime_lists_the_browsers_choice_and_says_why(air):
    fake, reg = fresh(has_camera=False)
    await settle(reg)
    eps = reg.endpoints("camera")
    expect([ep.label for ep in eps] == ["Browser's choice"], "cameras: %r" % labels(reg))
    expect("no camera" in eps[0].caps.get("why", ""), "why %r" % eps[0].caps.get("why"))


@check
async def the_camera_waits_to_open_then_reads_frames(air):
    bridge = Bridge(opening=3)
    cam = page_camera.Camera(format="anything", mirror=True, bridge=bridge)
    expect(bridge.slept > 0, "didn't wait for the browser")
    expect(cam.size() == (4, 2, 16), "size %r" % (cam.size(),))
    pic = bytearray(6 * 4 * 2)
    got = cam.capture_scaled(pic, 6, 4, x=1, y=1, w=2, h=2)
    expect(got == (2, 2), "wrote %r" % (got,))
    expect(bridge.calls[-1] == "read 6,4 1,1 2x2 2", bridge.calls[-1])
    expect(pic[(1 * 6 + 1) * 2 + 1] == 0xF8 and pic[1] == 0, "pixels %r" % bytes(pic))
    cam.capture_scaled(pic, 6, 4)  # 0 fills to the picture's edge
    expect(bridge.calls[-1] == "read 6,4 0,0 6x4 2", bridge.calls[-1])
    expect(cam.capture_jpeg(85) == b"\xff\xd8jpeg", "jpeg")
    cam.flip(True)
    cam.capture_jpeg(50)
    expect(bridge.calls[-1] == "jpeg 50 3", bridge.calls[-1])
    expect(cam.exposure(59) is None and cam.reg(0x3A18, 1) is None, "controls")
    cam.close()
    cam.close()
    expect(bridge.calls.count("close") == 1, "closed %r" % bridge.calls)


@check
async def no_new_frame_is_none_after_the_timeout(air):
    bridge = Bridge(opening=0, every=1000)
    cam = page_camera.Camera(bridge=bridge)
    expect(cam.capture_scaled(bytearray(8), 2, 2, timeout=20) is None, "a frame from nowhere")


@check
async def a_refused_camera_says_so(air):
    bridge = Bridge(fail=-1)
    try:
        page_camera.Camera(bridge=bridge)
    except OSError as e:
        expect("allow" in str(e), "said %s" % e)
        expect(bridge.calls == ["open", "close"], "calls %r" % bridge.calls)
    else:
        raise Failed("opened a refused camera")


@check
async def a_camera_never_answered_gives_up(air):
    bridge = Bridge(opening=10 ** 6)
    try:
        page_camera.Camera(bridge=bridge, timeout=200)
    except OSError as e:
        expect("didn't open" in str(e), "said %s" % e)
    else:
        raise Failed("opened a camera that never answered")
