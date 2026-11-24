# Board configs

Every OmniPython app needs a `board_config.py` that describes its display and
input hardware without selecting an application event system. This page lists
every board that has one, what each exposes, and how to pick or write one.

For the stable end-device role names (`touch`, `wlan`, …), lazy `PERIPHERALS`
discovery, and the touch duck-type, see **[Board peripherals](board-contract.md)**.

## What board_config.py provides

Typically:

- A `display_drv` object (BusDisplay, SDLDisplay, PGDisplay, FBDisplay, etc.)
- Neutral input callables when present: `host_read`, `touch_read`,
  `keypad_read`, `encoder_read`, and related options
- Raw input hardware where useful (`touch`, `keypad`, `encoder`, `joystick`)
- Optional setup (backlight pins, buses). On **MicroPython**, lazy extras move
  to `board_peripherals` under the [board peripherals contract](board-contract.md). On
  **CircuitPython**, `board_peripherals.py` is optional — the native `board`
  module covers most non-UI peripherals.

Configs live in
[`PyDevices/omnipython`](https://github.com/PyDevices/omnipython)
(`board_configs/`). Each MicroPython folder is a package named by the folder:
its `manifest.py` says what it installs, and requires the driver packages it
uses and `omnipython`, so one `mip.install` of the board brings everything. The
`package.json` beside it installs the same files from GitHub, and is written
from the manifest.

See the canonical commands and verification steps in
[Install](../get-started/install.md). To add a board or a driver, or to
mark one tested, see [CONTRIBUTING.md](https://github.com/PyDevices/omnipython/blob/main/CONTRIBUTING.md).

CircuitPython configs live under [`board_configs/cp/`](https://github.com/PyDevices/omnipython/tree/main/board_configs/cp) with the same bus layout and
directory names as MicroPython (no `cp_` prefix; a `board_peripherals.py` is
optional and only a few configs have one). They have no `manifest.py`, but each
folder has a `package.json`, written from what its files import, so one
`omip.install("github:PyDevices/omnipython/board_configs/cp/<folder>")` brings
the config, the drivers it uses and the Adafruit libraries it imports.
MicroPython configs stay at the top level of `board_configs/` (not under an
`mp/` folder).

## The CircuitPython console

CircuitPython shows its console on a board's built-in screen, and every
`print` scrolls and redraws it. On an 800x480 panel, 50 short lines took
about four seconds with the console on the screen and a quarter of a second
without it, and a program that streams sound or network frames loses
whatever arrives during the stall.

So a OmniPython config keeps the console off the screen. A config that paints
the screen shows its own group in place of the console, one that drives the
panel itself releases the firmware's display first, and any displaydev driver
takes the console off `board.DISPLAY` when it starts, if it's still there.
What you print still reaches the serial console and the web workflow. A
config of your own that makes a `framebufferio.FramebufferDisplay` sets that
display's `root_group` too, to its own group or to `None`.

A program that never imports `board_config` or makes a driver, such as a
headless app on a board with a screen, takes the console off itself:

```python
import board

board.DISPLAY.root_group = None
```

`displayio.release_displays()` takes the console off as well, but it also
releases the screen the firmware set up, so use it only when nothing will
draw. To put the console back on the screen, for instance while you debug a
board with no serial cable:

```python
import board
import displayio

board.DISPLAY.root_group = displayio.CIRCUITPYTHON_TERMINAL
```

## Picking a config

Match in priority order:

1. **Bus type** — SPI vs I80 (parallel)
2. **Display controller** — ILI9341, ST7789, GC9A01, …
3. **Touch controller** — FT6X36, XPT2046, …
4. **Microcontroller** — ESP32-S3, RP2040, …

An exact match for all four is rare; bus + display controller is usually enough to adapt.

## Installing a board's config

```python
import mip
mip.install(
    "github:PyDevices/omnipython/board_configs/<path>"
)
```

Replace `<path>` with a directory from the tables below (for example
`fbdisplay/esp32-p4-wifi6-touch-lcd-4b`). The board package brings its drivers
and `omnipython`; its `manifest.py` lists them.

## Every board

**Config** is a path under `board_configs/`, and a MicroPython tree: the ones with `board_peripherals`. **CP** says a CircuitPython twin exists under `cp/` at the same path; those are eager-UI only (`display_drv`, `app`, `touch`, `keypad`, `encoder`, `joystick`), and the native `board` module covers the rest. `display_drv`, `app` and `display_bus` are part of every board's surface and aren't repeated in **Eager UI**. A blank role column means the config doesn't list one, not that the board lacks the hardware. The [roles](board-contract.md) a lazy factory names may still raise `NotImplementedError` until its chip driver lands: the set is the contract, not a promise of completeness. `bt` (Classic) is listed only where a board is known to have it.

### SPI displays

| Board | Config | CP | Display and touch | Eager UI | Lazy `PERIPHERALS` |
|---|---|---|---|---|---|
| DIY ESP32 + ILI9341 + XPT2046 | `busdisplay/spi/diy_esp32_ili9341_xpt2046` |  |  |  |  |
| ESP32-WROVER-E ST7789 + joystick | `busdisplay/spi/esp32_wrover_e_st7789_joystick` |  |  | `joystick` | `wlan` |
| Adafruit FunHouse (no BLE on ESP32-S2) | `busdisplay/spi/funhouse` | yes |  | `touch`, `keypad` | `temperature`, `humidity`, `pressure`, `light`, `motion`, `pixels`, `audio_out`, `wlan` |
| Adafruit HalloWing M4 | `busdisplay/spi/hallowing_m4` | yes |  | — | `pixels`, `accelerometer`, `audio_out`, `i2c` |
| Ai-Thinker ESP32-Audio-Kit V2.2 + 2.8" ILI9341 IPS touch module | `busdisplay/spi/ili9341_esp32_audio_kit` |  |  |  |  |
| Adafruit QT Py ESP32 Pico + EyeSPI ILI9341 | `busdisplay/spi/ili9341_eyespi_qtpy_esp32` |  |  |  |  |
| Adafruit ESP32-S3 QT Py + EyeSPI ILI9341 | `busdisplay/spi/ili9341_eyespi_qtpy_esp32s3` |  |  |  |  |
| QT Py RP2040 + EyeSPI ILI9341 | `busdisplay/spi/ili9341_eyespi_qtpy_rp2040` |  |  |  |  |
| Pico + UNO-style shield | `busdisplay/spi/ili9341_pico_uno` |  |  |  |  |
| M5Stack CoreS3 (AW88298/ES7210/BMI270 wired; camera stub) | `busdisplay/spi/m5stack-cores3` |  |  | `touch` | `audio_out`, `pcm_out`, `pcm_in`, `audio_power`, `sdcard`, `camera`, `accelerometer`, `gyroscope`, `i2c`, `wlan`, `ble` |
| Adafruit Metro M7 + TFT shield 1947 | `busdisplay/spi/metro_m7_tft_touch_shield_1947` |  | 240×320, ILI9341 SPI (`spibus` SoftSPI or SPI0); touch FT6206 @ `0x38`; Onboard AirLift (NINA) | `touch` | `pixels`, `led`, `sdcard`, `radio`, `wlan`, `i2c` |
| ST NUCLEO-H743ZI2 + TFT shield 1947 | `busdisplay/spi/nucleo_h743zi2_tft_touch_shield_1947` |  | 240×320, ILI9341 SPI (`spibus` SPI1 / SoftSPI); touch FT6206 @ `0x38` | `touch` | `led`, `sdcard`, `ethernet` |
| ODROID-GO | `busdisplay/spi/odroid_go` |  |  | `joystick`, `keypad` | `battery`, `sdcard`, `audio_out`, `wlan` |
| Pico LCD 1.8" | `busdisplay/spi/pico-lcd-1.8` |  |  |  |  |
| Waveshare Pico-OLED-2.23 and Pico-Audio on a Pico | `busdisplay/spi/pico-oled-2.23-audio` |  | 128×32, SSD1305 SPI |  | `audio_out`, `pcm_out`, `audio_power` |
| 3.5" TFT FeatherWing (HX8357D) (host-dependent STEMMA) | `busdisplay/spi/pitft_hx8357_featherwing` | yes |  | `touch` | `i2c` |
| 3.5" TFT FeatherWing, HX8357D + STMPE610 on an Adafruit Feather ESP32 V2 | `busdisplay/spi/pitft_hx8357_featherwing_on_feather_esp32_v2` |  |  |  |  |
| PiTFT ILI9341 FeatherWing (host-dependent STEMMA) | `busdisplay/spi/pitft_ili9341_featherwing` | yes |  | `touch` | `i2c` |
| Adafruit PyBadge | `busdisplay/spi/pybadge` | yes |  | `keypad` | `pixels`, `accelerometer`, `audio_out`, `i2c` |
| Adafruit PyGamer | `busdisplay/spi/pygamer` | yes |  | `joystick`, `keypad` | `pixels`, `accelerometer`, `sdcard`, `battery`, `audio_out`, `i2c` |
| Adafruit PyPortal (AirLift as `radio`/`wlan`) | `busdisplay/spi/pyportal` | yes |  | `touch` | `sdcard`, `radio`, `audio_out`, `i2c`, `wlan` |
| Adafruit PyPortal Titano | `busdisplay/spi/pyportal_titano` | yes |  | `touch` | `sdcard`, `radio`, `audio_out`, `i2c`, `wlan` |
| Waveshare RP2040-Touch-LCD-1.28 | `busdisplay/spi/rp2040-touch-lcd-1.28` |  | 240×240 round, GC9A01A SPI (`spibus` / FourWire); touch CST816 (`cst8xx` / `cst816`) | `touch` | `accelerometer`, `gyroscope`, `battery` |
| GC9A01 round display on QT Py ESP32-S3 | `busdisplay/spi/seeed_gc9a01_on_qtpy_esp32s3` |  |  |  |  |
| GC9A01 on QT Py RP2040 | `busdisplay/spi/seeed_gc9a01_on_qtpy_rp2040` |  |  |  |  |
| Seeed Round Display for XIAO on a XIAO ESP32C5 | `busdisplay/spi/seeed_gc9a01_on_xiao_esp32c5` |  | 240×240 round, GC9A01 SPI (`spibus`); touch CHSC6X | `touch` | `sdcard`, `rtc`, `battery`, `led`, `boot_button`, `i2c`, `wlan`, `ble` |
| Seeed Round Display for XIAO (GC9A01, CHSC6X touch, microSD, PCF8563 clock) on a XIAO nRF52840, stock MicroPython | `busdisplay/spi/seeed_gc9a01_on_xiao_nrf52840` | yes |  |  |  |
| SSD1331 color OLED (MP) | `busdisplay/spi/ssd1331_096_oled` | yes |  |  |  |
| SSD1351 color OLED (MP) | `busdisplay/spi/ssd1351_128_oled` | yes |  |  |  |
| LILYGO T-Display-S3 Pro | `busdisplay/spi/t-display-s3-pro` |  |  | `touch` | `sdcard`, `battery`, `wlan`, `ble` |
| LILYGO T-Dongle-S3 | `busdisplay/spi/t-dongle-s3` |  |  | — | `pixels`, `wlan`, `ble` |
| LILYGO T-Embed | `busdisplay/spi/t-embed` |  | 170×320, ST7789 SPI (`spibus`); touch — (rotary); GPIO46 power | `encoder` | `pixels`, `audio_out`, `pcm_out`, `pcm_in`, `audio_power`, `audio_in_power`, `sdcard`, `battery`, `i2c`, `wlan`, `ble` |
| LILYGO T-QT Pro | `busdisplay/spi/t-qt-pro` |  |  | — | `battery`, `wlan`, `ble` |
| LILYGO T-Watch S3 | `busdisplay/spi/t-watch-s3` | yes | 240×240, ST7789 SPI (`spibus` / FourWire); touch FT6336 (`ft6x36`); AXP2101 rails | `touch`, `keypad` | `audio_out`, `pcm_out`, `pcm_in`, `audio_power`, `accelerometer`, `rtc`, `haptic`, `ir`, `lora`, `sleep`, `battery`, `boot_button`, `wlan`, `ble` |
| Wokwi ESP32-S3 + ILI9341 | `busdisplay/spi/wokwi_ili9341_esp32s3_no_touch` |  |  |  |  |
| Wokwi ESP32-S3 + ILI9341 + touch | `busdisplay/spi/wokwi_ili9341_ft6x36_esp32s3` |  |  |  |  |

### Parallel (I80) displays

| Board | Config | CP | Display and touch | Eager UI | Lazy `PERIPHERALS` |
|---|---|---|---|---|---|
| BPI-Centi-S3 | `busdisplay/i80/bpi-centi-s3` |  |  | `encoder` | `wlan`, `ble` |
| RP2040 + ILI9341 I80 | `busdisplay/i80/ili9341_i80_rp2040` |  |  |  |  |
| LILYGO T-Display-S3 | `busdisplay/i80/t-display-s3` | yes |  | — | `battery`, `wlan`, `ble` |
| LILYGO T-HMI | `busdisplay/i80/t-hmi` | yes | 240×320, ST7789 I80 (`i80bus`); touch XPT2046 SPI; GPIO14/10 power | `touch` | `sdcard`, `i2c`, `wlan`, `ble` |
| Teensy 4.1 + FlexIO ILI9341 (split layout; no onboard lazy extras) | `busdisplay/i80/teensy41_flexio_ili9341` |  |  | — | *(empty)* |
| WT32-SC01 Plus | `busdisplay/i80/wt32sc01-plus` | yes |  | `touch` | `sdcard`, `wlan`, `ble` |

### I2C OLEDs

| Board | Config | CP | Display and touch | Eager UI | Lazy `PERIPHERALS` |
|---|---|---|---|---|---|
| SH1106 OLED 128×64 on the STEMMA QT port of a QT Py ESP32 Pico with an Audio BFF (MP + `i2cbus`; audio and the Boot button from the BFF config) | `busdisplay/i2c/sh1106_oled_on_qtpy_esp32_pico_audio_bff` |  |  |  |  |
| SH1107 OLED 128×64 (MP + `i2cbus`) | `busdisplay/i2c/sh1107_oled_128x64` | yes |  |  |  |
| FeatherWing OLED 128×32 (MP + `i2cbus`) | `busdisplay/i2c/ssd1306_oled_featherwing` | yes |  |  |  |

### Framebuffer, RGB, DSI and HDMI displays

| Board | Config | CP | Display and touch | Eager UI | Lazy `PERIPHERALS` |
|---|---|---|---|---|---|
| Adafruit Feather RP2040 DVI (MP stub raises `NotImplementedError` (SRAM); CP POC under `cp/fbdisplay/adafruit_feather_rp2040_dvi_320x240`) | `fbdisplay/adafruit_feather_rp2040_dvi_320x240` |  |  | — | — |
| Metro RP2350 + Adafruit HSTX→DVI adapter | `fbdisplay/adafruit_metro_rp2350_hstx_640x480` |  |  |  |  |
| Arduino GIGA R1 WiFi + GIGA Display Shield | `fbdisplay/arduino-giga-display-shield` |  | 480×800 (800×480 in LVGL), ST7701S MIPI DSI (`mipidsi`, STM32H747 DSI host + LTDC); touch GT911 @ `0x5D` | `touch` | `audio_out`, `pcm_out`, `pcm_in`, `accelerometer`, `gyroscope`, `led`, `boot_button`, `usb_device`, `usb_midi`, `wlan` |
| Waveshare ESP32-P4-WIFI6-DEV-KIT + KeDei 5" DSI | `fbdisplay/esp32-p4-wifi6-dev-kit_kedei-5in-dsi` |  | 800×480, ICN6211 bridge, MIPI DSI (`mipidsi`, `non_burst`, `continuous_clock`); touch FocalTech (`ft6x36`) | `touch` | `audio_out`, `pcm_out`, `pcm_in`, `audio_power`, `i2c`, `sdcard`, `camera`, `ethernet`, `radio`, `wlan`, `ble`, `boot_button`, `usb_device` (from the `nodisplay/esp32-p4-wifi6-dev-kit` package) |
| Waveshare ESP32-P4-WIFI6-Touch-LCD-4B | `fbdisplay/esp32-p4-wifi6-touch-lcd-4b` |  | 720×720, ST7703 MIPI DSI (`mipidsi`); touch GT911 | `touch` | `audio_out`, `pcm_out`, `pcm_in`, `audio_power`, `audio_in_power`, `sdcard`, `camera`, `radio`, `wlan`, `ble`, `usb_device`, `boot_button` |
| Waveshare ESP32-S3-Touch-LCD-4.3 | `fbdisplay/esp32-s3-touch-lcd-4_3` | yes | 800×480, ST7262 RGB DotClock; touch GT911 @ `0x5D`; CH422G | `touch`, `io_expander` | `sdcard`, `can`, `rs485`, `usb_device`, `wlan`, `ble` |
| Waveshare ESP32-S3-Touch-LCD-7 | `fbdisplay/esp32-s3-touch-lcd-7` | yes | 800×480, ST7262 RGB DotClock; touch GT911 @ `0x5D`; CH422G | `touch`, `io_expander` | `sdcard`, `can`, `rs485`, `usb_device`, `wlan`, `ble` |
| Waveshare ESP32-S31-Touch-LCD-4.3C | `fbdisplay/esp32-s31-touch-lcd-4_3c` |  | 800×480 RGB DotClock; touch GT911 @ `0x5D` | `touch` | `audio_out`, `pcm_out`, `pcm_in`, `audio_power`, `audio_in_power`, `sdcard`, `accelerometer`, `gyroscope`, `rtc`, `battery`, `i2c`, `led`, `boot_button`, `can`, `rs485`, `wlan`, `ble` |
| Adafruit Feather RP2040 + RGB matrix wing (matrix is `display_drv`) | `fbdisplay/feather_rp2040_rgb_matrix_64x32` |  |  | — | `i2c` |
| M5Stack Tab5 (ILI9881C) (ES8388/ES7210 wired; camera stub) | `fbdisplay/m5stack_tab5_ili9881c` |  |  | `touch` | `audio_out`, `pcm_out`, `pcm_in`, `audio_power`, `sdcard`, `camera`, `i2c`, `wlan`, `ble` |
| M5Stack Tab5 (ST7123) (same) | `fbdisplay/m5stack_tab5_st7123` |  |  | `touch` | `audio_out`, `pcm_out`, `pcm_in`, `audio_power`, `sdcard`, `camera`, `i2c`, `wlan`, `ble` |
| Adafruit MatrixPortal M4 (HUB75 is `display_drv`) | `fbdisplay/matrixportal_m4_64x32` | yes |  | — | `accelerometer`, `i2c` |
| Adafruit MatrixPortal S3 | `fbdisplay/matrixportal_s3_64x64` | yes |  | — | `accelerometer`, `i2c`, `wlan`, `ble` |
| Olimex RP2350pc (onboard HDMI (HSTX); no adapter) | `fbdisplay/olimex_rp2350pc_640x480` |  |  | — | `sdcard`, `led`, `i2c` |
| Pico 2 + DVI Sock / PiCowbell HSTX (Sock and PiCowbell share GP12–19) | `fbdisplay/pico2_dvi_sock_640x480` |  |  | — | *(empty)* |
| Pico 2 W + DVI Sock / PiCowbell HSTX (same HSTX pins + CYW43) | `fbdisplay/pico2w_dvi_sock_640x480` |  |  | — | `wlan`, `ble` |
| Adafruit Qualia S3 + TL040HDS20 | `fbdisplay/qualia_tl040hds20` | yes | 720×720, RGB-666→565 DotClock; touch FT6x36 @ `0x48`; PCA9554 @ `0x3f` | `touch`, `keypad`, `io_expander` | `wlan`, `ble` |
| Teensy 4.1 + RGB matrix featherwing | `fbdisplay/rgb_matrix_featherwing_teensy41_64x32` |  |  | — | *(empty)* |
| SparkFun IoT RedBoard RP2350 + HSTX→DVI (needs FPC + SparkFun HSTX→DVI breakout) | `fbdisplay/sparkfun_iot_redboard_rp2350_hstx_640x480` |  |  | — | `sdcard`, `led`, `i2c`, `wlan`, `ble` |
| LILYGO T-RGB 2.1″ | `fbdisplay/t-rgb_480` |  | 480×480, ST7701 RGB DotClock; touch CST820 (`cst8xx`); XL9535 | `touch` | `sdcard`, `battery`, `wlan`, `ble` |

### Pixel and LED grids

| Board | Config | CP | Display and touch | Eager UI | Lazy `PERIPHERALS` |
|---|---|---|---|---|---|
| DotStar 12×6 grid (MicroPython) | `pixeldisplay/dotstar_12x6` | yes |  |  |  |
| NeoPixel 8×4 grid (MicroPython) | `pixeldisplay/neopixel_8x4` | yes |  |  |  |

### CircuitPython-only configs

| Board | Config |
|---|---|
| CircuitPython USB Video | `cp/fbdisplay/usb_video` |

### Headless boards

A board with no display has no `board_config.py`, because there's nothing to
construct up front; an app imports `board_peripherals` directly, and an app
that also runs with a display treats `board_config` as optional.

| Directory | Board |
|-----------|-------|
| `nodisplay/qtpy_esp32_pico_audio_bff` | QT Py ESP32 Pico + Adafruit Audio BFF (MicroPython; `audio_out` on I2S, `boot_button`) |
| `nodisplay/esp32-s31-zero` | Waveshare ESP32-S31-Zero (MicroPython; `pixels`, `boot_button`, `wlan`, `ble`) |
| `cp/nodisplay/qtpy_esp32_pico_audio_bff` | the same, on CircuitPython (`audio_out` is `audiobusio.I2SOut`) |

### Desktop and browser

| Directory | Platform |
|-----------|----------|
| `sdldisplay` | CPython / MicroPython Unix — SDL2 (`SDLDisplay`) |
| `sdldisplay/linux_kms` | Linux KMS/DRM (no X11/Wayland) — `SDL_VIDEODRIVER=kmsdrm` |
| `pgdisplay` | CPython — PyGame (`PGDisplay`) |
| `windisplay` | Windows CPython — native Win32 (`WinDisplay` + `audiodev.win_audio`) |
| `jndisplay` | Jupyter Notebook |
| `psdisplay` | PyScript browser |


## Notes on particular boards

What to know before you flash and wire one of these. The
[Arduino GIGA R1 WiFi with the Display Shield](arduino-giga-display-shield.md)
has its own page. Native display drivers come with
[omnipython-builds](https://github.com/PyDevices/omnipython-builds/tree/main/modules/displayif)'
`displayif` module.

**The ESP32-S3 RGB boards** (Qualia S3, the Waveshare 4.3 and 7 inch, T-RGB)
run on `ESP32_GENERIC_S3` with `SPIRAM_OCT`: eight megabytes of octal PSRAM.
The two Waveshare boards have two USB ports: flash and use the REPL on the
UART port (CH343), because the native port may not show a serial port until the
firmware is up. The 4.3 inch panel runs at a 14 MHz pixel clock, because Wi-Fi
falls over beside the panel at 16. The 4.3 inch board's touch needs its axes
reflected over the diagonal, which its config already does; the 7 inch
board's doesn't. For CircuitPython, use firmware built from the board's own
definition (`waveshare_esp32s3_touch_lcd_43` or `_7`): it wakes the panel
at boot and hands it over as `board.DISPLAY`.

**Qualia S3 with the TL040HDS20** needs BGR 5/6/5 data-pin order and the
PCA9554 expander at `0x3f`. On MicroPython the panel uses two framebuffers and
`auto_refresh=False`, because LVGL paints the panel directly; the CircuitPython
config paints a separate bitmap, so `auto_refresh=True` is right there.

**T-RGB 2.1 inch** uses its native USB: hold BOOT and press RESET to reach the
ROM bootloader, then press RESET again after flashing for a clean serial port.

**T-Embed** is the same: BOOT plus RESET to flash `ESP32_GENERIC_S3` with
`SPIRAM_OCT`, then RESET. The config passes explicit SPI pins on purpose,
because `SPI(2)`'s defaults land on the octal PSRAM pads. Don't leave a Python
`/lib/spibus.py` on the board: it shadows the firmware's native `spibus`.

**T-HMI** drives its panel over an 8-bit parallel bus with the native `i80bus`;
don't install a Python bus fallback. Its resistive touch wants firm presses.
A thin noisy line left after a geometry test is usually stale display memory:
`display_drv.fill(0)` clears it.

**Waveshare RP2040-Touch-LCD-1.28** enters the ROM UF2 bootloader (`RPI-RP2`);
the Adafruit TinyUF2 doesn't ship for RP2040. The SPI runs at 10 MHz (60 MHz
was unreliable on a cold boot) and the backlight is a plain GPIO, because PWM
doesn't survive a soft reset and looks like a blank panel. LVGL is too heavy
for this board's RAM: use the Simon example, or the standalone CircuitPython
one. After heavy SPI use, recover with a cold boot rather than a soft reset.
On CircuitPython the official board build exposes `LCD_*` and `IMU_*` aliases
and no `board.SPI()` or `board.I2C()`.

**Metro M7 with the 2.8 inch TFT Touch Shield (1947)** has one toggle in its
config, `USE_SOFTSPI`. The default is software SPI, which needs the shield's
11/SO/SI pads soldered and its ICSP pads cut, at 2 MHz, because the Metro can't
move hardware SPI onto D11 to D13. Set it to `False` for the opposite wiring
(ICSP soldered, 11/SO/SI cut) at 24 MHz, which shares the bus with the
AirLift. The board's boot drive is `METROM7BOOT`. A custom MicroPython build
is needed; moving the filesystem offset wipes `/flash`, so redeploy the config
and secrets afterwards. Free memory is small (about 64 KiB of OCRAM), so
appdev, LVGL and a full set of `.py` files don't fit: use the Simon example's
slim path. On MicroPython the AirLift joins Wi-Fi and resolves names, but TCP
sockets fail with nina-fw 1.7.4; CircuitPython 10.2.1 gets HTTP and HTTPS
through `adafruit_esp32spi`, but its `displaydev` runs out of memory, so
prefer MicroPython for the display and CircuitPython for networking.

**NUCLEO-H743ZI2 with the same shield** uses hardware SPI (`USE_SOFTSPI =
False`, 24 MHz): `machine.SPI(1)` is already on D13/D11/D12, so the shield's
11/SO/SI jumpers work as they are. Stock MicroPython maps `D13` to PA7, the
Ethernet pin; the firmware remaps it to PA5, and `Pin("A5")` is the analog pin,
not SPI SCK. Firmware is a custom `NUCLEO_H743ZI2` build with `displayif`,
`graphics` and `lvgl`, flashed through the ST-Link drive. About 450 KiB of
heap is free at idle, and Simon and LVGL fit.

**ESP32-P4-WIFI6-Touch-LCD-4B** has no Ethernet PHY (Ethernet is a different
SKU), and its `camera` role is a CSI stub. **M5Stack CoreS3 and Tab5** wire the
audio codecs and IMU, with camera stubs. **Metro M7 and Nucleo** rows are the
host board plus the shield, which carries the display and touch. Generic OLED
breakouts and EyeSPI stacks aren't listed unless they expose roles beyond the
display.

## Default config

[`board_configs/desktop/`](https://github.com/PyDevices/omnipython/tree/main/board_configs/desktop) — universal non-MCU
`board_config` for desktop, PyScript, and Jupyter. Host display selection is
`displaydev.auto.AutoDisplay` (PS / JN / Win→PG→SDL on Windows); the config
exports hardware only:

```python
display_drv = AutoDisplay(...)
host_read = display_drv.get_events
```

An application opting into `appdev` then creates its own traffic controller:

```python
import board_config
import appdev

app = appdev.App(board_config)
```

LVGL instead creates an independent coordinator in `display_driver`.

Panel size overrides (before `import board_config`): `OMNIPYTHON_WIDTH`,
`OMNIPYTHON_HEIGHT`, `OMNIPYTHON_ROTATION`, `OMNIPYTHON_SCALE`, and
`OMNIPYTHON_MAXIMIZED=1` to open maximised with the panel the window's whole
client area at scale 1 (WinDisplay, on Windows; see
[Displays](../guides/displays.md#windisplay)). Apps should read geometry from
`display_drv`, not module-level names on `board_config`.

Set the env vars **before** `import board_config` (or any import that loads
it). On a host with no environment, `boarddev.env_set("OMNIPYTHON_WIDTH", 800)`
does the same from Python. A script that wants a default size but should respect the user's own
environment sets it only when nothing else has:

```python
import boarddev

if boarddev.env_get("OMNIPYTHON_WIDTH") is None:
    boarddev.env_set("OMNIPYTHON_WIDTH", 800)
import board_config
```

A value set with `env_set` wins over `os.environ`, so without the check it
would override the user. Parsing lives in
[`boarddev.env_int`](https://github.com/PyDevices/omnipython/blob/main/lib/boarddev.py)
and friends (`env_get`, `env_float`, `env_bool`, `env_set`).

Per-board configs under `board_configs/` describe hardware; they never
construct an app.

## Custom config

Copy the closest match, edit pin assignments and driver imports, and test with
`import pydevices_demo`. See the
[**pydevices_demo.py**](https://github.com/PyDevices/gallery/blob/main/lib/examples/pydevices_demo.py)
for a walkthrough of the recommended smoke test.
