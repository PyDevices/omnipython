# multimer

One `machine.Timer`-shaped `Timer`, one clock, and one dispatcher, on every
interpreter OmniPython runs on: CPython, MicroPython (boards, unix, windows,
wasm) and CircuitPython.

Canonical source: [omnipython/lib/multimer](https://github.com/PyDevices/omnipython/tree/main/lib/multimer).

For a complete program to start from, see [multimer_simpletest.py](https://github.com/PyDevices/omnipython/blob/main/examples/multimer_simpletest.py).

## Install

### CPython (PyPI)

```bash
pip install --pre omnipython
```

`omnipython` is one distribution covering the whole core `lib/` tree. MIP
ships the same set as one `omnipython` package.

### MicroPython (MIP)

```python
import omip

omip.install("omnipython")
```

`omip` comes with OmniPython firmware. On other MicroPython firmware, run
`mip.install("github:PyDevices/omnipython/lib/omip.py")` once to put it on the board.

## Quick start

```python
import multimer
from multimer import Timer

tim = Timer(-1)
tim.init(mode=Timer.PERIODIC, period=500, callback=lambda t: print("tick"))

multimer.sleep_ms(3000)      # or end the script and look at it from >>>
multimer.report()
```

Callbacks run on the main thread at a safe point on every host; the script
can end and the timers keep firing at the prompt. Importing `multimer`
touches nothing until the first timer is armed.

**Everything else — the wake sources per host, `hold()`, `schedule()`,
`keepalive`, `repl()` for hosts with no prompt, and the introspection — is in
[docs/guides/timers.md](https://github.com/PyDevices/omnipython/blob/main/docs/guides/timers.md).**

## Links

- [Documentation — multimer](https://github.com/PyDevices/omnipython/blob/main/docs/guides/timers.md)
- [Source](https://github.com/PyDevices/omnipython/tree/main/lib/multimer)
- [Issues](https://github.com/PyDevices/omnipython/issues)
- Related: `omnipython-pygraphics`, `omnipython-desktop`

## License

MIT — see [LICENSE](https://github.com/PyDevices/omnipython/blob/main/LICENSE).
