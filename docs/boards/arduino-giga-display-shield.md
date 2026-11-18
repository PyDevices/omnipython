# Arduino GIGA R1 WiFi with the Display Shield

What the OmniPython board config for the GIGA R1 WiFi and its Display Shield
gives you, and how to set the board up. The role names (`audio_out`, `pcm_in`,
`usb_device` and the rest) are explained in
[Board peripherals](board-contract.md); the other boards are in
[Board configs](board-configs.md).

- **Config:** `fbdisplay/arduino-giga-display-shield`, in [`board_configs/`](https://github.com/PyDevices/omnipython/tree/main/board_configs/fbdisplay/arduino-giga-display-shield).
- **Resolution:** 480×800, portrait. LVGL programs see an 800×480 landscape
  screen: `LVGL_ROTATION` in `board_config.py` sets which way up (0 keeps it
  portrait), and LVGL rotates touch to match. Programs that draw without LVGL
  see the panel as 480×800.
- **Display:** `mipidsi.Bus` + `mipidsi.Display`, ST7701S init sequence
  (`giga_display_shield_init`), 2-lane DSI at 500 Mbit/s per lane, pixel clock
  40 MHz, framebuffer in the GIGA's SDRAM. Panel power on PC6, backlight on PB12.
- **Touch:** GT911 on I2C4 (SCL PB6, SDA PH12), reset PI2, interrupt PI1.
  If `I2C(4).scan()` finds nothing (it should list the GT911, at `0x14` or
  `0x5D`, beside `0x50` and `0x68`), the shield isn't fully seated on the
  GIGA's headers: press it home or reseat it.
- **Audio:** the headphone jack, which the STM32H747's DAC drives directly
  (left PA5, right PA4), through the firmware's `audioio.AudioOut`.
  `audio_out` and `pcm_out` both play there, at any rate, mono or stereo, at
  12 bits. There's no codec, so volume is scaled in software. The DAC's ring
  holds about 93 ms; `latency="buffered"` asks for 250 ms and `queue_ms` for
  any length, which a player wants and an instrument doesn't. A write to
  `/flash` pauses the interpreter for 140-280 ms, so don't write files while
  audio plays. Needs the firmware's `audiodsp` and `audioif` modules.
- **Microphones:** `pcm_in` records the Display Shield's MP34DT06J, a PDM
  microphone that the STM32H747's DFSDM decimates in hardware (clock PD3,
  data PC1), at 8, 16, 24, 32 or 48 kHz. `pcm_in(mic="jack")` records a
  headset's microphone in the jack instead, from the ring on A7 (PA0), sampled
  by the ADC at any rate; that path has been checked on the ADC's side, not yet
  with a headset in the jack. Both are mono 16-bit and record while `audio_out`
  plays; one records at a time. The firmware keeps about a quarter of a second
  at 16 kHz, so a reader can fall that far behind without losing anything.
- **USB MIDI:** `usb_midi` makes the USB-C port a MIDI device the computer
  plays, beside the REPL's serial port. Needs firmware with
  `machine.USBDevice` and micropython-lib's `usb-device-midi`.
