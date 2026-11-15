# Direct MicroPython WebAssembly

The direct browser runtime is a reproducible MicroPython v1.28.0 WebAssembly
variant. Its compiled `_wasm_bridge`
owns browser integration; Python never imports `js`, uses DOM proxies, or
receives browser objects.

The bridge provides:

- continuous RGB565 framebuffer painting through `requestAnimationFrame`;
- pointer, touch, pen, wheel, keyboard, gamepad, and focus input;
- Web Audio playback and capture with explicit permission state;
- one-shot and periodic browser timers with Python callback delivery; and
- Asyncify-backed Fetch used by frozen `requests` and `mip`.

The Python backends are `displaydev.wasmdisplay.WasmDisplay`,
`audiodev.wasm_audio`, and `multimer`'s `wasm` source. Their automatic selectors prefer
these providers only when `_wasm_bridge` imports successfully. The display
owns one RGB565 `bytearray`; the browser scans it each animation frame, so
there is no explicit present or double-buffer protocol.

[`bin/wasm.py`](https://github.com/PyDevices/pydevices/blob/main/bin/wasm.py) (and [`bin/pyscript.py`](https://github.com/PyDevices/pydevices/blob/main/bin/pyscript.py)) require `PyDevices.github.io`,
`gallery`, and `mip` checked out as siblings of this repository —
the host serves gallery content and MIP packages straight out of those
directories.

Run an application through the first-party gallery host with:

```bash
bin/wasm.py -m bouncing_balls
bin/wasm.py my_app.py
bin/wasm.py --no-open -m paint
```

The launcher only stages URL intent, serves those checkouts, prints the URL, and
opens a browser. Playwright is maintained as a separate test harness.

Microphone use requires the host page's Enable Microphone control, and the
backend raises a clear permission error until it has been used. Audio output
unlocks on the page's first click, tap or key press.

## Audio in the browser

A browser blocks sound until the person has used the page. Call `play()` as
usual: until the first click, tap or key press the output is locked, `play()`
returns and keeps the sample, and the first tick of `service()` after the
click starts it. The bridge turns audio on at that first gesture itself, so a
page needs no Enable Audio control and a program needs no retry of its own.

`AudioOut` does this for any transport that raises `audiodev.AudioLocked` from
`open()`, a `RuntimeError` that existing handlers still catch. Raw `pcm_out()`
output still raises it until the page is unlocked, since it has nothing to
keep.

Execution stays on the browser main thread; running the VM in a worker is
not part of this backend contract.
