# USB support

What a board can do on USB, in two directions: drive devices from its host
port, and present itself to a computer or to another board's host port. The
[USB guide](../guides/usb.md) shows how to use each package; the host's limits
are in
[the host's own page](https://github.com/PyDevices/omnipython-builds/blob/main/modules/usbhost/docs/host.md).

## Host: what a board can drive

### Host: what works

| Device | Package | What you get |
|---|---|---|
| Keyboard, mouse, media keys | [`usb-host-hid`](https://github.com/PyDevices/omnipython/tree/main/packages/usb/usb-host-hid) | Key, button and movement events named as `adafruit_hid` names them. Boot protocol by default, report protocol with `boot=False` |
| Gamepad, joystick | [`usb-host-hid`](https://github.com/PyDevices/omnipython/tree/main/packages/usb/usb-host-hid) | `usb.host.hid_generic`: button, axis and hat events from the device's report descriptor. A D-pad reported as buttons, and pads that need a start-up message, aren't read |
| Flash drive | [`usb-host-msc`](https://github.com/PyDevices/omnipython/tree/main/packages/usb/usb-host-msc) | Bulk-Only Transport, mounted with `vfs.VfsFat`, read and write. 512-byte blocks |
| USB serial (CDC-ACM, CH340/CH341, CP210x, FTDI, PL2303) | [`usb-host-cdc`](https://github.com/PyDevices/omnipython/tree/main/packages/usb/usb-host-cdc) | A `Serial` that reads and writes like `machine.UART`, with DTR and RTS and line coding. A CDC-ECM or NCM network device isn't taken for a serial port |
| MIDI controller (MIDI 1.0) | [`midiports`](https://github.com/PyDevices/omnipython/blob/main/packages/midiports/README.md) | `midiports.usb_host`, the same port shape as `usb_midi` |
| Speaker or microphone (USB Audio 1.0 and 2.0) | [`usb-host-audio`](https://github.com/PyDevices/omnipython/tree/main/packages/usb/usb-host-audio) | `Speaker` and `Microphone`, and audiodev `audio_out()` and `pcm_in()` over them |
| Webcam (UVC) | [`usb-host-video`](https://github.com/PyDevices/omnipython/tree/main/packages/usb/usb-host-video) | Whole MJPEG or YUY2 frames, negotiated with the camera |
| Phone or camera (MTP and PTP) | [`usb-host-mtp`](https://github.com/PyDevices/omnipython/tree/main/packages/usb/usb-host-mtp) | List, read and fetch photos and files, and thumbnails. Read only |
| Android USB tethering (RNDIS), CDC-ECM Ethernet adapters | [`usb-host-net`](https://github.com/PyDevices/omnipython/tree/main/packages/usb/usb-host-net) | `Tether`, a network interface with an address from the phone or the adapter's network. CDC-NCM and vendor-specific adapters aren't supported |
| Board in its DFU bootloader | [`usb-host-dfu`](https://github.com/PyDevices/omnipython/tree/main/packages/usb/usb-host-dfu) | Read a board's flash, a block at a time. Read only: nothing is downloaded or erased |
| Anything else | [`usb-core`](https://github.com/PyDevices/omnipython/tree/main/packages/usb/usb-core) | `usb.core.find`, `ctrl_transfer`, `read` and `write`, in PyUSB's shape |

### Host: where it runs

| Board | Engine | Speed | Classes |
|---|---|---|---|
| ESP32-S3 | ESP-IDF's USB host library | Full speed | All of the above |
| ESP32-P4 | ESP-IDF's USB host library | High speed | All of the above |
| ESP32-S31 | ESP-IDF's USB host library (`espressif/usb`) | High speed | A drive, a MIDI controller, a webcam and a CDC serial port are checked; a sound card hasn't been tried. On the Waveshare ESP32-S31-Touch-LCD-4.3C the host port is the 4-pin header J3 |
| ESP32-S2 | ESP-IDF's USB host library | Full speed | The same build; the classes are checked on the S3 and P4 |
| ESP32-P4 on CircuitPython | ESP-IDF's USB host library | High speed | A wireless keyboard and mouse dongle; drives and streams haven't been tried |
| Arduino GIGA R1 Display Shield | TinyUSB's host, on the USB-A port | Full speed | Control, bulk and interrupt transfers only: a drive, a keyboard and a MIDI controller work |

### Host: what isn't supported

| What | Where | Because |
|---|---|---|
| Audio and video devices | GIGA | TinyUSB's host there has no isochronous transfers |
| USB tethering and Ethernet adapters | GIGA, CircuitPython | The tethering adapter is built on ESP-IDF's host and lwIP; the GIGA runs TinyUSB's host, and CircuitPython's ESP32-P4 port has no network yet |
| Any host at all | Boards other than the ESP32-S2, S3, P4, S31 and the GIGA | `usbhost` builds only for those; the module is skipped on other chips, rp2 among them |
| A high-speed link | ESP32-S2, S3, GIGA | Their host ports are full speed |
| A webcam and a USB Audio 2.0 speaker in one session | ESP32 | The controller's FIFO split is fixed for each `usb.core.start()`, and a camera and a speaker need different splits |
| Every device at once | ESP32-S3 | The host has eight channels (the P4 and S31 have sixteen). A device's control pipe takes one, a bulk pair two and an interrupt IN one, so a drive and a keyboard fit and a drive and a MIDI controller don't |
| Full- and low-speed devices behind a hub | ESP32-P4 | The port runs at high speed and the host there has no transaction translator. Start the host with `usb.core.start(full_speed=True)`, which slows the whole bus. The S31's host has one |

## Device: what a board can present

### Device: what works

| The board is | Package | What you get |
|---|---|---|
| A serial port | Built in, and [`usb-device-cdc`](https://github.com/micropython/micropython-lib/tree/master/micropython/usb/usb-device-cdc) | The REPL stays on its own port; `usb-device-cdc` adds more |
| A MIDI device (MIDI 1.0) | [`usb-device-midi`](https://github.com/micropython/micropython-lib/tree/master/micropython/usb/usb-device-midi) and `midiports.usb_device` | One cable |
| A keyboard, mouse or media remote | [`usb-device-keyboard`](https://github.com/micropython/micropython-lib/tree/master/micropython/usb/usb-device-keyboard), [`usb-device-mouse`](https://github.com/micropython/micropython-lib/tree/master/micropython/usb/usb-device-mouse) and [`usb-hid`](https://github.com/PyDevices/omnipython/tree/main/packages/usb/usb-hid) | `usb-hid` gives `adafruit_hid` CircuitPython's `usb_hid.devices` |
| A gamepad, or a pointer that says where it is | [`usb-hid`](https://github.com/PyDevices/omnipython/tree/main/packages/usb/usb-hid) | `Device.GAMEPAD` (16 buttons, a hat, four axes) and `Device.ABSOLUTE_POINTER` (X and Y across the screen, for a touch panel to drive), in the shape of CircuitPython's custom `usb_hid.Device`s |
| Any other HID device | [`usb-device-hid`](https://github.com/micropython/micropython-lib/tree/master/micropython/usb/usb-device-hid) | `HIDInterface` takes any report descriptor you give it |
| A network adapter (CDC-NCM) | [`usb-device-net`](https://github.com/PyDevices/omnipython/tree/main/packages/usb/usb-device-net) | `NCMInterface`: the computer gets an address from the board's DHCP server, and `NCMInterface.nic` is the board's end as a `network.USBD_NCM`. Windows 10 and later, Linux and macOS need no driver. Takes two IN endpoint numbers |
| A flash drive | [`usb-device-msc`](https://github.com/PyDevices/omnipython/tree/main/packages/usb/usb-device-msc) | Bulk-Only Transport over any block device: an SD card, a partition, RAM. `readonly=True` refuses writes |
| A sound card, a microphone, or both as a headset (USB Audio 2.0) | [`usb-device-audio`](https://github.com/PyDevices/omnipython/tree/main/packages/usb/usb-device-audio) | `SpeakerInterface`, `MicrophoneInterface` and `HeadsetInterface`: 48 kHz stereo 16-bit through rings, with feedback on the speaker so the clocks stay in step. The packet size follows the link's speed. A speaker or a microphone takes one IN endpoint number and a headset takes two |
| A webcam (UVC 1.1) | [`usb-device-video`](https://github.com/PyDevices/omnipython/tree/main/packages/usb/usb-device-video) | YUY2 or MJPEG, one size or a list for the computer to choose from |

### Device: where it runs

The packages run on MicroPython's `machine.USBDevice`. Audio and video also
need the OmniPython firmware's streaming endpoints (`USBDevice.Ring` and
`USBDevice.stream()`), which `build.py` includes. The network adapter needs
the firmware's `network.USBD_NCM`, which it has wherever the board has lwIP.

| Board | Link speed | Notes |
|---|---|---|
| ESP32-S2, S3 | Full speed | IN endpoints 1 to 4 |
| Arduino GIGA R1 Display Shield | Full speed | The USB-C port, through TinyUSB's device |
| ESP32-P4 | High speed on its high-speed port; full speed through the full-speed PHY | IN endpoints 1 to 7 at high speed, 1 to 4 at full speed. The sound card and the webcam size their packets to the link |
| RP2040, RP2350 | Full speed | IN endpoints 1 to 15. The network adapter on the W boards, which have lwIP |

### Device: what isn't supported

| What | Because |
|---|---|
| More functions than the endpoints allow | `init()` refuses the set with a `ValueError` that names the chip's IN endpoint count and what each function takes, before anything changes. The ESP32-S2, S3 and a full-speed P4 have IN endpoints 1 to 4, a high-speed P4 1 to 7, and the REPL's serial port takes two of them. `builtin_driver=False` leaves the serial port off until the next reset, and the REPL stays on the UART and WebREPL |
| Device mode on the ESP32-S31 | The S31's firmware has no `machine.USBDevice`; its USB OTG port is the host's |
| Vendor control requests, WebUSB and WinUSB descriptors | `machine.USBDevice` passes class control requests to Python, but not vendor ones, and has no Binary Object Store descriptor |
