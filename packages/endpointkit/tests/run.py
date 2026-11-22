# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""endpointkit's checks, runnable on MicroPython and CPython.

    python packages/endpointkit/tests/run.py           # from the repo root, or
    micropython packages/endpointkit/tests/run.py

pytest collects ``test_all`` from here too.
"""

import os
import sys

try:
    sys.path.insert(0, __file__.rsplit("/", 2)[0])
except (NameError, IndexError):
    pass
sys.path.insert(0, os.getcwd() + "/packages/endpointkit")

import endpointkit  # noqa: E402
from endpointkit import Registry  # noqa: E402
from endpointkit.fake import FakeProvider, bench  # noqa: E402

FAILS = []


def check(cond, what):
    if not cond:
        FAILS.append(what)
        print("FAIL", what)


def raises(exc, fn, *args, **kw):
    try:
        fn(*args, **kw)
    except exc as e:
        return e
    return None


def tmpfile(name):
    getenv = getattr(os, "getenv", lambda name: None)
    base = getenv("TMPDIR") or getenv("TEMP") or "/tmp"
    path = base + "/endpointkit-%s.json" % name
    try:
        os.remove(path)
    except OSError:
        pass
    return path


def ids(eps):
    return [ep.id for ep in eps]


def t_list_and_select():
    r = Registry()
    i2s = r.register(FakeProvider("audio.out", "i2s", [("0", "Jack")], ("i2s.0",)))
    usb = r.register(FakeProvider("audio.out", "uac", [("card", "USB card")], ("usb.host",)))
    check(ids(r.endpoints("audio.out")) == ["i2s:0", "uac:card"], "endpoints in provider order")
    check(r.find("uac:card").label == "USB card", "find by id")
    check(r.find("uac:nope") is None, "find unknown is None")
    r.select("audio.out", "i2s:0")
    check(i2s.started == ["0"], "select starts the endpoint")
    r.select("audio.out", ["i2s:0", "uac:card"])
    check(i2s.started == ["0"] and usb.started == ["card"], "audio.out fans out")
    r.select("audio.out", "uac:card")
    check(i2s.started == [] and usb.started == ["card"], "dropping one stops it")
    r.select("audio.out", None)
    check(usb.started == [] and r.selection("audio.out") == [], "None chooses nothing")


def t_one_kind():
    r = Registry()
    r.register(FakeProvider("camera", "csi", [("0", "A"), ("1", "B")]))
    check(raises(ValueError, r.select, "camera", ["csi:0", "csi:1"]) is not None, "ONE kind refuses two")
    check(raises(ValueError, r.select, "nokind", "x") is not None, "unknown kind refused")


def t_slow_and_waiting():
    r = Registry()
    bt = r.register(FakeProvider("audio.out", "a2dp", [("spk", "Speaker")], ("radio.bt",), delay=3))
    check(r.endpoints("audio.out") == [], "slow provider finds nothing at first")
    r.select("audio.out", "a2dp:spk")
    check(r.selection("audio.out") == ["a2dp:spk"] and bt.started == [], "a choice can wait for its endpoint")
    check(r.selected("audio.out") == [], "selected lists only found endpoints")
    r.poll()
    r.poll()
    check(bt.started == [], "not started before found")
    check(r.poll() is True, "poll says something changed")
    check(bt.started == ["spk"], "started when found")
    check(r.poll() is False, "quiet poll")
    bt.remove("spk")
    r.poll()
    check(bt.started == [] and r.selection("audio.out") == ["a2dp:spk"], "unplug stops but keeps the choice")
    bt.add("spk", "Speaker")
    r.poll()
    check(bt.started == ["spk"], "replug starts again")


def t_store():
    path = tmpfile("store")
    r = Registry(path)
    p = r.register(FakeProvider("midi.in", "uart", [("1", "DIN")]))
    r.select("midi.in", ["uart:1", "ble:pad"])
    r2 = Registry()
    late = FakeProvider("midi.in", "ble", [("pad", "Pad")], delay=1)
    r2.register(late)
    r2.set_store(path)
    check(r2.chosen("midi.in") == ["uart:1", "ble:pad"], "choices come back from the store")
    r2.poll()
    check(late.started == ["pad"], "a restored choice starts when found")
    p2 = r2.register(FakeProvider("midi.in", "uart", [("1", "DIN")]))
    check(p2.started == ["1"], "a restored choice starts when its provider registers")
    with open(path, "w") as f:
        f.write("not json")
    check(Registry(path).chosen("midi.in") == [], "a broken store starts empty")
    os.remove(path)
    del p


def t_conflicts():
    r = Registry()
    bt = r.register(FakeProvider("audio.out", "a2dp", [("spk", "Speaker")], ("radio.bt",)))
    pan = r.register(FakeProvider("net", "btpan", [("phone", "Phone")], ("radio.bt",)))
    r.register(FakeProvider("net", "eth", [("0", "Ethernet")], ("eth.0",)))
    r.select("audio.out", "a2dp:spk")
    stops, shared = r.conflicts("net", "btpan:phone")
    check(ids(stops) == ["a2dp:spk"] and shared == ["radio.bt"], "conflicts names what stops")
    e = raises(endpointkit.Conflict, r.select, "net", "btpan:phone")
    check(e is not None and ids(e.stops) == ["a2dp:spk"], "select raises Conflict")
    check(r.selection("net") == [] and bt.started == ["spk"], "a refused choice changes nothing")
    r.select("net", "eth:0")
    check(r.conflicts("net", "eth:0") == ([], []), "no conflict with what it replaces")
    r.select("net", "btpan:phone", confirm=True)
    check(bt.started == [] and r.selection("audio.out") == [], "confirm stops the other")
    check(pan.started == ["phone"], "confirm starts the new one")
    two = r.register(FakeProvider("audio.out", "i2s", [("a", "A"), ("b", "B")], ("i2s.0",)))
    check(raises(endpointkit.Conflict, r.select, "audio.out", ["i2s:a", "i2s:b"]) is not None, "two of one choice sharing a bus")
    del two


def t_pins():
    r = Registry()
    p = r.register(FakeProvider("cast.target", "roku", [("tv", "TV"), ("den", "Den")]))
    r.select("cast.target", "roku:tv")
    r.pin("cast.target", "roku:den", "video")
    check(p.started == ["den"] and r.pinned("cast.target") == ("video", ["roku:den"]), "a pin wins")
    r.select("cast.target", "roku:tv")
    check(p.started == ["den"] and r.chosen("cast.target") == ["roku:tv"], "choosing under a pin saves but waits")
    r.unpin("video")
    check(p.started == ["tv"] and r.pinned("cast.target") is None, "unpin brings the choice back")


def t_subscriptions():
    r = Registry()
    seen = []

    def cb(event, kind):
        seen.append((event, kind))

    def bad(event, kind):
        raise RuntimeError("subscriber bug")

    r.subscribe(None, bad)
    r.subscribe("audio.out", cb)
    p = r.register(FakeProvider("audio.out", "i2s", [("0", "Jack")]))
    check(("endpoints", "audio.out") in seen, "hears endpoints")
    r.register(FakeProvider("camera", "csi", [("0", "Cam")]))
    check(not [s for s in seen if s[1] == "camera"], "hears only its kind")
    del seen[:]
    r.select("audio.out", "i2s:0")
    check(seen == [("selection", "audio.out")], "hears selection, after a failing subscriber")
    del seen[:]
    p.set_state("0", endpointkit.CONNECTED)
    r.poll()
    check(seen == [("state", "audio.out")], "hears state")
    r.unsubscribe(cb)
    del seen[:]
    r.select("audio.out", None)
    check(seen == [], "unsubscribe")


def t_errors():
    r = Registry()
    p = r.register(FakeProvider("audio.out", "uac", [("card", "Card")], fail=("card",)))
    seen = []
    r.subscribe("audio.out", lambda e, k: seen.append(e))
    r.select("audio.out", "uac:card")
    ep = r.find("uac:card")
    check(ep.error == "Card won't start", "a failed start is recorded")
    check("error" in seen, "subscribers hear the error")
    p.fail = []
    r.select("audio.out", "uac:card")
    check(ep.error is None and p.started == ["card"], "a retry clears the error")


def t_new_kinds_and_unregister():
    r = Registry()
    fakes = bench(r, delay=1)
    check(r.endpoints("espnow.peer") == [], "ESP-NOW peers arrive slowly")
    r.poll()
    check(ids(r.endpoints("espnow.peer")) == ["espnow:a", "espnow:b"], "a new kind with no core change")
    r.select("thread.net", "thread:home")
    check(fakes["thread"].started == ["home"], "Thread joins")
    check(raises(ValueError, endpointkit.add_kind, "thread.net", endpointkit.MANY) is not None, "a kind keeps its count")
    r.select("net", "eth:0")
    r.unregister(fakes["eth"])
    check(fakes["eth"].started == [] and r.endpoints("net")[0].id == "wlan:home", "unregister stops and forgets")
    check(r.selection("net") == ["eth:0"], "unregister keeps the choice")
    check(raises(ValueError, r.register, FakeProvider("net", "wlan")) is not None, "provider names are unique")


def t_module_registry():
    endpointkit.add_kind("test.kind")
    p = endpointkit.register(FakeProvider("test.kind", "modfake", [("x", "X")]))
    endpointkit.select("test.kind", "modfake:x")
    check(ids(endpointkit.registry.selected("test.kind")) == ["modfake:x"], "module functions use the device's registry")
    endpointkit.unregister(p)


def test_all():
    del FAILS[:]
    for name, fn in sorted(globals().items()):
        if name.startswith("t_"):
            fn()
    assert not FAILS, FAILS


if __name__ == "__main__":
    test_all()
    print("endpointkit: all checks passed on", sys.implementation.name)
