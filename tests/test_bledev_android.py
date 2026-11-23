# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""bledev on Android without a phone: stand-ins for bleak, python-for-android's
``android.permissions`` and pyjnius, behaving as an Android 13 phone does where
it matters. The permission answer comes on another thread, as Android's
main thread gives it, so the checks prove the loop hears it.
"""

import asyncio
import sys
import threading
import types
import unittest

import _env  # noqa: F401  (puts lib/ on sys.path)


class _Phone:
    """The phone's answers: its API level, what it has granted, what it asked."""

    def __init__(self):
        self.reset()

    def reset(self, sdk=33, refuse=()):
        self.sdk = sdk
        self.refuse = set(refuse)
        self.granted = set()
        self.asked = []
        self.scans = []
        self.adverts = []


phone = _Phone()


def check_permission(name):
    return name in phone.granted


def request_permissions(names, callback):
    phone.asked.append(list(names))
    grants = [name not in phone.refuse for name in names]
    phone.granted.update(n for n, g in zip(names, grants) if g)
    threading.Thread(target=callback, args=(names, grants)).start()


class BleakError(Exception):
    pass


class BleakScanner:
    def __init__(self, callback, scanning_mode="active", **kwargs):
        phone.scans.append(scanning_mode)
        self._callback = callback

    async def start(self):
        for native, adv in phone.adverts:
            self._callback(native, adv)

    async def stop(self):
        pass


def _autoclass(name):
    assert name == "android.os.Build$VERSION", name
    return types.SimpleNamespace(SDK_INT=phone.sdk)


def _install():
    def module(name, **attrs):
        m = types.ModuleType(name)
        m.__dict__.update(attrs)
        sys.modules[name] = m

    module("bleak", BleakClient=object, BleakScanner=BleakScanner)
    module("bleak.exc", BleakError=BleakError)
    module("android")
    module("android.permissions", check_permission=check_permission, request_permissions=request_permissions)
    module("jnius", autoclass=_autoclass)


_NAMES = ("bleak", "bleak.exc", "android", "android.permissions", "jnius", "bledev.bleak")
_saved = {name: sys.modules.get(name) for name in _NAMES}
_install()
sys.modules.pop("bledev.bleak", None)
import bledev  # noqa: E402
import bledev.auto  # noqa: E402
import bledev.bleak as bb  # noqa: E402

bb._ANDROID = True


def _restore():
    for name, module in _saved.items():
        if module is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = module


async def _scan():
    ble = bb.BleakBLE()
    async with ble.scan(10):
        pass


async def _scan_results():
    ble = bb.BleakBLE()
    async with ble.scan(10) as scan:
        return [result async for result in scan]


class Permissions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _install()  # the android and jnius stand-ins, for the backend's first scan

    @classmethod
    def tearDownClass(cls):
        _restore()

    def setUp(self):
        bb._permitted = False

    def test_android_13_asks_for_scan_connect_and_location(self):
        phone.reset(sdk=33)
        asyncio.run(_scan())
        self.assertEqual(phone.asked, [[
            "android.permission.ACCESS_FINE_LOCATION",
            "android.permission.BLUETOOTH_SCAN",
            "android.permission.BLUETOOTH_CONNECT",
        ]])
        self.assertEqual(phone.scans, ["active"], "a passive scan on Android hears nothing of its own")

    def test_android_11_asks_only_for_location(self):
        phone.reset(sdk=30)
        asyncio.run(_scan())
        self.assertEqual(phone.asked, [["android.permission.ACCESS_FINE_LOCATION"]])

    def test_asked_once_and_not_again_once_granted(self):
        phone.reset(sdk=33)
        asyncio.run(_scan())
        asyncio.run(_scan())
        self.assertEqual(len(phone.asked), 1)
        bb._permitted = False  # a new process: granted already, so nothing to ask
        asyncio.run(_scan())
        self.assertEqual(len(phone.asked), 1)
        self.assertEqual(phone.scans, ["active"] * 3)

    def test_a_refusal_says_which_and_never_scans(self):
        phone.reset(sdk=33, refuse={"android.permission.BLUETOOTH_SCAN"})
        with self.assertRaises(bledev.BLEError) as caught:
            asyncio.run(_scan())
        self.assertIn("BLUETOOTH_SCAN", str(caught.exception))
        self.assertNotIn("CONNECT", str(caught.exception))
        self.assertEqual(phone.scans, [])


    def test_an_advert_with_no_service_list(self):
        # bleak's Android backend passes None, not [], when an advert lists no services.
        phone.reset(sdk=33)
        native = types.SimpleNamespace(address="AA:BB:CC:DD:EE:FF", name="tag")
        adv = types.SimpleNamespace(local_name="tag", rssi=-60, service_uuids=None,
                                    manufacturer_data={}, service_data={})
        phone.adverts = [(native, adv)]
        try:
            results = asyncio.run(_scan_results())
        finally:
            phone.adverts = []
        self.assertEqual(len(results), 1)
        self.assertEqual(list(results[0].services()), [])


class Auto(unittest.TestCase):
    def setUp(self):
        self._on_android = bledev.auto._on_android
        self._importable = bledev.auto._importable
        bledev.auto._on_android = lambda: True

    def tearDown(self):
        bledev.auto._on_android = self._on_android
        bledev.auto._importable = self._importable

    def test_android_with_bleak_gets_bleak(self):
        bledev.auto._importable = lambda name: name == "bleak"
        self.assertEqual(bledev.auto.backend_name(), "bleak")

    def test_android_without_bleak_says_what_the_app_needs(self):
        bledev.auto._importable = lambda name: False
        self.assertIsNone(bledev.auto.backend_name())
        with self.assertRaises(bledev.UnsupportedError) as caught:
            bledev.auto.adapter()
        self.assertIn("bleak recipe", str(caught.exception))


_restore()


if __name__ == "__main__":
    unittest.main()
