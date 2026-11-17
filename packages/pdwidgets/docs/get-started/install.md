# Install

pdwidgets is one pure-Python package. The pip package is called
`omnipython-pdwidgets`; you import `pdwidgets`. It draws through a display from
[OmniPython](https://github.com/PyDevices/omnipython/blob/main/docs/index.md), colors from
[palettes](https://docs.omnipython.org/en/latest/palettes/) and shapes from
[pygraphics](https://docs.omnipython.org/en/latest/pygraphics/), and pip installs all three
for you.

## On a desktop (CPython)

```bash
pip install omnipython-pdwidgets omnipython-desktop
```

`omnipython-desktop` supplies `board_config`, the module that opens a window and
gives the program its display. Leave it out if you bring your own board config.

The window comes from SDL2, which the desktop board config loads when it
starts. On Debian and Ubuntu, install it first:

```bash
sudo apt install libsdl2-2.0-0
```

On macOS use `brew install sdl2`. On a machine with no screen, such as CI, set
`SDL_VIDEODRIVER=dummy` and the program draws to memory. The [OmniPython docs](https://github.com/PyDevices/omnipython/blob/main/docs/index.md)
cover the other desktop setups under Install.

## On a MicroPython-compatible board

From the board's REPL, with the board online:

```python
import omip
for package in ("omnipython", "pygraphics", "palettes", "pdwidgets"):
    omip.install(package)
```

`omip` comes with OmniPython firmware. On other MicroPython firmware, run
`mip.install("github:PyDevices/omnipython/lib/omip.py")` once to put it on the board.

mip doesn't follow dependencies between these packages, so each is installed by
name. Your board also needs its board config, which says how its display and
touch are wired; installing it brings OmniPython with it. The
[OmniPython docs](https://github.com/PyDevices/omnipython/blob/main/docs/index.md) list
every board config.

The same lines work on the unix port of MicroPython. Pass `target="some/folder"`
to `mip.install` to choose where the files go.

## On a CircuitPython-compatible board

There is no `circup` or bundle route for pdwidgets. Its
[`manifest.py`](https://github.com/PyDevices/omnipython/blob/main/packages/pdwidgets/manifest.py)
isn't tied to one runtime, so a CircuitPython firmware build that freezes it
can carry pdwidgets, but no such build has been run. [Platforms](../platforms.md) says
what has been checked.

## In the browser

In PyScript or Pyodide, install the wheel with `micropip` and import it:

```python
import micropip
await micropip.install("omnipython-pdwidgets")

import pdwidgets as pd
```

micropip installs `omnipython`, `omnipython-pygraphics` and `omnipython-palettes`
from the wheel's metadata. The [browser examples](https://gallery.omnipython.org/pyscript/)
run widget apps this way.

## Frozen into firmware

Release firmware images don't include pdwidgets: add it with the `mip` lines
above, or build it in. A firmware build can freeze pdwidgets by including
[`manifest.py`](https://github.com/PyDevices/omnipython/blob/main/packages/pdwidgets/manifest.py)
from its own freeze manifest. With
[omnipython-builds](https://github.com/PyDevices/omnipython-builds),
that's `build.py --modules pdwidgets`.

[Your first program](first-program.md) checks the install.
