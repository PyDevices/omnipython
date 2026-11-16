# Roadmap

OmniPython is heading toward covering more of the hardware a board can carry,
with each kind of peripheral described honestly by its role.

## Audio

- A board role for encoded audio. Chips such as the VS1053 decode MP3, Ogg or
  MIDI themselves and encode from a mic, so they get a role of their own
  beside `pcm_out` and `pcm_in` instead of passing as PCM.

## USB

- The HID, CDC and MSC host drivers on CircuitPython's own `usb.core` (RP2040,
  i.MX): they lack only `configuration_descriptor()` and the private
  `_release_all()` there. Audio, video and net need the usbhost engine.

## BLE

- `bledev.hid` reads report descriptors of any length. Today a board reads
  only the first 246 bytes, so a device with a longer map (an Xbox controller's
  is 283) is cut off; the fix is a long GATT read in the firmware.
- BLE MIDI through Windows MIDI Services' new Bluetooth transport: once it
  ships, a board running `bledev.midi.serve()` should open in any Windows MIDI
  app without pairing, and the BLE docs say so.

## hmilink

- A secret a panel must present before it can read or change the document, and
  encryption on the transports that can carry it, for networks you don't fully
  trust. medialink's links use the same secret to encrypt their sound and
  pictures.
- `hmilink.appkit`: an appkit launcher and its apps' models served over one
  transport, so a phone can see and switch apps. An app set that serves no
  panel loads none of it.

## medialink

- Talk both ways at once on a videophone, on boards whose speaker and
  microphone share one I2S port: that needs a duplex I2S path.
- Decode pictures beside the sound rather than in the same loop, so a
  videophone keeps clean sound with 640x480 pictures both ways.
- One camera watched from several screens at once; today the last watcher
  to connect gets the pictures.
- A BLE transport, using ADPCM to fit its bandwidth, for boards with no
  Wi-Fi between them.

## vtterm

- CircuitPython's own console on the display. CircuitPython has no
  `os.dupterm`, so vtterm shows a session with another device there, not the
  board's own REPL.

Bugs, and things you need that don't work yet, go to
[issues](https://github.com/PyDevices/omnipython/issues).
