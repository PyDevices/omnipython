# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""``lib/wifi.py`` against a fake ``network.WLAN`` on a fake clock.

Covers a static address (``ifconfig()`` set before ``connect()``) and the
deprecated ``connect_from_secrets()``, which hands over to
``wifi_manager.connect()``. How ``wifi_manager`` treats a static address
and a link is in ``test_wifi_manager.py``.
"""

import importlib
import sys
import types
import unittest

import _env  # noqa: F401
from fake_wlan import FakeWLAN, clock as _clock, sleep_ms as _sleep_ms, ticks_diff as _ticks_diff, ticks_ms as _ticks_ms

def _load(wlan):
    net = types.ModuleType("network")
    net.STA_IF = FakeWLAN.STA_IF
    net.WLAN = lambda _if: wlan
    fake_time = types.ModuleType("time")
    fake_time.sleep_ms = _sleep_ms
    fake_time.ticks_ms = _ticks_ms
    fake_time.ticks_diff = _ticks_diff
    # The deprecated connect_from_secrets() hands over to wifi_manager. The
    # real one sits beside wifi in lib/; this one records what it was asked.
    manager = types.ModuleType("wifi_manager")
    manager.calls = []
    manager.JOIN_TIMEOUT_S = 20

    def connect(**kwargs):
        manager.calls.append(kwargs)
        return "10.0.0.5"

    manager.connect = connect
    real_time = sys.modules["time"]
    sys.modules["wifi_manager"] = manager
    sys.modules["network"] = net
    sys.modules["time"] = fake_time
    try:
        sys.modules.pop("wifi", None)
        wifi = importlib.import_module("wifi")
    finally:
        sys.modules["time"] = real_time
    return wifi, manager


class ConnectFromSecretsTests(unittest.TestCase):
    """``connect_from_secrets()`` is ``wifi_manager.connect()`` with the old defaults."""

    def setUp(self):
        _clock[0] = 0

    def tearDown(self):
        for name in ("wifi", "network", "wifi_manager"):
            sys.modules.pop(name, None)

    def test_it_asks_wifi_manager_with_the_old_defaults(self):
        wifi, manager = _load(FakeWLAN())
        self.assertTrue(wifi.connect_from_secrets())
        self.assertEqual(
            manager.calls,
            [{"setup": False, "wait": True, "ntp": True, "module": "secrets", "timeout": 45}],
        )

    def test_its_arguments_pass_through(self):
        wifi, manager = _load(FakeWLAN())
        wifi.connect_from_secrets("mine", wait=False, ntp=False, timeout=9)
        self.assertEqual(
            manager.calls,
            [{"setup": False, "wait": False, "ntp": False, "module": "mine", "timeout": 9}],
        )


class StaticAddressTests(unittest.TestCase):
    """A board with a fixed address on one network can take one from DHCP
    on another, and go back to its own afterwards."""

    def setUp(self):
        _clock[0] = 0

    def tearDown(self):
        for name in ("wifi", "network", "wifi_manager"):
            sys.modules.pop(name, None)

    def test_a_fixed_address_reads_back(self):
        wlan = FakeWLAN()
        wlan.ifconfig(("10.0.0.42", "255.255.255.0", "10.0.0.1", "10.0.0.1"))
        wifi, _ = _load(wlan)
        self.assertEqual(wifi.radio.ipv4_static, ("10.0.0.42", "255.255.255.0", "10.0.0.1", "10.0.0.1"))

    def test_a_dhcp_board_has_no_fixed_address(self):
        wlan = FakeWLAN(ip="10.0.0.77", linked=True)
        wifi, _ = _load(wlan)
        self.assertIsNone(wifi.radio.ipv4_static)

    def test_start_dhcp_takes_an_address_from_the_new_network(self):
        wlan = FakeWLAN()
        wlan.ifconfig(("10.0.0.42", "255.255.255.0", "10.0.0.1", "10.0.0.1"))
        wifi, _ = _load(wlan)
        wifi.radio.start_dhcp()
        self.assertIsNone(wifi.radio.ipv4_static)
        wifi.radio.connect("garage", "pw")
        self.assertEqual(wifi.radio.ipv4_address, "10.0.0.77")
        # and it is safe to ask twice
        wifi.radio.start_dhcp()

    def test_a_port_without_ipconfig_uses_ifconfig(self):
        wlan = FakeWLAN()
        wlan.ifconfig(("10.0.0.42", "255.255.255.0", "10.0.0.1", "10.0.0.1"))
        ipconfig = FakeWLAN.ipconfig
        del FakeWLAN.ipconfig
        try:
            wifi, _ = _load(wlan)
            self.assertIsNone(wifi.radio.ipv4_static)  # it can't tell
            wifi.radio.start_dhcp()
            self.assertTrue(wlan.dhcp)
        finally:
            FakeWLAN.ipconfig = ipconfig


if __name__ == "__main__":
    unittest.main()
