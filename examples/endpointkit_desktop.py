# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""List your computer's sound devices, MIDI ports and network.

Registers the endpointkit providers that come with omnipython-desktop:
audiodev's for sound output and input, midiports' for MIDI, and hostnet's
for the network link. It prints every endpoint by kind and what is chosen,
then keeps polling for a while and prints the list again whenever a device
comes or goes, so plugging in a USB headset or a MIDI keyboard shows up
within a few seconds. Success is your speakers, microphones and MIDI ports
listed under their kinds.

Needs: CPython with omnipython-desktop and its audio and MIDI backends.

Run it:

    python endpointkit_desktop.py

Tested on: CPython 3.14 on Windows 11, which listed its speakers,
microphone and MIDI ports, and CPython 3.12 on Linux under WSL, which
has only the default sound devices and no MIDI ports.
"""

import time

import endpointkit
import hostnet
from audiodev import endpoints as audio_endpoints
from midiports import endpoints as midi_endpoints

# Change these to match your setup.
KINDS = ("audio.out", "audio.in", "midi.in", "midi.out", "net")
SECONDS = 30  # how long to watch for devices coming and going


def show():
    """Print each kind's endpoints, marking the chosen ones."""
    for kind in KINDS:
        chosen = endpointkit.selection(kind)
        for ep in endpointkit.endpoints(kind):
            mark = "*" if ep.id in chosen else " "
            print("%s %-9s %-40s %s" % (mark, kind, ep.label, ep.state))


# Register the computer's own providers.
audio_endpoints.register()
midi_endpoints.register()
hostnet.register()
show()

# Poll for a while. poll() is True when something changed.
print("Watching for %d seconds; plug something in." % SECONDS)
end = time.monotonic() + SECONDS
while time.monotonic() < end:
    if endpointkit.poll():
        print("Changed:")
        show()
    time.sleep(0.2)
