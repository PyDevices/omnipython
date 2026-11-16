# Desktop utility modules

Every non-debris library module placed directly under this directory is
automatically included in both the pip and MIP `pydevices-desktop` packages and
in [`pydevices-desktop.toml`](../pydevices-desktop.toml). Utilities do not publish as separate packages.

| Module | Role |
|---|---|
| [`mdns.py`](mdns.py) | CircuitPython's `mdns` API over python-zeroconf, which pydevices-desktop installs ([`requirements.txt`](requirements.txt)) |
| [`micropython.py`](micropython.py) | CPython compatibility shim for common MicroPython decorators and helpers |
| [`frame_recorder.py`](frame_recorder.py) | FFmpeg recording for desktop displays |
| [`jpegio.py`](jpegio.py) | JPEG encode and decode, MicroPython's `jpegio` API over Pillow; says how to install Pillow when it's missing |
| [`pngio.py`](pngio.py) | PNG encode and decode, MicroPython's `pngio` API over Pillow; says how to install Pillow when it's missing |
| [`svgio.py`](svgio.py) | SVG decode, MicroPython's `svgio` API. On a desktop [`_svgio_resvg.py`](_svgio_resvg.py) draws with resvg and Pillow, and says how to install them when they're missing; under Pyodide [`_svgio_canvas.py`](_svgio_canvas.py) draws with the browser's canvas and needs nothing installed. [`_svgio_compact.py`](_svgio_compact.py) reads the compact form for both |
| [`usdl2.py`](usdl2.py) | Pure-Python SDL2 FFI fallback |
| [`uwin32.py`](uwin32.py) | Pure-Python Win32 FFI fallback |

Firmware-frozen modules resolve before `lib` in the documented preferred
`MICROPYPATH`, so bundled fallbacks do not replace native firmware modules.
