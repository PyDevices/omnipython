<img src="docs/images/hello.png" width="160" alt="A red rectangle above a green one and a blue one, on black">

# OmniPython

This repository is the part of OmniPython that talks to hardware: displays, touch,
audio, USB, Bluetooth LE, Wi-Fi and timers, with one board config per board
and the same program on MicroPython-compatible boards, CircuitPython-compatible
boards, a desktop, a browser and an Android phone.

```bash
pip install --pre omnipython-desktop
```

```python
import omip
omip.install("github:PyDevices/omnipython/board_configs/fbdisplay/esp32-p4-wifi6-touch-lcd-4b")
```

`omip` comes with OmniPython firmware. On other MicroPython firmware, run
`mip.install("github:PyDevices/omnipython/lib/omip.py")` once to put it on the board.

The first is for a desktop. The second installs one board's config on that
board, and OmniPython with it; [Install](docs/get-started/install.md) has every
board and channel.

```python
from board_config import display_drv

w, h = display_drv.width, display_drv.height
print("display:", w, "x", h)

display_drv.fill(0x0000)
display_drv.fill_rect(16, 16, w - 32, h // 2 - 24, 0xF800)
display_drv.fill_rect(16, h // 2 + 8, w // 2 - 24, h // 2 - 24, 0x07E0)
display_drv.fill_rect(w // 2 + 8, h // 2 + 8, w // 2 - 24, h // 2 - 24, 0x001F)
display_drv.show()
```

```text
display: 320 x 480
```

On a desktop that opens a window at the desktop config's 320 × 480 and draws
the picture at the top of this page. On a board it draws the same layout at
the size of its screen.

[Docs](https://github.com/PyDevices/omnipython/blob/main/docs/index.md) · [Examples](https://gallery.omnipython.org/pyscript/) · [Roadmap](ROADMAP.md)

OmniPython is made by [PyDevices](https://pydevices.com).
