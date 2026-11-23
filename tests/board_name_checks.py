# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""``boarddev.name()``'s checks, runnable on CPython and unix MicroPython.

    python tests/board_name_checks.py           # from the repo root, or
    micropython tests/board_name_checks.py

A board's stores and IDs are fakes put in ``sys.modules`` (``esp32``,
``machine``, ``microcontroller``), so every store runs on a desktop. Prints
``OK`` at the end; any failed check raises.
"""

import os
import sys

try:
    _here = __file__
except NameError:  # pragma: no cover
    _here = sys.argv[0]
_sep = "\\" if "\\" in _here else "/"
_dir = _here.rsplit(_sep, 1)[0] if _sep in _here else "."
sys.path.insert(0, _dir + _sep + ".." + _sep + "lib")

import boarddev  # noqa: E402

_TMP = os.getenv("TMPDIR") or "/tmp"


def check(cond, what):
    if not cond:
        raise AssertionError(what)


def raises(fn, *args):
    try:
        fn(*args)
    except ValueError as e:
        return str(e)
    raise AssertionError("no ValueError for %r" % (args,))


def test_rules():
    for good in ("kitchen", "Kitchen-2", "a", "x" * 20, "omnipython-a1b2c3", "123"):
        boarddev.check_name(good)
    check("at most 20" in raises(boarddev.check_name, "x" * 21), "21 characters")
    check("empty" in raises(boarddev.check_name, ""), "empty")
    check("letters, digits and hyphens" in raises(boarddev.check_name, "kitchen speaker"), "a space")
    check("letters, digits and hyphens" in raises(boarddev.check_name, "my_board"), "an underscore")
    check("letters, digits and hyphens" in raises(boarddev.check_name, "board.local"), "a dot")
    check("hyphen" in raises(boarddev.check_name, "-board"), "leading hyphen")
    check("hyphen" in raises(boarddev.check_name, "board-"), "trailing hyphen")
    check("string" in raises(boarddev.check_name, 42), "not a string")
    # name() refuses before it saves anything.
    raises(boarddev.name, "kitchen speaker")


def test_desktop():
    """This interpreter is a desktop: the env store and the computer's name."""
    boarddev.name(None)
    computer = boarddev.name()
    check(computer, "a desktop has a name")
    check("." not in computer, "the domain is cut off: %r" % computer)
    boarddev.name("kitchen")
    check(boarddev.name() == "kitchen", "set, then read")
    check(boarddev.env_get("OMNIPYTHON_BOARD_NAME") == "kitchen", "kept in the environment variable")
    boarddev.name(None)
    check(boarddev.name() == computer, "None goes back to the computer's name")


def test_browser():
    first = boarddev._name_default("micropython", "webassembly")
    check(first.startswith("omnipython-") and len(first) == 17, "omnipython- and six hex digits: %r" % first)
    int(first[11:], 16)
    check(boarddev._name_default("cpython", "emscripten") == first, "the same name for the whole page load")
    check(boarddev._name_store("cpython", "emscripten") == "env", "a browser keeps a saved name in the environment")


class _NVS:
    blobs = {}

    def __init__(self, namespace):
        self.ns = namespace

    def get_blob(self, key, buf):
        data = _NVS.blobs.get((self.ns, key))
        if data is None:
            raise OSError(-0x1102)  # ESP_ERR_NVS_NOT_FOUND
        buf[: len(data)] = data
        return len(data)

    def set_blob(self, key, data):
        _NVS.blobs[(self.ns, key)] = bytes(data)

    def erase_key(self, key):
        if (self.ns, key) not in _NVS.blobs:
            raise OSError(-0x1102)
        del _NVS.blobs[(self.ns, key)]

    def commit(self):
        pass


class _Module:
    pass


def _fake(name, **attrs):
    m = _Module()
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m


def _unfake(*names):
    for n in names:
        sys.modules.pop(n, None)


