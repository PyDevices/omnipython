# Run the tests

OmniPython's libraries run on CPython, MicroPython and CircuitPython, so the
tests do too. This page says how to run them on each, and what each run can and
can't tell you.

You need a checkout of
[omnipython](https://github.com/PyDevices/omnipython) for the library tests, and
a MicroPython or CircuitPython binary for the runs that use one.

## On CPython

The tests are Python's own `unittest`. From the repository root:

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m unittest discover -s tests -v
```

The two variables give SDL a dummy screen and sound card, so no window opens
and no sound plays. Don't run the audio tests while another program is playing
sound.

To run one file, name it with `-p`:

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m unittest discover -s tests -p test_events.py
```

Some tests need packages the library doesn't depend on: `zeroconf` for the
`mdns` network test, Pillow and `resvg-py` for `svgio`, `pyte` for `vtterm`.
Install them first for the full run.

## On MicroPython

Tests that run a program under MicroPython use the unix build. They look for the
binary in this order:

1. The `OMNIPYTHON_MICROPYTHON` environment variable.
2. `micropython` on your `PATH`.
3. `bin/micropython` in a folder above the checkout.

```bash
OMNIPYTHON_MICROPYTHON=/path/to/micropython \
  python -m unittest discover -s tests -p test_omip.py -k MicroPythonRun
```

With no binary, a test skips and prints `this check did NOT run on MicroPython`.
Set `OMNIPYTHON_REQUIRE_MICROPYTHON=1` and the skip becomes a failure, which is
what to use when a green run has to mean it ran. A passing CPython run says
little about a board: MicroPython has no `namedtuple._replace()`, and a
`bytearray` takes only step-1 slices. A test that runs the same check under
MicroPython is how a difference like that shows up before it reaches a board.

To build the unix binary, follow
[Build for a board](https://docs.omnipython.org/en/latest/firmware/guides/build-for-a-board.html),
with `--port unix`:

```bash
./build_mp.py --port unix --modules pygraphics
```

## On CircuitPython

CircuitPython's unix port runs the checks that exist for it the same way, with
`OMNIPYTHON_CIRCUITPYTHON`, `circuitpython` on your `PATH` or `bin/circuitpython`
in a folder above the checkout:

```bash
OMNIPYTHON_CIRCUITPYTHON=/path/to/circuitpython \
  python -m unittest discover -s tests -p test_omip.py -k CircuitPythonRun
```

Without a binary the test skips and says it did not run on CircuitPython.
[Build for CircuitPython](https://docs.omnipython.org/en/latest/firmware/guides/build-for-circuitpython.html)
builds one with `--interpreter circuitpython --port unix`.

## On a board

A unix build has no pins, screen or radio, so a board's config is checked on the
board. `tools/smoke/board_smoke.py` imports the board's `board_config`, draws on
the display, reads touch and builds each peripheral the config lists. Run it
for you with:

```bash
python tools/mark_tested.py esp32-s3-touch-lcd-4_3 -d ws://my-board.local \
  --hardware "Waveshare ESP32-S3-Touch-LCD-4.3, rev 2"
```

`-d` is anything `mcuctl` takes: a WebSocket address, a serial port such as
`COM5` or `/dev/ttyACM0`. When every check passes, it writes the run to the
board's `tested.json`, which [Tested boards](../boards/tested-boards.md) lists.
`--local` runs it on a desktop MicroPython instead. The scripts under
`tests/hardware/` are for people with the part attached: USB host devices, for
instance.

## Other repositories

Each repository has its own tests and says how to run them in its
`CONTRIBUTING.md`.

- **audiodsp** runs CPython tests and parity gates that play the same
  sources through CircuitPython and through this port, and diff the sound byte
  for byte. The gates that need built interpreters, and the pinned CircuitPython
  they compare against, are in
  [Running the parity gates](https://github.com/PyDevices/audiodsp/blob/main/docs/how-it-works/parity-gates.md).
  Run the tests for the module you changed: the whole suite takes a long time.
- **Firmware** (omnipython-builds) has unit tests for `build_mp.py` and its
  scripts, run with `PYTHONPATH=tests python3 -m unittest test_build_mp
  test_freeze_list -v`.
