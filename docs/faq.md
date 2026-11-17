# Questions

## About OmniPython

### What is OmniPython?

Python libraries and C modules for MicroPython, CircuitPython and CPython. A
program imports them and drives the same display, input and audio on a board, a
desktop, a browser tab or an Android phone. [The stack](stack.md) lists
everything you can import or run.

### Is it a fork of MicroPython or CircuitPython?

No. It's what you import on top of them. The firmware builds are MicroPython or
CircuitPython with OmniPython's modules compiled in, plus patches that fix
bugs, enable hardware or add a few APIs. Each patch is a file in the
[patches folder](https://github.com/PyDevices/omnipython-builds/tree/main/patches)
and you can read it there.

### Does my code really run unchanged everywhere?

Your app does. Each board brings a `board_config`, a short file that says what's
on the board, and that file is different for every board. The app asks the
[board contract](boards/board-contract.md) for a display or a speaker and never
names the hardware.

### Which Pythons and hosts does it run on?

- Microcontrollers: MicroPython and CircuitPython.
- A Linux computer: MicroPython, CircuitPython and CPython.
- Windows: MicroPython and CPython.
- A browser: MicroPython through WebAssembly, and CPython through PyScript.
- Android: CPython.
- macOS: CPython. Only the audio engine, audiodsp, has native macOS wheels so far.

The [desktop](guides/run-on-the-desktop.md),
[browser](guides/run-in-the-browser.md),
[PyScript](guides/run-in-pyscript.md) and
[Android](guides/run-on-android.md) guides each say what runs there.

### Which boards are tested?

The ones on [Tested boards](boards/tested-boards.md). Each has a record of when
it was flashed, on what firmware, what was checked and what was skipped. Board
configs for many more boards are in the untested index: they're there to use and
report back on, with no promise yet.

### Do I need your firmware?

For the pure-Python parts, no: install them with `mip` onto the MicroPython you
already run. A few USB packages are the exception and need the OmniPython
firmware too: [USB support](reference/usb-support.md) says which. The C modules,
such as the audio engine, the camera, USB host and H.264, are compiled into the
firmware. For those you flash an OmniPython build or
[build your own](https://docs.omnipython.org/en/latest/firmware/guides/build-for-a-board.html).

### What does it cost?

Nothing. The libraries are MIT licensed. A few third-party parts that ship with
them carry their own licenses, such as the MP3 and Ogg Vorbis decoders in
audiodsp, and each repository's `NOTICE` file lists them.

## OmniPython and its neighbours

### How does it relate to CircuitPython?

Where CircuitPython has an API, OmniPython uses its names and shapes, so code
moves between the two. [CircuitPython's APIs](reference/circuitpython-apis.md)
lists which ones run on MicroPython and CPython. The audio modules are ported
from CircuitPython and checked against CircuitPython's own output byte for byte.
Bugs found that way went back upstream, and seven of the fixes are merged in
CircuitPython.

### CircuitPython has its own camera and display drivers for the ESP32-P4. Why use OmniPython there?

If you only use CircuitPython, use what's built in. OmniPython is for running the
same program on MicroPython, CircuitPython and CPython, and it adds H.264
encoding on the P4's hardware encoder, the P4's pixel accelerator, TensorFlow
Lite and casting the screen to a TV.
[Modules](https://docs.omnipython.org/en/latest/firmware/reference/modules.html)
says which of them build on CircuitPython.

### How is this different from MicroPythonOS?

[MicroPythonOS](https://github.com/MicroPythonOS/MicroPythonOS) is an operating
system for microcontrollers like the ESP32. OmniPython isn't an OS: it's
libraries your own program imports, and that program runs on three Pythons, not
one.

### I need a driver for a sensor. Is it here?

Maybe. There are 70 driver packages, and the tested ones are the ones the
tested boards use. For breadth, start with micropython-lib and Adafruit's
CircuitPython bundle: on MicroPython `omip` installs from micropython-lib, and on
CircuitPython from Adafruit's bundle. [The stack](stack.md) lists the drivers
that are here.

### Can I use it on a Raspberry Pi's pins?

No. OmniPython has no layer for a single-board computer's GPIO, SPI or I2C pins,
so the board drivers don't reach them.

## Stability

### Will an update change how my project sounds?

The audio modules that CircuitPython also has are held to CircuitPython's
output, apart from the differences audiodsp lists. The instruments and effects
built on them have no CircuitPython reference, so their sound can change when a
model improves. If a sound matters, pin the release.
