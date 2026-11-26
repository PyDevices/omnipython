# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""The T-Watch S3's board config on CPython, its chips replaced by fakes.

The screen sleeps as one (the panel, its backlight's supply and the touch
controller), the system clock starts from the clock chip when that kept
time, and the accelerometer comes up with its step counter and gestures on.
"""

import importlib.util
from pathlib import Path
import sys
import time
import types
import unittest
from unittest import mock

_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))
import _env  # noqa: E402

BOARD = Path(_env.ROOT) / "board_configs" / "busdisplay" / "spi" / "t-watch-s3"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _PMU:
    def __init__(self):
        self.rails = {}

    def set_rail(self, name, millivolts=None, enable=True):
        self.rails[name] = enable


class _Chip:
    def __init__(self, lost):
        self.lost_power = lost

    def datetime(self):
        return (2026, 11, 26, 3, 14, 5, 9, 0)


class _Panel:
    def __init__(self, *args, **kw):
        self.calls = []

    def sleep_mode(self, value):
        self.calls.append(value)


class _Touch:
    def __init__(self, *args, **kw):
        self.power_mode = 0

    def read_points(self):
        return []


def _board(lost=False):
    """Import board_config with every chip a fake; returns it, the fake PMU
    and machine.RTC's mock."""
    pmu = _PMU()
    rtc = mock.MagicMock()
    peripherals = types.ModuleType("board_peripherals")
    peripherals._i2c_bus = lambda: object()
    peripherals.pmu = lambda: pmu
    peripherals.rtc = lambda: _Chip(lost)
    peripherals.PERIPHERALS = frozenset({"rtc"})
    peripherals.load_peripherals = lambda ns: None
    machine = types.ModuleType("machine")
    machine.I2C = mock.MagicMock()
    machine.Pin = mock.MagicMock()
    machine.RTC = mock.MagicMock(return_value=rtc)
    fakes = {
        "board_peripherals": peripherals,
        "machine": machine,
        "keys": mock.MagicMock(),
        "ft6x36": types.SimpleNamespace(FT6x36=_Touch),
        "keypad_gpio": mock.MagicMock(),
        "spibus": mock.MagicMock(),
        "st7789": types.SimpleNamespace(ST7789=_Panel),
        "axp2101": mock.MagicMock(),
    }
    # MicroPython's time functions, which CPython hasn't.
    t = {
        "sleep_ms": lambda ms: None,
        "ticks_ms": lambda: int(time.monotonic() * 1000),
        "ticks_diff": lambda a, b: a - b,
    }
    with mock.patch.dict(sys.modules, fakes), mock.patch.multiple(time, create=True, **t):
        board = _load(BOARD / "board_config.py", "twatch_board_config")
    return board, pmu, rtc


class ScreenSleepTests(unittest.TestCase):
    def test_sleep_takes_the_backlight_and_touch_with_the_panel(self):
        board, pmu, _ = _board()
        panel = board.display_drv
        t = {"sleep_ms": lambda ms: None, "ticks_ms": lambda: 10**6, "ticks_diff": lambda a, b: a - b}
        with mock.patch.multiple(time, create=True, **t):
            board.display_drv.sleep_mode(True)
            self.assertEqual(panel.calls, [True])
            self.assertFalse(pmu.rails["aldo2"])
            self.assertEqual(board.touch.power_mode, 1)
            board.display_drv.sleep_mode(False)
        self.assertEqual(panel.calls, [True, False])
        self.assertTrue(pmu.rails["aldo2"])
        self.assertEqual(board.touch.power_mode, 0)


class ClockTests(unittest.TestCase):
    def test_the_clock_starts_from_the_chip(self):
        _, _, rtc = _board(lost=False)
        rtc.datetime.assert_called_once_with((2026, 11, 26, 3, 14, 5, 9, 0))

    def test_a_chip_that_lost_power_is_not_believed(self):
        _, _, rtc = _board(lost=True)
        rtc.datetime.assert_not_called()


class AccelerometerTests(unittest.TestCase):
    def test_steps_and_gestures_come_up_with_the_role(self):
        bma = types.ModuleType("bma423")
        for name, value in (("STEP_COUNTER", 1), ("ACTIVITY", 2), ("WRIST_WEAR", 4), ("DOUBLE_TAP", 16),
                            ("INT_WRIST_WEAR", 8), ("INT_DOUBLE_TAP", 16)):
            setattr(bma, name, value)
        chip = mock.MagicMock()
        bma.BMA423 = mock.MagicMock(return_value=chip)
        with mock.patch.dict(sys.modules, {"bma423": bma, "axp2101": mock.MagicMock()}):
            bp = _load(BOARD / "board_peripherals.py", "twatch_board_peripherals")
            bp._i2c_bus = lambda: object()
            bp.pmu = lambda: _PMU()
            self.assertIs(bp.accelerometer(), chip)
        chip.load_features.assert_called_once_with()
        chip.enable_features.assert_called_once_with(1 | 2 | 4 | 16)
        chip.map_interrupts.assert_called_once_with(8 | 16)


if __name__ == "__main__":
    unittest.main()
