# omnipython-desktop

Desktop board and host-adapter bundle for non-MCU OmniPython applications.

Installed modules:
- board_config
- board_peripherals
- boarddev
- mdns (CircuitPython's `mdns` API over python-zeroconf)
- micropython (CPython compatibility shim)
- usdl2
- uwin32 (Windows CPython)

It depends on the full `omnipython` meta-package, which includes `appdev`, and
on python-zeroconf, which `mdns` runs on ([`utils/requirements.txt`](https://github.com/PyDevices/omnipython/blob/main/utils/requirements.txt)).

Source of truth:
- Fixed library modules come from [`board_configs/desktop/`](https://github.com/PyDevices/omnipython/tree/main/board_configs/desktop) and `drivers/`.
- Every non-debris library module under `utils/` is discovered automatically.
- [`omnipython-desktop.toml`](https://github.com/PyDevices/omnipython/blob/main/omnipython-desktop.toml) lists the same complete payload for PyScript.

This package is intended to provide a single pip-installable desktop config
bundle while core OmniPython libraries continue to come from OmniPython packages.

`board_config.py` ownership for packaged desktop installs lives here
(`omnipython-desktop`), analogous to the MIP desktop bundle in
[`board_configs/desktop`](https://github.com/PyDevices/omnipython/tree/main/board_configs/desktop).

## Install (TestPyPI)

Install and verification flows are centralized here:
[Install](../get-started/install.md)

Use the sections:
- "omnipython-desktop via pip"
- "Verify with .venv"
- "Verify without .venv (python.exe / pip.exe)"

`board_config` constructs `display_drv` and exports neutral host/input callables
via `displaydev.auto.AutoDisplay`; it does not create an event app. Lazy roles such as `audio_out` /
`pcm_in` still come from `board_peripherals` and allocate on first access.
Terminal-only apps can `import board_peripherals` without opening a window.
