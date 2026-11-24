# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""``wifi_manager``: which networks it tries and in what order, setup mode's
way out, and a setup screen that an app switch has deleted.

The radio, the clock and the screen are fakes, so nothing here touches a
network. On a weak link a scan misses a known network about half the time
and a join fails once and then works, so the join order and the two rounds
are what keep a board on its network.
"""

import importlib
import json
import sys
import types
import unittest
from unittest import mock

import _env  # noqa: F401
import wifi_manager as wm
from fake_wlan import FakeWLAN
from fake_wlan import clock as _fake_clock
from fake_wlan import sleep_ms as _fake_sleep_ms
from fake_wlan import ticks_diff as _fake_ticks_diff
from fake_wlan import ticks_ms as _fake_ticks_ms

_clock = [0]


class FakeRadio:
    """``scan()`` returns *seen*; ``join()`` takes its result for each SSID
    from *script* (``None`` joins, a string is the reason it didn't), and
    fails with "network not found" once a script runs out."""

    def __init__(self, seen=None, script=None):
        self.seen = seen
        self.script = {k: list(v) for k, v in (script or {}).items()}
        self.joins = []
        self.scans = 0
        self.address = None
        self.ap = None

    def scan(self):
        self.scans += 1
        if self.seen is None:
            raise OSError("scan failed")
        return dict(self.seen)

    def join(self, ssid, password, timeout):
        self.joins.append(ssid)
        results = self.script.get(ssid) or ["network not found"]
        err = results.pop(0)
        if err is None:
            self.address = "10.0.0.5"
        return err

    def ip(self):
        return self.address

    def mac(self):
        return b"\x00\x11\x22\x33\x44\x55"

    def start_ap(self, ssid, password):
        self.ap = ssid
        return "192.168.4.1"

    def stop_ap(self):
        self.ap = None


class FakeUI:
    def __init__(self):
        self.shown = None
        self.statuses = []
        self.closed = False

    def show(self, ap_name, ap_pass, url):
        self.shown = (ap_name, url)

    def status(self, text, ok=False, error=False):
        self.statuses.append(text)

    def close(self):
        self.closed = True


def _net(ssid, hidden=False):
    return {"ssid": ssid, "password": "pw-" + ssid, "hidden": hidden}


class _Patched(unittest.TestCase):
    """Fakes in place of the stores, the clock and the sleep."""

    def setUp(self):
        self._saved = {
            name: getattr(wm, name)
            for name in ("_known", "_load", "_remember", "_sleep_ms", "_ticks_ms", "_ticks_diff", "_make_ui")
        }
        self.known = []
        self.stored = []  # what a join has worked with before
        self.remembered = []
        _clock[0] = 0
        self.sleeps = 0
        self.on_sleep = None
        wm._known = lambda module="secrets": list(self.known)
        wm._load = lambda: list(self.stored)
        wm._remember = lambda ssid, password, hidden=False: self.remembered.append(ssid)
        wm._ticks_ms = lambda: _clock[0]
        wm._ticks_diff = lambda a, b: a - b
        wm._sleep_ms = self._sleep
        wm._cancelled = False

    def tearDown(self):
        for name, value in self._saved.items():
            setattr(wm, name, value)
        wm._cancelled = False

    def _sleep(self, ms):
        _clock[0] += ms
        self.sleeps += 1
        if self.on_sleep is not None:
            self.on_sleep(self.sleeps)


class FakeSta:
    """An esp32 station: ``status()`` follows *timeline*, a list of
    ``(ms from connect, status)``, and it is connected from *up_at* on."""

    def __init__(self, timeline, up_at=None):
        self.timeline = timeline
        self.up_at = up_at
        self.t0 = None

    def disconnect(self):
        self.t0 = None

    def connect(self, ssid, password):
        self.t0 = _clock[0]

    def isconnected(self):
        return self.up_at is not None and _clock[0] - self.t0 >= self.up_at

    def ifconfig(self):
        return ("10.0.0.7", "255.255.255.0", "10.0.0.1", "10.0.0.1")

    def status(self):
        now = _clock[0] - self.t0
        return [st for at, st in self.timeline if at <= now][-1]


class FakeNet:
    STAT_WRONG_PASSWORD = 202
    STAT_NO_AP_FOUND = 201


class MPRadioJoinTest(_Patched):
    def _radio(self, sta):
        radio = wm._MPRadio.__new__(wm._MPRadio)
        radio._net = FakeNet
        radio.sta = sta
        return radio

    def test_a_join_that_reports_wrong_password_and_then_connects_is_not_given_up(self):
        # What the DEV-KIT does on its first join after a boot.
        sta = FakeSta([(0, 1001), (7400, 202)], up_at=11300)
        self.assertIsNone(self._radio(sta).join("home", "pw", 20))

    def test_a_wrong_password_that_holds_is_reported(self):
        sta = FakeSta([(0, 1001), (4000, 202)])
        self.assertEqual(self._radio(sta).join("home", "pw", 20), "wrong password")
        self.assertLess(_clock[0], 20000)

    def test_a_wrong_password_seen_late_is_still_wrong_at_the_timeout(self):
        sta = FakeSta([(0, 1001), (15000, 202)])
        self.assertEqual(self._radio(sta).join("home", "pw", 20), "wrong password")

    def test_no_access_point_is_reported(self):
        sta = FakeSta([(0, 1001), (3000, 201)])
        self.assertEqual(self._radio(sta).join("home", "pw", 20), "network not found")


class JoinKnownTest(_Patched):
    def test_in_range_first_strongest_first_then_the_rest(self):
        self.known = [_net("away"), _net("weak"), _net("strong")]
        radio = FakeRadio(seen={"weak": -78, "strong": -50, "other": -40})
        self.assertIsNone(wm._join_known(radio, 5))
        self.assertEqual(radio.joins, ["strong", "weak", "away"] * 2)

    def test_a_join_that_fails_once_works_in_the_second_round(self):
        self.known = [_net("home")]
        radio = FakeRadio(seen={"home": -78}, script={"home": ["wrong password", None]})
        self.assertEqual(wm._join_known(radio, 5), "10.0.0.5")
        self.assertEqual(radio.joins, ["home", "home"])
        self.assertEqual(self.remembered, ["home"])

    def test_a_network_the_scan_missed_is_still_tried(self):
        self.known = [_net("home")]
        radio = FakeRadio(seen={"neighbour": -60}, script={"home": [None]})
        self.assertEqual(wm._join_known(radio, 5), "10.0.0.5")
        self.assertEqual(radio.joins, ["home"])

    def test_a_failed_scan_tries_every_known_network(self):
        self.known = [_net("a"), _net("b")]
        radio = FakeRadio(seen=None, script={"b": [None]})
        self.assertEqual(wm._join_known(radio, 5), "10.0.0.5")
        self.assertEqual(radio.joins, ["a", "b"])

    def test_one_known_network_is_joined_without_a_scan(self):
        self.known = [_net("home")]
        radio = FakeRadio(seen={"home": -50}, script={"home": [None]})
        self.assertEqual(wm._join_known(radio, 5), "10.0.0.5")
        self.assertEqual(radio.scans, 0)
        self.assertEqual(radio.joins, ["home"])

    def test_one_known_network_out_of_range_is_tried_twice_without_a_scan(self):
        self.known = [_net("home")]
        radio = FakeRadio(seen={})
        self.assertIsNone(wm._join_known(radio, 5))
        self.assertEqual(radio.scans, 0)
        self.assertEqual(radio.joins, ["home", "home"])

    def test_several_known_networks_are_scanned_for(self):
        self.known = [_net("a"), _net("b")]
        radio = FakeRadio(seen={"b": -50}, script={"b": [None]})
        self.assertEqual(wm._join_known(radio, 5), "10.0.0.5")
        self.assertEqual(radio.scans, 1)
        self.assertEqual(radio.joins, ["b"])

    def test_nothing_known_tries_nothing(self):
        radio = FakeRadio(seen={"home": -50})
        self.assertIsNone(wm._join_known(radio, 5))
        self.assertEqual(radio.joins, [])


class RefusedTest(_Patched):
    """An access point that turns away a password it has taken before: after
    a reset that sent no deauthentication it can, for minutes."""

    def test_a_password_that_worked_before_is_tried_again_after_a_wait(self):
        self.known = self.stored = [_net("home")]
        radio = FakeRadio(seen={}, script={"home": ["wrong password"] * 3 + [None]})
        self.assertEqual(wm._join_known(radio, 5), "10.0.0.5")
        self.assertEqual(radio.joins, ["home"] * 4)
        self.assertGreaterEqual(_clock[0], wm._RETRY_FIRST_S * 1000)

    def test_the_other_known_networks_are_tried_in_each_retry(self):
        self.known = self.stored = [_net("extender"), _net("router")]
        radio = FakeRadio(
            seen={"extender": -40, "router": -60},
            script={"extender": ["wrong password"] * 3, "router": ["wrong password"] * 2 + [None]},
        )
        self.assertEqual(wm._join_known(radio, 5), "10.0.0.5")
        self.assertEqual(radio.joins, ["extender", "router"] * 3)
        self.assertEqual(self.remembered, ["router"])

    def test_it_gives_up_after_the_retry_time_and_says_so(self):
        self.known = self.stored = [_net("home")]
        radio = FakeRadio(seen={}, script={"home": ["wrong password"] * 50})
        with mock.patch("builtins.print") as out:
            self.assertIsNone(wm._join_known(radio, 5))
        self.assertLessEqual(_clock[0], wm.REFUSED_RETRY_S * 1000)
        self.assertGreater(len(radio.joins), 2)
        said = " ".join(str(a) for c in out.call_args_list for a in c.args)
        self.assertIn("still turned this board away", said)

    def test_a_password_that_never_worked_is_not_retried(self):
        self.known = [_net("home")]
        self.stored = [{"ssid": "home", "password": "old"}]
        radio = FakeRadio(seen={}, script={"home": ["wrong password"] * 5})
        self.assertIsNone(wm._join_known(radio, 5))
        self.assertEqual(radio.joins, ["home", "home"])
        self.assertEqual(_clock[0], 0)

    def test_a_network_that_isnt_there_is_not_waited_for(self):
        self.known = self.stored = [_net("home")]
        radio = FakeRadio(seen={})
        self.assertIsNone(wm._join_known(radio, 5))
        self.assertEqual(radio.joins, ["home", "home"])
        self.assertEqual(_clock[0], 0)

    def test_setup_modes_rescan_does_not_wait(self):
        self.known = self.stored = [_net("home")]
        radio = FakeRadio(seen={}, script={"home": ["wrong password"] * 5})
        self.assertIsNone(wm._join_known(radio, 5, retry_s=0))
        self.assertEqual(radio.joins, ["home", "home"])


class CircuitPythonJoinTest(_Patched):
    """CircuitPython's radio searches every channel for a network it can't see."""

    def _radio(self, outcomes):
        class Radio:
            def __init__(self):
                self.calls = []
                self.ipv4_address = None
                self.ap_info = types.SimpleNamespace(channel=6)

            def connect(self, ssid, password, channel=0, timeout=None):
                self.calls.append((ssid, channel))
                outcome = outcomes.pop(0)
                if outcome is not None:
                    raise ConnectionError(outcome)
                self.ipv4_address = "10.0.0.5"

        radio = wm._CPRadio.__new__(wm._CPRadio)
        radio.r = Radio()
        return radio

    def setUp(self):
        super().setUp()
        wm._channels.clear()

    def test_a_network_that_isnt_there_is_not_searched_for_twice(self):
        self.known = [_net("home")]
        radio = self._radio(["No network with that ssid", "No network with that ssid"])
        self.assertIsNone(wm._join_known(radio, 5))
        self.assertEqual(len(radio.r.calls), 1)

    def test_another_failure_still_gets_the_second_round(self):
        self.known = [_net("home")]
        radio = self._radio(["Authentication failure", None])
        self.assertEqual(wm._join_known(radio, 5), "10.0.0.5")
        self.assertEqual(len(radio.r.calls), 2)

    def test_the_next_join_starts_on_the_channel_that_worked(self):
        self.known = [_net("home")]
        radio = self._radio([None])
        self.assertEqual(wm._join_known(radio, 5), "10.0.0.5")
        self.assertEqual(radio.r.calls, [("home", 0)])
        again = self._radio([None])
        again.join("home", "pw", 5)
        self.assertEqual(again.r.calls, [("home", 6)])


_RADIO_AND_POWER = ("bluetooth", "btclassic", "_bleio", "board_peripherals")


class ConnectLinkTest(unittest.TestCase):
    """``connect()`` on an esp32-shaped station: an address without a link is
    not a connection, so a static address joins at boot and rejoins after a
    drop, and a join that is still waiting for ``isconnected()`` is waited out."""

    def setUp(self):
        self._saved = {
            name: getattr(wm, name)
            for name in ("_load", "_save", "_settings", "_write_record", "_sleep_ms", "_ticks_ms", "_ticks_diff")
        }
        _fake_clock[0] = 0
        self.stored = []
        self.settings = {}
        wm._load = lambda: list(self.stored)
        wm._save = lambda nets: self.stored.__init__(nets) or True
        wm._settings = lambda: dict(self.settings)

        def write_record(nets, settings):
            self.settings.clear()
            self.settings.update(settings)
            return True

        wm._write_record = write_record
        wm._sleep_ms = _fake_sleep_ms
        wm._ticks_ms = _fake_ticks_ms
        wm._ticks_diff = _fake_ticks_diff
        self.ntp_calls = 0

        def settime():
            self.ntp_calls += 1

        secrets = types.ModuleType("_wm_test_secrets")
        secrets.WIFI_SSID = "bench"
        secrets.WIFI_PASSWORD = "pw"
        ntp = types.ModuleType("ntptime")
        ntp.settime = settime
        self._modules = {"_wm_test_secrets": secrets, "ntptime": ntp}
        self._before = {
            name: sys.modules.get(name)
            for name in ("network", "secrets", "wifi", *_RADIO_AND_POWER, *self._modules)
        }
        # Other tests leave fakes of these behind; here each test brings its
        # own, and None makes the rest fail to import, as on a bare board.
        for name in _RADIO_AND_POWER:
            sys.modules[name] = None
        sys.modules.update(self._modules)
        sys.modules["secrets"] = types.ModuleType("secrets")  # no network of its own

    def tearDown(self):
        for name, value in self._saved.items():
            setattr(wm, name, value)
        for name, value in self._before.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value

    def _connect(self, wlan, **kwargs):
        net = types.ModuleType("network")
        net.STA_IF = 0
        net.AP_IF = 1
        net.WLAN = lambda _if: wlan
        net.PM_NONE, net.PM_PERFORMANCE, net.PM_POWERSAVE = 0, 1, 2
        net.hostname = lambda name=None: None
        sys.modules["network"] = net
        # The MicroPython wifi shim binds the station it finds at import, and
        # wants MicroPython's time functions.
        sys.modules.pop("wifi", None)
        real_time = sys.modules["time"]
        fake_time = types.ModuleType("time")
        fake_time.sleep_ms = _fake_sleep_ms
        fake_time.ticks_ms = _fake_ticks_ms
        fake_time.ticks_diff = _fake_ticks_diff
        sys.modules["time"] = fake_time
        try:
            importlib.import_module("wifi")
        finally:
            sys.modules["time"] = real_time
        kwargs.setdefault("module", "_wm_test_secrets")
        kwargs.setdefault("setup", False)
        return wm.connect(**kwargs)

    def test_static_address_without_link_connects(self):
        wlan = FakeWLAN()
        wlan.ifconfig(("10.0.0.42", "255.255.255.0", "10.0.0.1", "10.0.0.1"))
        self.assertEqual(self._connect(wlan), "10.0.0.42")
        self.assertEqual(wlan.connects, ["bench"])
        self.assertTrue(wlan.linked)

    def test_static_address_rejoins_after_drop(self):
        wlan = FakeWLAN()
        wlan.ifconfig(("10.0.0.42", "255.255.255.0", "10.0.0.1", "10.0.0.1"))
        self.assertEqual(self._connect(wlan), "10.0.0.42")
        wlan.drop()
        self.assertEqual(wlan.ifconfig()[0], "10.0.0.42")
        self.assertEqual(self._connect(wlan), "10.0.0.42")
        self.assertEqual(len(wlan.connects), 2)
        self.assertTrue(wlan.linked)

    def test_dhcp_connect_waits_out_isconnected_lag(self):
        wlan = FakeWLAN()
        wlan.lag_ms = 800
        self.assertEqual(self._connect(wlan), "10.0.0.77")
        self.assertEqual(wlan.connects, ["bench"])

    def test_dhcp_rejoins_after_drop(self):
        wlan = FakeWLAN()
        self.assertEqual(self._connect(wlan), "10.0.0.77")
        wlan.drop()
        self.assertEqual(self._connect(wlan), "10.0.0.77")
        self.assertEqual(len(wlan.connects), 2)

    def test_port_without_isconnected_falls_back_to_address(self):
        wlan = FakeWLAN(ip="10.0.0.77", linked=True, has_isconnected=False)
        self.assertEqual(self._connect(wlan), "10.0.0.77")
        self.assertEqual(wlan.connects, [])

    def test_a_live_link_is_left_alone_and_the_clock_too(self):
        wlan = FakeWLAN(ip="10.0.0.77", linked=True)
        self.assertEqual(self._connect(wlan, ntp=True), "10.0.0.77")
        self.assertEqual(wlan.connects, [])
        self.assertEqual(self.ntp_calls, 0)

    def test_no_link_ever_returns_none(self):
        wlan = FakeWLAN()
        wlan.ifconfig(("10.0.0.42", "255.255.255.0", "10.0.0.1", "10.0.0.1"))
        wlan.assoc_ms = 10**9
        self.assertIsNone(self._connect(wlan, ntp=True))
        self.assertEqual(wlan.connects, ["bench", "bench"])
        self.assertEqual(self.ntp_calls, 0)

    def test_the_clock_is_set_after_a_join_when_asked(self):
        self.assertEqual(self._connect(FakeWLAN(), ntp=True), "10.0.0.77")
        self.assertEqual(self.ntp_calls, 1)

    def _battery(self, voltage):
        bp = types.ModuleType("board_peripherals")
        bp.PERIPHERALS = frozenset({"battery"})
        bp.battery = lambda: types.SimpleNamespace(voltage=voltage)
        sys.modules["board_peripherals"] = bp

    def test_a_board_without_a_battery_keeps_its_radio_awake(self):
        wlan = FakeWLAN()
        self.assertEqual(self._connect(wlan), "10.0.0.77")
        self.assertEqual(wlan.pm, 0)

    def test_a_board_already_joined_is_kept_awake_too(self):
        wlan = FakeWLAN(ip="10.0.0.77", linked=True)
        self.assertEqual(self._connect(wlan), "10.0.0.77")
        self.assertEqual(wlan.pm, 0)

    def test_power_saving_is_set_only_when_it_changes(self):
        wlan = FakeWLAN(ip="10.0.0.77", linked=True)
        wlan.pm = 0
        self._connect(wlan)
        self.assertEqual(wlan.pm_sets, 0)

    def test_a_board_with_a_battery_saves_power(self):
        self._battery(3.9)
        wlan = FakeWLAN()
        wlan.pm = 0
        self._connect(wlan)
        self.assertEqual(wlan.pm, 1)

    def test_a_battery_role_with_no_battery_fitted_keeps_it_awake(self):
        self._battery(None)
        wlan = FakeWLAN()
        self._connect(wlan)
        self.assertEqual(wlan.pm, 0)

    def test_bluetooth_on_leaves_the_radio_to_sleep(self):
        ble = types.ModuleType("bluetooth")
        ble.BLE = lambda: types.SimpleNamespace(active=lambda: True)
        sys.modules["bluetooth"] = ble
        wlan = FakeWLAN()
        self.assertEqual(self._connect(wlan), "10.0.0.77")
        self.assertEqual((wlan.pm, wlan.pm_sets), (1, 0))

    def test_the_choice_is_remembered_and_beats_the_default(self):
        wlan = FakeWLAN()
        self._connect(wlan)  # the station the wifi shim binds
        wm.set_power_save(True)
        self.assertEqual(wlan.pm, 1)
        self.assertEqual(self.settings, {"power_save": True})
        self._connect(wlan)
        self.assertEqual(wlan.pm, 1)
        self._battery(3.9)
        wm.set_power_save(False)
        self._connect(wlan)
        self.assertEqual(wlan.pm, 0)
        wm.set_power_save(None)
        self.assertEqual(self.settings, {})
        self.assertTrue(wm.power_save())

    def test_the_clock_is_left_alone_by_default(self):
        self.assertEqual(self._connect(FakeWLAN()), "10.0.0.77")
        self.assertEqual(self.ntp_calls, 0)

    def test_a_failed_clock_set_still_returns_the_address(self):
        def refuse():
            raise OSError(113, "EHOSTUNREACH")

        sys.modules["ntptime"].settime = refuse
        self.assertEqual(self._connect(FakeWLAN(), ntp=True), "10.0.0.77")

    def test_wait_false_starts_the_join_and_returns_at_once(self):
        wlan = FakeWLAN()
        self.assertIsNone(self._connect(wlan, wait=False))
        self.assertEqual(wlan.connects, ["bench"])
        self.assertFalse(wlan.linked)
        self.assertEqual(_fake_clock[0], 0)
        # the link comes up on its own, and the next call sees it
        _fake_sleep_ms(2000)
        self.assertEqual(self._connect(wlan, wait=False), "10.0.0.77")
        self.assertEqual(wlan.connects, ["bench"])

    def test_wait_false_with_a_static_address_and_no_link_rejoins(self):
        wlan = FakeWLAN()
        wlan.ifconfig(("10.0.0.42", "255.255.255.0", "10.0.0.1", "10.0.0.1"))
        self.assertIsNone(self._connect(wlan, wait=False))
        self.assertEqual(wlan.connects, ["bench"])

    def test_wait_false_with_nothing_known_starts_nothing(self):
        wlan = FakeWLAN()
        self.assertIsNone(self._connect(wlan, wait=False, module="_wm_no_such_module"))
        self.assertEqual(wlan.connects, [])

    def test_a_remembered_network_is_tried_when_the_secrets_one_is_out_of_range(self):
        wlan = FakeWLAN()
        self.stored = [{"ssid": "kept", "password": "pw2"}]
        joined = []
        real_connect = wlan.connect

        def connect(ssid, password):
            joined.append(ssid)
            if ssid == "kept":
                real_connect(ssid, password)

        wlan.connect = connect
        self.assertEqual(self._connect(wlan), "10.0.0.77")
        self.assertEqual(joined, ["bench", "kept"])


class BoardNameTest(unittest.TestCase):
    """The board's name is its hostname and its setup access point's name."""

    def setUp(self):
        # The board's name itself is test_board_name's; here, what wifi_manager does with it.
        named = mock.patch.object(wm, "boarddev", types.SimpleNamespace(name=lambda: "kitchen"))
        named.start()
        self.addCleanup(named.stop)
        self.hostnames = []
        self._before = sys.modules.get("network")
        net = types.ModuleType("network")
        net.STA_IF = 0
        net.AP_IF = 1
        net.hostname = self.hostnames.append

        class Wlan:
            def active(self, *a):
                return True

            def isconnected(self):
                return True

            def ifconfig(self):
                return ("10.0.0.9", "255.255.255.0", "10.0.0.1", "10.0.0.1")

        net.WLAN = lambda _if: Wlan()
        sys.modules["network"] = net

    def tearDown(self):
        if self._before is None:
            sys.modules.pop("network", None)
        else:
            sys.modules["network"] = self._before

    def test_connect_makes_the_board_name_the_hostname(self):
        self.assertEqual(wm.connect(setup=False), "10.0.0.9")
        self.assertEqual(self.hostnames, ["kitchen"])

    def test_a_hostname_given_wins(self):
        wm.connect(setup=False, hostname="panel")
        self.assertEqual(self.hostnames, ["panel"])

    def test_run_makes_the_board_name_the_hostname(self):
        saved = wm._Setup
        wm._Setup = lambda *a, **k: types.SimpleNamespace(run=lambda: None)
        try:
            wm.run(display_drv=object())
        finally:
            wm._Setup = saved
        self.assertEqual(self.hostnames, ["kitchen"])

    def test_the_access_point_is_named_after_the_board(self):
        radio = FakeRadio(seen={})
        ui = FakeUI()
        saved = wm._make_ui, wm._sleep_ms
        wm._make_ui = lambda display_drv: ui
        wm._sleep_ms = lambda ms: wm.cancel()
        s = wm._Setup(radio, None, 5, rescan=False)
        for name in ("_open_sockets", "_close_sockets", "_serve_dns", "_serve_http"):
            setattr(s, name, lambda *a: None)
        try:
            s.run()
        finally:
            wm._make_ui, wm._sleep_ms = saved
            wm._cancelled = False
        self.assertEqual(ui.shown[0], "kitchen")


class SetupModeTest(_Patched):
    def _setup(self, radio, rescan):
        ui = FakeUI()
        wm._make_ui = lambda display_drv: ui
        s = wm._Setup(radio, None, 5, rescan=rescan)
        for name in ("_open_sockets", "_close_sockets", "_serve_dns", "_serve_http"):
            setattr(s, name, lambda *a: None)
        return s, ui

    def test_cancel_ends_setup_without_a_network(self):
        radio = FakeRadio(seen={})
        s, ui = self._setup(radio, rescan=True)
        self.on_sleep = lambda n: n == 3 and wm.cancel()
        self.assertIsNone(s.run())
        self.assertTrue(ui.closed)
        self.assertIsNone(radio.ap)

    def test_a_cancel_from_before_does_not_end_the_next_setup(self):
        wm.cancel()
        radio = FakeRadio(seen={})
        s, ui = self._setup(radio, rescan=True)

        def submit(n):
            if n == 2:
                s.pending = ("home", "pw", False)

        self.on_sleep = submit
        radio.script = {"home": [None]}
        self.assertEqual(s.run(), "10.0.0.5")

    def test_run_waits_for_a_new_network_instead_of_rejoining_a_known_one(self):
        self.known = [_net("home")]
        radio = FakeRadio(seen={"home": -50}, script={"home": [None]})
        s, ui = self._setup(radio, rescan=False)

        def tick(n):
            _clock[0] += (wm.RESCAN_S + 1) * 1000  # a rescan is due every loop
            if n == 5:
                wm.cancel()

        self.on_sleep = tick
        self.assertIsNone(s.run())
        self.assertEqual(radio.joins, [])

    def test_setup_from_connect_rejoins_a_known_network_that_comes_back(self):
        self.known = [_net("home")]
        radio = FakeRadio(seen={}, script={"home": [None]})
        s, ui = self._setup(radio, rescan=True)
        self.on_sleep = lambda n: _clock.__setitem__(0, _clock[0] + (wm.RESCAN_S + 1) * 1000)
        self.assertEqual(s.run(), "10.0.0.5")
        self.assertEqual(radio.joins, ["home"])

    def test_a_network_from_the_page_is_joined_and_remembered(self):
        radio = FakeRadio(seen={"home": -60}, script={"home": [None]})
        s, ui = self._setup(radio, rescan=True)
        s.pending = ("home", "pw", False)
        self.assertEqual(s.run(), "10.0.0.5")
        self.assertEqual(self.remembered, ["home"])
        self.assertTrue(ui.closed)


class _Deleted(Exception):
    pass


class FakeLv:
    def __init__(self, active, deleted=False):
        self.active = active
        self.deleted = deleted
        self.loaded = []

    def screen_active(self):
        if self.deleted:
            raise _Deleted("Referenced object was deleted!")
        return self.active

    def screen_load(self, scr):
        self.loaded.append(scr)

    def color_hex(self, c):
        return c


class FakeObj:
    def __init__(self, deleted=False):
        self.deleted = deleted
        self.deletes = 0
        self.text = None

    def delete(self):
        if self.deleted:
            raise _Deleted("Referenced object was deleted!")
        self.deletes += 1

    def set_style_text_color(self, color, part):
        if self.deleted:
            raise _Deleted("Referenced object was deleted!")

    def set_text(self, text):
        self.text = text


def _lv_ui(lv, scr, prev):
    ui = object.__new__(wm._LvUI)
    ui.lv, ui.scr, ui.prev, ui.status_lbl = lv, scr, prev, FakeObj()
    return ui


class LvglScreenTest(_Patched):
    def test_close_gives_the_screen_back_when_it_is_still_showing(self):
        scr, prev = FakeObj(), FakeObj()
        lv = FakeLv(active=scr)
        ui = _lv_ui(lv, scr, prev)
        ui.close()
        self.assertEqual(lv.loaded, [prev])
        self.assertEqual(scr.deletes, 1)
        self.assertIsNone(ui.scr)

    def test_close_leaves_another_apps_screen_alone(self):
        scr, prev, other = FakeObj(), FakeObj(), FakeObj()
        lv = FakeLv(active=other)
        ui = _lv_ui(lv, scr, prev)
        ui.close()
        self.assertEqual(lv.loaded, [])
        self.assertIsNone(ui.scr)

    def test_close_survives_screens_an_app_switch_deleted(self):
        scr, prev = FakeObj(deleted=True), FakeObj(deleted=True)
        ui = _lv_ui(FakeLv(active=None, deleted=True), scr, prev)
        ui.close()
        self.assertIsNone(ui.scr)

    def test_status_on_a_deleted_label_still_reaches_the_repl(self):
        ui = _lv_ui(FakeLv(active=None), FakeObj(), FakeObj())
        ui.status_lbl = FakeObj(deleted=True)
        ui.status("Joining home...")
        self.assertIsNone(ui.status_lbl)



class CacheFileTest(unittest.TestCase):
    """Where ports without esp32.NVS remember networks: a writable drive."""

    def test_an_stm32_board_keeps_networks_on_flash(self):
        # On an Arduino GIGA, / only holds the mounts and refuses writes.
        self.assertEqual(wm._cache_file("pyboard"), "/flash/wifi_networks.json")

    def test_other_ports_keep_networks_at_the_root(self):
        self.assertEqual(wm._cache_file("rp2"), "/wifi_networks.json")
        self.assertEqual(wm._cache_file("linux"), "/wifi_networks.json")


if __name__ == "__main__":
    unittest.main()


class SettingsStoreTest(unittest.TestCase):
    """The power saving choice rides in the networks' own store, in an entry
    with no ``ssid`` that versions before it pass over."""

    def setUp(self):
        import tempfile

        self._dir = tempfile.TemporaryDirectory()
        self._saved = wm.CACHE_FILE
        wm.CACHE_FILE = self._dir.name + "/wifi_networks.json"

    def tearDown(self):
        wm.CACHE_FILE = self._saved
        self._dir.cleanup()

    def test_networks_and_the_choice_are_kept_together(self):
        wm._save([{"ssid": "bench", "password": "pw"}])
        with mock.patch.object(wm, "_apply_power_save"):
            wm.set_power_save(False)
        wm._save([{"ssid": "attic", "password": "x"}, {"ssid": "bench", "password": "pw"}])
        self.assertEqual(wm.networks(), ["attic", "bench"])
        self.assertIs(wm.power_save(), False)
        with open(wm.CACHE_FILE) as f:
            entries = json.load(f)
        old_reader = [n for n in entries if isinstance(n, dict) and n.get("ssid")]
        self.assertEqual([n["ssid"] for n in old_reader], ["attic", "bench"])

    def test_forgetting_the_networks_keeps_the_choice(self):
        with mock.patch.object(wm, "_apply_power_save"):
            wm.set_power_save(True)
        wm.forget()
        self.assertEqual(wm.networks(), [])
        self.assertIs(wm.power_save(), True)

    def test_no_choice_saved_means_the_default(self):
        with mock.patch.object(wm, "_has_battery", return_value=False):
            self.assertIs(wm.power_save(), False)
        with mock.patch.object(wm, "_has_battery", return_value=True):
            self.assertIs(wm.power_save(), True)
