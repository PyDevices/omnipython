# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""A finger move on a browser backend gives Motion(touch=True) as well as FINGERMOTION.

SDL does both, so drag code written against the mouse works on a touch screen.
"""

import importlib
import pathlib
import sys
import types
import unittest
from unittest import mock

_LIB = pathlib.Path(__file__).resolve().parent.parent / "lib"


class _Rect:
    left = top = 0


class _Canvas:
    def getBoundingClientRect(self):
        return _Rect()

    def setPointerCapture(self, _id):
        pass

    def focus(self):
        pass


class _Ev:
    def __init__(self, x, y, pointer_type="touch", pointer_id=3, buttons=1):
        self.clientX, self.clientY = x, y
        self.offsetX, self.offsetY = x, y
        self.pointerType, self.pointerId = pointer_type, pointer_id
        self.buttons, self.button = buttons, 0
        self.movementX = self.movementY = 0  # touch pointer events report none


class TestWebInputTouchMotion(unittest.TestCase):
    def setUp(self):
        js = types.ModuleType("js")
        js.navigator = None
        self._mods = mock.patch.dict(sys.modules, {"js": js})
        self._mods.start()
        self._path = mock.patch.object(sys, "path", [str(_LIB)] + sys.path)
        self._path.start()
        sys.modules.pop("displaydev._webinput", None)
        _webinput = importlib.import_module("displaydev._webinput")

        self.input = _webinput.WebInput()
        self.input.canvas = _Canvas()

    def tearDown(self):
        sys.modules.pop("displaydev._webinput", None)
        self._path.stop()
        self._mods.stop()

    def test_touch_drag_gives_motion_with_touch_flag_and_rel(self):
        import events

        self.input._on_pointer_down(_Ev(10, 20))
        self.input._on_pointer_move(_Ev(14, 27))
        self.input._on_pointer_up(_Ev(14, 27, buttons=0))
        got = self.input.read()
        self.assertEqual(
            [e.type for e in got],
            [
                events.FINGERDOWN,
                events.MOUSEBUTTONDOWN,
                events.FINGERMOTION,
                events.MOUSEMOTION,
                events.FINGERUP,
                events.MOUSEBUTTONUP,
            ],
        )
        motion = got[3]
        self.assertTrue(motion.touch)
        self.assertEqual(motion.pos, (14, 27))
        self.assertEqual(motion.rel, (4, 7))
        self.assertEqual(motion.buttons, (1, 0, 0))
        self.assertTrue(got[1].touch and got[5].touch)

    def test_mouse_motion_is_not_touch(self):
        import events

        self.input._on_pointer_move(_Ev(5, 6, pointer_type="mouse", pointer_id=0, buttons=0))
        (motion,) = self.input.read()
        self.assertEqual(motion.type, events.MOUSEMOTION)
        self.assertFalse(motion.touch)


class TestWasmTouchMotion(unittest.TestCase):
    def setUp(self):
        self._path = mock.patch.object(sys, "path", [str(_LIB)] + sys.path)
        self._path.start()
        self.bridge = types.ModuleType("_wasm_bridge")
        self.batch = []
        self.bridge.poll_events = lambda _id, _types: (list(self.batch), 0)
        self._mods = mock.patch.dict(sys.modules, {"_wasm_bridge": self.bridge})
        self._mods.start()
        sys.modules.pop("displaydev.wasmdisplay", None)

    def tearDown(self):
        sys.modules.pop("displaydev.wasmdisplay", None)
        self._mods.stop()
        self._path.stop()

    def test_finger_move_from_the_bridge_is_followed_by_touch_motion(self):
        import events
        from displaydev.wasmdisplay import WasmDevices

        dev = WasmDevices("display_canvas")
        # What the C bridge hands over for a touch: Finger records only.
        self.batch = [
            events.Finger(events.FINGERDOWN, (1, 1), 2, None),
            events.Button(events.MOUSEBUTTONDOWN, (1, 1), 1, True, None),
            events.Finger(events.FINGERMOTION, (4, 6), 2, None),
            events.Finger(events.FINGERUP, (4, 6), 2, None),
        ]
        out = dev.read()
        self.assertEqual(
            [e.type for e in out],
            [
                events.FINGERDOWN,
                events.MOUSEBUTTONDOWN,
                events.FINGERMOTION,
                events.MOUSEMOTION,
                events.FINGERUP,
            ],
        )
        motion = out[3]
        self.assertTrue(motion.touch)
        self.assertEqual((motion.pos, motion.rel, motion.buttons), ((4, 6), (3, 5), (1, 0, 0)))
        self.assertEqual(dev._finger_pos, {})

    def test_mouse_motion_gets_no_extra_event(self):
        import events
        from displaydev.wasmdisplay import WasmDevices

        dev = WasmDevices("display_canvas")
        self.batch = [events.Motion(events.MOUSEMOTION, (4, 6), (1, 1), (0, 0, 0), False, None)]
        self.assertEqual(len(dev.read()), 1)


if __name__ == "__main__":
    unittest.main()
