# pdwidgets

pdwidgets is a whole user-interface toolkit written in Python, with no C:
labels, buttons, sliders, lists, dialogs and layouts, built on OmniPython's
displaydev, boarddev, appdev and multimer. It shows that the core is a
foundation other UI frameworks can stand on, and it runs the same code on
MicroPython-compatible boards, CPython and in the browser. For an interface you
ship, [LVGL](https://docs.omnipython.org/en/latest/lvgl/) is the toolkit to reach for.

Click the button and drag the slider below. It runs in your browser, on
MicroPython compiled to WebAssembly.

````{raw} html
<div class="omnipython-live-demo">
  <div class="demo-editor-pane">
    <textarea class="code-editor">
import appdev
import pdwidgets as pd
from displaydev.auto import AutoDisplay

# Display, app and screen
display_drv = AutoDisplay(width=320, height=240, canvas_id=CANVAS_ID)
app = appdev.App(display_drv)
display = pd.Display(display_drv, app)
screen = pd.Screen(display, bg=0x18C3)

# Widgets
title = pd.Label(screen, value="pdwidgets live demo", align=pd.ALIGN.TOP_LEFT, x=16, y=16, bg=screen.bg)
status = pd.Label(screen, value="Waiting for a tap", align=pd.ALIGN.TOP_LEFT, x=16, y=45, bg=screen.bg)

count = 0
btn = pd.Button(screen, label="Tap me", align=pd.ALIGN.TOP_LEFT, x=16, y=80, w=130, h=38, radius=6, style="raised")

def on_tap(sender, event):
    global count
    count += 1
    status.value = f"Tapped {count} time{'s' if count != 1 else ''}"

btn.add_event_cb(pd.events.MOUSEBUTTONUP, on_tap)

slider = pd.Slider(screen, value=0.5, align=pd.ALIGN.TOP_LEFT, x=16, y=140, w=200, h=24)

print("Click Tap me on the canvas.")
    </textarea>
    <div class="demo-controls">
      <button class="run-btn" disabled>▶ Run</button>
      <button class="reset-btn">↺ Reset</button>
      <span class="demo-status">Initializing Python…</span>
    </div>
    <pre class="demo-output"></pre>
  </div>
  <div class="demo-canvas-pane">
    <canvas id="canvas_pdwidgets_index" width="320" height="240" tabindex="0"></canvas>
  </div>
</div>
````

[Install it](get-started/install.md), then run
[your first program](get-started/first-program.md). The
[guides](guides/lay-out-widgets.md) take one task each, the
docstrings in
[`lib/pdwidgets`](https://github.com/PyDevices/omnipython/tree/main/packages/pdwidgets/lib/pdwidgets)
document every widget and name, and
[How it works](how-it-works/index.md) explains the design.

```{toctree}
:hidden:
:caption: Get started

get-started/install
get-started/first-program
```

```{toctree}
:hidden:
:caption: Guides

guides/lay-out-widgets
guides/respond-to-input
guides/theme-an-app
guides/build-a-settings-screen
guides/build-a-calculator
guides/build-a-dashboard
```

```{toctree}
:hidden:
:caption: Reference

reference/index
widgets
events
platforms
```

```{toctree}
:hidden:
:caption: How it works

how-it-works/index
how-it-works/architecture
```

```{toctree}
:hidden:
:caption: Changelog

changelog
```
