# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""Optional backend selection. Nothing in bledev imports this module.

    import bledev.auto
    ble = bledev.auto.adapter()

picks, in order: ``mpble`` where MicroPython's ``bluetooth`` module exists,
``cpble`` where CircuitPython's ``_bleio`` does, ``webble`` in a browser (PyScript, Pyodide, the Workbench simulator), and
on CPython with bleak installed (``pip install omnipython[ble]``): ``winrt``
on Windows and ``bluez`` on Linux, which serve as a peripheral and connect
as a central through bleak, and ``bleak`` itself elsewhere (macOS), central
only. ``backend="bleak"`` still gives the central-only adapter anywhere.
Android gets ``bleak`` too: an app built with python-for-android gets it from
its recipe, and bledev asks for the Bluetooth permissions at the first scan.
Pass ``backend="fake"`` (or set ``BLEDEV_BACKEND``) to force one; extra
keyword arguments go to the backend's constructor.

A host with none raises `bledev.UnsupportedError` saying what to install.
"""

import sys

try:
    import os
except ImportError:  # a port with no os module
    os = None

from . import UnsupportedError

#: backend name -> (module, class). Each module stands alone and never imports this one.
BACKENDS = {
    "mpble": ("bledev.mpble", "MPBLE"),
    "cpble": ("bledev.cpble", "CPBLE"),
    "bleak": ("bledev.bleak", "BleakBLE"),
    "winrt": ("bledev.winrt", "WinRTBLE"),
    "bluez": ("bledev.bluez", "BlueZBLE"),
    "webble": ("bledev.webble", "WebBLE"),
    "fake": ("bledev.fake", "FakeBLE"),
}


def _importable(name):
    try:
        __import__(name)
        return True
    except Exception:
        return False


def _in_browser():
    if sys.platform in ("emscripten", "webassembly"):
        return True
    return _importable("_wasm_bridge") or _importable("pyodide")


def _on_android():
    """An app built with python-for-android, or CPython's own Android build."""
    if sys.platform == "android":
        return True
    environ = getattr(os, "environ", None)  # MicroPython's os has none
    return environ is not None and environ.get("P4A_BOOTSTRAP") is not None


def backend_name():
    """The backend this host would get, or ``None`` if it has no BLE."""
    impl = getattr(sys, "implementation", None)
    impl = getattr(impl, "name", "")
    if impl in ("micropython", "circuitpython"):
        if _in_browser():
            return "webble"
        if _importable("bluetooth"):
            return "mpble"
        if _importable("_bleio"):
            return "cpble"
        return None
    if _on_android():
        return "bleak" if _importable("bleak") else None
    if _in_browser():
        return "webble"
    if _importable("bleak"):
        if sys.platform == "win32":
            return "winrt"
        if sys.platform.startswith("linux"):
            return "bluez"
        return "bleak"
    return None


def _env_backend():
    try:
        import os

        return os.getenv("BLEDEV_BACKEND")
    except Exception:
        return None


def adapter(backend=None, **kwargs):
    """Construct the adapter for this host (or for ``backend``)."""
    name = backend or _env_backend() or backend_name()
    if name is None and _on_android():
        raise UnsupportedError(
            "no BLE backend in this Android app: build it with python-for-android's "
            "bleak recipe and the BLUETOOTH_SCAN and BLUETOOTH_CONNECT permissions"
        )
    if name is None:
        raise UnsupportedError(
            "no BLE backend on this host: on CPython, pip install 'omnipython[ble]' "
            "for bleak; on MicroPython, use firmware built with bluetooth; on "
            "CircuitPython, a board with _bleio"
        )
    if name not in BACKENDS:
        raise UnsupportedError("unknown bledev backend {!r}; one of {}".format(name, sorted(BACKENDS)))
    module_name, class_name = BACKENDS[name]
    module = __import__(module_name, None, None, [class_name])
    return getattr(module, class_name)(**kwargs)