def test_esp32():
    _fake("esp32", NVS=_NVS)
    _fake("machine", unique_id=lambda: b"\x24\x6f\x28\xa1\xb2\xc3")
    try:
        store = boarddev._name_store("micropython", "esp32")
        check(store == "nvs", "an ESP32 keeps it in NVS, not %r" % store)
        check(boarddev._name_read(store) is None, "nothing saved yet")
        check(boarddev._name_default("micropython", "esp32") == "omnipython-a1b2c3", "the unique ID's last three bytes")
        boarddev._name_write(store, "kitchen")
        check(_NVS.blobs[("omnipython", "board_name")] == b"kitchen", "namespace omnipython, key board_name")
        check(boarddev._name_read(store) == "kitchen", "read back")
        boarddev._name_write(store, None)
        check(boarddev._name_read(store) is None, "forgotten")
        boarddev._name_write(store, None)  # forgetting twice is fine
    finally:
        _unfake("esp32", "machine")


def test_other_ports():
    _fake("machine", unique_id=lambda: b"\xe6\x61\x41\x04\x03\x5a\x2b\x2c")
    saved = boarddev._name_file
    path = _TMP + "/omnipython-name-check.json"
    boarddev._name_file = lambda: path
    try:
        store = boarddev._name_store("micropython", "rp2")
        check(store == "file", "an rp2 keeps it in a file, not %r" % store)
        check(boarddev._name_default("micropython", "rp2") == "omnipython-5a2b2c", "the unique ID's last three bytes")
        boarddev._name_write(store, None)
        check(boarddev._name_read(store) is None, "nothing saved yet")
        boarddev._name_write(store, "garage")
        check(boarddev._name_read(store) == "garage", "read back")
        boarddev._name_write(store, None)
        check(boarddev._name_read(store) is None, "forgotten")
    finally:
        boarddev._name_file = saved
        _unfake("machine")
    check(saved().endswith("/omnipython.json"), "the file is omnipython.json")


def test_circuitpython():
    class _Cpu:
        uid = bytearray(b"\x01\x02\x03\x0a\x0b\x0c")

    _fake("microcontroller", cpu=_Cpu())
    try:
        check(boarddev._name_store("circuitpython", "Espressif") == "toml", "CircuitPython keeps it in settings.toml")
        check(boarddev._name_store("circuitpython", "linux") == "env", "CircuitPython's unix port has no drive: the environment")
        check(boarddev._name_default("circuitpython", "Espressif") == "omnipython-0a0b0c", "cpu.uid's last three bytes")
    finally:
        _unfake("microcontroller")
    path = _TMP + "/omnipython-settings-check.toml"
    with open(path, "w") as f:
        f.write('CIRCUITPY_WIFI_SSID = "home"\nOMNIPYTHON_BOARD_NAME = "old"\nCIRCUITPY_WEB_API_PORT = 80\n')
    boarddev._toml_write(path, "OMNIPYTHON_BOARD_NAME", "kitchen")
    with open(path) as f:
        text = f.read()
    check(text == 'CIRCUITPY_WIFI_SSID = "home"\nCIRCUITPY_WEB_API_PORT = 80\nOMNIPYTHON_BOARD_NAME = "kitchen"\n', "replaced: %r" % text)
    boarddev._toml_write(path, "OMNIPYTHON_BOARD_NAME", None)
    with open(path) as f:
        text = f.read()
    check(text == 'CIRCUITPY_WIFI_SSID = "home"\nCIRCUITPY_WEB_API_PORT = 80\n', "removed: %r" % text)
    os.remove(path)
    boarddev._toml_write(path, "OMNIPYTHON_BOARD_NAME", "fresh")
    with open(path) as f:
        check(f.read() == 'OMNIPYTHON_BOARD_NAME = "fresh"\n', "a new settings.toml")
    os.remove(path)


def main():
    test_rules()
    test_desktop()
    test_browser()
    test_esp32()
    test_other_ports()
    test_circuitpython()
    print("OK")


main()
