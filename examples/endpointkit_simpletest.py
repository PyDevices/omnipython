# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""List what a device can connect to and choose where its audio goes.

Registers stand-in transports from ``endpointkit.fake``, a board's worth
of audio, MIDI, network and camera with no hardware behind them, and
polls until the slow ones (Bluetooth) have reported. It prints every
endpoint by kind, chooses a Bluetooth speaker for audio, and then tries
to share the phone's connection over Bluetooth too. The Bluetooth radio
can't do both, so endpointkit raises ``Conflict`` naming what the second
choice would stop, and the program goes ahead only when it confirms.
Success is that line, then the network on the phone and the audio
with no speaker left. Swap the fakes for a real transport's ``register()`` and the rest of the
program stays the same.

Needs: endpointkit, on MicroPython or CPython. No hardware.

Run it:

    mpremote mip install github:PyDevices/omnipython/packages/endpointkit
    mpremote run endpointkit_simpletest.py

Tested on: the MicroPython unix port v1.30.0-preview.160, and CPython
3.12 on Linux.
"""

import endpointkit
from endpointkit import fake

# Change these to match your setup.
SPEAKER = "a2dp:spk"  # an endpoint id: "<provider>:<local id>"
TETHER = "btpan:phone"  # a choice that needs the same radio as SPEAKER


def show(event, kind):
    """Print each change endpointkit reports for a kind."""
    print("  (%s changed: %s)" % (kind, event))


# Register the stand-ins, and hear when the audio choice moves.
fake.bench()
endpointkit.subscribe("audio.out", show)

# Poll until the Bluetooth speaker turns up. Slow transports report as
# they find things; a real program polls from a timer.
while not endpointkit.find(SPEAKER):
    endpointkit.poll()

# List every endpoint by kind, with its state.
for kind in sorted(endpointkit.KINDS):
    for ep in endpointkit.endpoints(kind):
        print("%-12s %-14s %-20s %s" % (kind, ep.id, ep.label, ep.state))

# Choose the Bluetooth speaker for audio.
endpointkit.select("audio.out", SPEAKER)
print("Audio goes to", [ep.label for ep in endpointkit.selected("audio.out")])

# Ask for Bluetooth tethering. It needs the same radio, so endpointkit
# says what it would stop; a program would ask the person here.
try:
    endpointkit.select("net", TETHER)
except endpointkit.Conflict as conflict:
    print("Tethering would stop", [ep.label for ep in conflict.stops], "on", conflict.resources)
    endpointkit.select("net", TETHER, confirm=True)
print("Network:", [ep.label for ep in endpointkit.selected("net")])
print("Audio goes to", [ep.label for ep in endpointkit.selected("audio.out")])