- **USB host:** the USB-A port hosts keyboards, mice, flash drives and MIDI
  controllers through `usb.core`, `usb.host.hid`, `usb.host.msc` and
  `midiports.usb_host`, while the USB-C port stays the REPL. The port has no
  power until `usb.core.start()`. Bus-powered devices that draw more than about
  500 mA may not run; use a powered hub. Needs firmware with the `usbhost`
  module ([what it supports](https://github.com/PyDevices/omnipython-builds/blob/main/modules/usbhost/README.md)).
- **USB flash drive as `/sd`:** the board has no card slot, so `sdcard` is the
  flash drive in the USB-A hub, as a block device: `os.mount(board.sdcard, "/sd")`
  and apps that read `/sd` (midiEngine's `/sd/midi` and `/sd/soundfonts`, the MP3
  player) find the drive's files. It starts the USB host, so keep a keyboard or
  MIDI device in the same hub, and give it a few seconds to show up. It needs
  `usb.host.msc` in the ROMFS, which a `usbhost` firmware's ROMFS carries (below). Interrupting a transfer to the drive can leave
  it timing out until the board resets.
- **Bluetooth LE:** `ble` is a bledev adapter over the GIGA's Murata 1DX,
  which also answers every `bluetooth.BLE` method. Needs firmware with
  Bluetooth, and micropython-lib's `aioble`.
- **IMU:** the shield's BMI270 on I2C4 at `0x68`, beside the touch
  controller, so `accelerometer` and `gyroscope` (one object) take
  `board_config.i2c`. Needs micropython-lib's `bmi270`.
- **LED and button:** `led` is the GIGA's green LED (PJ13, active low, as a
  `machine.Signal`); `boot_button` is the BOOT0 button on PC13, reading 1
  while pressed.
- **Not yet roles:** the camera connector waits for firmware support; the shield's RGB LED (IS31FL3197 at `0x50`) waits for a driver. CAN needs a
  transceiver the board doesn't have, and the only RTC is the STM32's own
  (`machine.RTC`).
- **Firmware:** omnipython-builds' `ARDUINO_GIGA` board with its
  `DISPLAY_SHIELD` variant and `--modules displayif,lvgl`
  ([flashing it](https://github.com/PyDevices/omnipython-builds/blob/main/docs/guides/flash-a-board.md)).
- **Libraries:** the OmniPython libraries don't fit in the firmware beside
  LVGL, so they go in the board's 4 MB ROMFS with the drivers this board
  needs: the two in this repository, micropython-lib's `bmi270` for the IMU
  and `aioble` for Bluetooth, and the audio packages
  `audioeffects` and `audioinstruments` that apps like midiEngine import. The
  firmware keeps its own Python modules (asyncio, webrepl, mip and the rest)
  in the ROMFS too, and a deploy replaces the whole partition, so start the
  folder with those, from the firmware release's `romfs-files` zip or the
  build's `romfs/` folder, which already holds `usb.device` and, from a `usbhost`
  build, `usb.core` and the `usb.host` classes (a `usb` package in the ROMFS
  hides any `usb/` you install in `/flash/lib`, so the host packages can only go
  in the ROMFS). Then add the rest and deploy it once, from a clone of this
  repository:

  ```bash
  git clone --depth 1 https://github.com/PyDevices/omnipython.git
  mkdir romfs
  unzip omnipython-mp-arduino_giga-display_shield-*.romfs-files.zip -d romfs
  cp -r omnipython/lib/* omnipython/drivers/touch/gt911.py \
      omnipython/drivers/display/giga_display_shield_init.py romfs/
  cp -r omnipython/packages/midiports/midiports romfs/
  curl -o romfs/bmi270.py https://raw.githubusercontent.com/micropython/micropython-lib/master/micropython/drivers/imu/bmi270/bmi270.py
  mkdir romfs/aioble
  for f in __init__ central client core device l2cap peripheral security server; do
      curl -o romfs/aioble/$f.py https://raw.githubusercontent.com/micropython/micropython-lib/master/micropython/bluetooth/aioble/aioble/$f.py
  done
  for r in audioeffects audioinstruments; do
      git clone --depth 1 --branch v0.5.1 https://github.com/PyDevices/$r.git
      cp -r $r/lib/$r romfs/
      rm -f romfs/$r/README.md
  done
  mpremote romfs deploy romfs
  cd omnipython/board_configs/fbdisplay/arduino-giga-display-shield
  mpremote cp board_config.py board_peripherals.py :/flash/
  ```

  With the `mpy-cross` Python package installed, mpremote compiles the folder
  to `.mpy` on the way; without it the board compiles the `.py` files as
  they're imported. `/rom` comes before `/flash` on `sys.path`.

- **Installing apps:** the firmware has no `omip`, and `mip`'s default folder
  can be the read-only ROMFS, so name `/flash/lib` yourself. Join Wi-Fi from
  `secrets.py`, then put `omip` on the board's flash:

  ```python
  import mip
  mip.install("github:PyDevices/omnipython/lib/omip.py", target="/flash/lib")
  ```

  `omip.install` then installs into `/flash/lib` and `/flash/apps` on its
  own, so the app lines in
  [install an app](https://github.com/PyDevices/apps/blob/main/docs/guides/install-an-app.md)
  work as written. Where that guide says `target="/"`, for Home's `main.py`
  and for a newer `omip`, say `target="/flash"` and `target="/flash/lib"`
  here: the board's writable drive is `/flash`.
