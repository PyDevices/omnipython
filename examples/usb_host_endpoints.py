# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""List what's plugged into the board's USB host port, as it changes.

Registers ``usb.host.endpoints``, which starts the host port and puts
every device on it into endpointkit's lists under the role it plays: a
keyboard under ``keys``, a MIDI keyboard under ``midi.in`` and
``midi.out``, a flash drive under ``storage``, a USB serial board under
``serial``. The program prints the list, then keeps polling and prints
it again whenever you plug something in or pull it out. Each poll reads
only the host's plug and unplug counters, so it costs next to nothing
when nothing moves. Success is your devices listed under their kinds,
with a hub's devices each listed on their own.

Needs: a board running MicroPython with the OmniPython USB host, such
as an ESP32-S2, S3, P4 or S31, the usb-host-endpoints package (mip
brings endpointkit and usb.core with it), and a USB device or hub on the
host port. A usb package frozen into the firmware wins over ``/lib``, so
a firmware with usb frozen in needs one whose ``usb.core`` has
``counters()``. On a board whose only USB port carries the REPL,
use the UART or WebREPL, because the host takes that port.

Run it:

    mpremote mip install github:PyDevices/omnipython/packages/usb/usb-host-endpoints
    mpremote run usb_host_endpoints.py

Tested on: Waveshare ESP32-S31-Touch-LCD-4.3C on MicroPython
v1.30.0-preview.160 (built 2026-11-22), over WebREPL, with this
repository's usb.core, usb.host.endpoints and endpointkit ahead of the
frozen ones, and a USB hub holding a MIDI keyboard, a flash drive and
another board's USB serial port. The hub's power was cycled once while
it watched.
"""

import time

import endpointkit
from usb.host import endpoints

# Change these to match your setup.
SECONDS = 60  # how long to watch for devices coming and going


def show():
    """Print every device on the port under each kind it serves."""
    count = 0
    for kind in endpoints.KINDS:
        for ep in endpointkit.endpoints(kind):
            caps = ep.caps
            print("%-9s %-32s %04x:%04x interface %d" % (kind, ep.label, caps["vid"], caps["pid"], caps["interface"]))
            count += 1
    if not count:
        print("Nothing on the USB host port")


# Register a provider for every kind a USB device can serve. This starts
# the host port if nothing has yet.
endpoints.register()
endpointkit.poll()
show()

# Poll a few times a second. poll() is True when something came or went.
print("Watching for %d seconds; plug something in or pull it out." % SECONDS)
start = time.ticks_ms()
while time.ticks_diff(time.ticks_ms(), start) < SECONDS * 1000:
    if endpointkit.poll():
        print("Changed:")
        show()
    time.sleep_ms(250)
