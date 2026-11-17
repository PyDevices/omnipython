# Install

palettes is one pure-Python package with no dependencies, so every channel
installs the same files. The pip package is called `omnipython-palettes`; you
import `palettes`.

## On a desktop (CPython)

```bash
pip install omnipython-palettes
```

## On a MicroPython-compatible board

From the board's REPL, with the board online:

```python
import omip
omip.install("palettes")
```

`omip` comes with OmniPython firmware. On other MicroPython firmware, run
`mip.install("github:PyDevices/omnipython/lib/omip.py")` once to put it on the board.

The same two lines work on the unix port of MicroPython. Pass `target="some/folder"`
to `mip.install` to choose where the files go.

## On a CircuitPython-compatible board

Copy the `lib/palettes` folder from the
[repository](https://github.com/PyDevices/omnipython/tree/main/packages/palettes/lib/palettes)
into the `lib` folder of the `CIRCUITPY` drive.

## In the browser

In PyScript or Pyodide, install the wheel with `micropip` and import it:

```python
import micropip
await micropip.install("omnipython-palettes")

from palettes import get_palette
```

## Frozen into firmware

A firmware build can freeze palettes by including
[`manifest.py`](https://github.com/PyDevices/omnipython/blob/main/packages/palettes/manifest.py)
from its own freeze manifest. With
[omnipython-builds](https://github.com/PyDevices/omnipython-builds),
that's `build.py --modules palettes`.

[Your first program](first-program.md) checks the install.
