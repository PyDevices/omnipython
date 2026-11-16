# displaydev

Cross-platform display drivers for MicroPython, CircuitPython, and CPython — `BusDisplay`, `SDLDisplay`, `PGDisplay`, `WinDisplay`, `PSDisplay`, `JNDisplay`, `FBDisplay`, and more behind one drawing API.

Canonical source: [omnipython/lib/displaydev](https://github.com/PyDevices/omnipython/tree/main/lib/displaydev).

For a complete program to start from, see [displaydev_simpletest.py](https://github.com/PyDevices/omnipython/blob/main/examples/displaydev_simpletest.py).

## Install

### CPython (TestPyPI)

This package is published as a pure-Python wheel to TestPyPI.

```bash
pip install \
  -i https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  omnipython
```

`omnipython` is one distribution covering the whole core `lib/` tree, so this
also installs `events`, `keys`, `appdev`, `multimer`, `audiodev`, and
`boarddev`. MIP ships the same set as one `omnipython` package.

Why both indexes: OmniPython wheels are on TestPyPI while some of their
dependencies are on PyPI only — [details](https://github.com/PyDevices/omnipython/blob/main/docs/guides/troubleshooting.md#pip-cannot-resolve-a-pydevices-distribution).

For desktop SDL, also install [`omnipython-desktop`](https://test.pypi.org/project/omnipython-desktop/) with the same two-index pattern (bundles `usdl2` and the desktop `board_config`). For PyGame, install `pygame-ce` from PyPI (`import pygame`).

### MicroPython (MIP)

```python
import omip

omip.install("omnipython")
```

`omip` comes with OmniPython firmware. On other MicroPython firmware, run
`mip.install("github:PyDevices/omnipython/lib/omip.py")` once to put it on the board.

## Quick start

Apps normally import a hardware-only `board_config` (from OmniPython / `omnipython-desktop`):

```python
from board_config import display_drv

display_drv.fill(0)
display_drv.fill_rect(10, 10, 40, 40, 0xF800)
display_drv.show()
```

Optional host auto-selection lives in `displaydev.auto` (never imported from the
package root); `AutoDisplay` picks `PSDisplay` on PyScript, `JNDisplay` on
Jupyter, and `WinDisplay`→`PGDisplay`→`SDLDisplay` on desktop. Explicit boards
import a backend directly. The choice is a lookup in the [`backends`](../backends.py) registry, which you can add to: see [Displays](../../docs/guides/displays.md#write-your-own-backend).

Install a board package for MCU pins, or the desktop bundle from OmniPython —
see [install workflows](https://github.com/PyDevices/omnipython/blob/main/docs/get-started/install.md).

**Backends, the input contract, rotation, scrolling, and the internals are in
[docs/guides/displays.md](https://github.com/PyDevices/omnipython/blob/main/docs/guides/displays.md).**

## What you get

- Unified `framebuf`-style drawing surface (`fill`, `fill_rect`, `blit_rect`, `show`, …)
- MCU (`BusDisplay`, `FBDisplay`) and host backends (SDL, PyGame, Jupyter, PyScript)
- `displaydev.auto.AutoDisplay` / `host_kind` for desktop-like host selection (board_config remains the app import surface)

Host backends use `events` and `keys` for event records and key codes, and
`appdev` when the application chooses that coordinator. All three arrive with
`omnipython` on pip; on MIP install them by name.

## Links

- [Documentation — Displays](https://github.com/PyDevices/omnipython/blob/main/docs/guides/displays.md)
- [Source](https://github.com/PyDevices/omnipython/tree/main/lib/displaydev)
- [Issues](https://github.com/PyDevices/omnipython/issues)
- Related: `omnipython-pygraphics`, `omnipython-desktop`

## License

MIT — see [LICENSE](https://github.com/PyDevices/omnipython/blob/main/LICENSE).
