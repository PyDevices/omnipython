# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""What's plugged into this board's USB host port, as endpointkit endpoints.

Register once, and every device you plug in shows up under the kind it
serves, and drops out when you pull it::

    import endpointkit
    from usb.host import endpoints

    endpoints.register()
    while True:
        endpointkit.poll()          # appkit's Shell does this for you
        for ep in endpointkit.endpoints("keys"):
            print(ep.label, ep.state)

A device can serve several kinds: a headset is ``audio.out`` and
``audio.in``, a keyboard with a touchpad is ``keys`` and ``pointer``. The
kinds are:

========================  =====================================================
``audio.out``, ``audio.in``  a USB Audio speaker, headset or interface
``midi.in``, ``midi.out``    a USB MIDI keyboard, controller or interface
``keys``                     a keyboard
``pointer``                  a mouse, trackball or touchpad
``gamepad``                  a gamepad or joystick
``camera``                   a USB Video (UVC) webcam
``storage``                  a flash drive or card reader, or a phone's files (MTP)
``serial``                   a USB serial adapter or board (CDC-ACM)
``net``                      a USB network adapter or a phone sharing its connection
========================  =====================================================

``storage`` and ``serial`` aren't among endpointkit's own kinds, so
`register` adds them.

Finding a device is cheap: each `endpointkit.poll` reads the host's plug and
unplug counters once, and looks at the devices again only when they move.
Choosing an endpoint marks it connected and opens nothing: a program reads
the choice and opens the device with its class driver (``usb.host.audio``,
``usb.host.hid``, ``usb.host.msc`` and the rest), which `device` and
`interface` hand it::

    ep = endpointkit.selected("storage")[0]
    drive = msc.Drive(endpoints.device(ep))

An endpoint's id holds the device's vendor and product IDs and, when it has
one, its serial number, so a saved choice finds the same device after a
restart.
"""

import endpointkit
import usb.core

#: Kinds this module adds to endpointkit's: how many of each can be chosen, what
#: a person calls them and their icon.
NEW_KINDS = {
    "storage": (endpointkit.MANY, "Storage", "sd_card"),
    "serial": (endpointkit.MANY, "Serial ports", "usb"),
}

#: The kinds a USB device can serve, in the order `register` makes their providers.
KINDS = ("audio.out", "audio.in", "midi.in", "midi.out", "keys", "pointer", "gamepad",
         "camera", "storage", "serial", "net")

# Descriptor types and interface classes (USB 2.0 ch. 9 and each class's spec).
_INTERFACE = 4
_ENDPOINT = 5
_HID_DESC = 0x21
_AUDIO = 1
_AUDIO_STREAMING = 2
_MIDI_STREAMING = 3
_CDC = 2
_CDC_ACM = 2
_CDC_ECM = 6
_CDC_NCM = 0x0D
_HID = 3
_STILL_IMAGE = 6   # MTP and PTP
_MSC = 8
_VIDEO = 0x0E
_VIDEO_STREAMING = 2
_WIRELESS = 0xE0   # RNDIS: class E0, subclass 1, protocol 3
_MISC = 0xEF       # RNDIS on some phones: class EF, subclass 4, protocol 1

# HID Generic Desktop usages that name what a device is.
_HID_KINDS = {1: "pointer", 2: "pointer", 4: "gamepad", 5: "gamepad", 6: "keys", 7: "keys", 8: "gamepad"}


def _walk(blob):
    """The descriptors in a configuration blob, as (type, offset, length)."""
    i = 0
    n = len(blob)
    while i + 1 < n:
        length = blob[i]
        if length < 2 or i + length > n:
            return
        yield blob[i + 1], i, length
        i += length


def interfaces(blob):
    """Each interface of a configuration blob, alternate 0 and up merged.

    Returns a list of dicts in interface order, each with ``number``,
    ``cls``, ``subclass``, ``protocol``, ``ins`` and ``outs`` (the data
    endpoint addresses of every alternate) and ``report_length`` (a HID
    interface's report descriptor length, else 0).
    """
    found = {}
    order = []
    cur = None
    for kind, i, length in _walk(blob):
        if kind == _INTERFACE and length >= 9:
            number = blob[i + 2]
            cur = found.get(number)
            if cur is None:
                cur = {"number": number, "cls": blob[i + 5], "subclass": blob[i + 6],
                       "protocol": blob[i + 7], "ins": [], "outs": [], "report_length": 0}
                found[number] = cur
                order.append(number)
        elif cur is None:
            continue
        elif kind == _ENDPOINT and length >= 7:
            address, attributes = blob[i + 2], blob[i + 3]
            # An isochronous endpoint whose usage is feedback paces a
            # speaker's stream; it carries no audio of its own.
            if attributes & 3 == 1 and attributes >> 4 & 3 == 1:
                continue
            side = cur["ins"] if address & 0x80 else cur["outs"]
            if address not in side:
                side.append(address)
        elif kind == _HID_DESC and length >= 9:
            cur["report_length"] = blob[i + 7] | blob[i + 8] << 8
    return [found[n] for n in order]


def hid_kinds(report):
    """The kinds a HID report descriptor's application collections name.

    A combined receiver can name several: ``["keys", "pointer"]``. Usages
    other than Generic Desktop's keyboard, mouse, pointer, joystick and
    gamepad (media keys, a vendor's own) name none.
    """
    kinds = []
    page = 0
    usage = None
    i = 0
    n = len(report)
    while i < n:
        prefix = report[i]
        if prefix == 0xFE:  # a long item: its data length is the next byte
            i += 3 + (report[i + 1] if i + 1 < n else 0)
            continue
        size = (0, 1, 2, 4)[prefix & 3]
        value = 0
        for k in range(size):
            if i + 1 + k < n:
                value |= report[i + 1 + k] << (8 * k)
        tag = prefix & 0xFC
        if tag == 0x04:      # Usage Page
            page = value
        elif tag == 0x08:    # Usage
            if usage is None:
                usage = (value >> 16, value & 0xFFFF) if size == 4 else (page, value)
        elif tag == 0xA0:    # Collection
            if value == 1 and usage is not None and usage[0] == 1:
                kind = _HID_KINDS.get(usage[1])
                if kind and kind not in kinds:
                    kinds.append(kind)
            usage = None
        elif tag == 0x80 or tag == 0x90 or tag == 0xB0:  # Input, Output, Feature
            usage = None
        i += 1 + size
    return kinds


def _hid_report(dev, itf):
    """A HID interface's report descriptor, or None when the device won't give it."""
    length = itf["report_length"] or 256
    try:
        return bytes(dev.ctrl_transfer(0x81, 6, 0x2200, itf["number"], length, 1000))
    except (OSError, usb.core.USBError):
        return None


def kinds_of(dev, blob):
    """What each interface of a device serves: a list of (kind, interface number)."""
    out = []

    def add(kind, number):
        if (kind, number) not in out:
            out.append((kind, number))

    for itf in interfaces(blob):
        cls, sub, number = itf["cls"], itf["subclass"], itf["number"]
        if cls == _AUDIO and sub == _AUDIO_STREAMING:
            if itf["outs"]:
                add("audio.out", number)
            if itf["ins"]:
                add("audio.in", number)
        elif cls == _AUDIO and sub == _MIDI_STREAMING:
            if itf["ins"]:
                add("midi.in", number)
            if itf["outs"]:
                add("midi.out", number)
        elif cls == _HID:
            # A boot keyboard or mouse says so in its interface; anything
            # else says what it is in its report descriptor.
            if sub == 1 and itf["protocol"] == 1:
                add("keys", number)
            elif sub == 1 and itf["protocol"] == 2:
                add("pointer", number)
            else:
                report = _hid_report(dev, itf)
                for kind in hid_kinds(report) if report else ():
                    add(kind, number)
        elif cls == _VIDEO and sub == _VIDEO_STREAMING:
            # One camera per device, however many streams it offers.
            if not any(k == "camera" for k, _ in out):
                add("camera", number)
        elif cls == _MSC or (cls == _STILL_IMAGE and sub == 1):
            add("storage", number)
        elif cls == _CDC and sub == _CDC_ACM:
            add("serial", number)
        elif (cls == _CDC and sub in (_CDC_ECM, _CDC_NCM)) or (cls == _WIRELESS and sub == 1 and itf["protocol"] == 3) \
                or (cls == _MISC and sub == 4 and itf["protocol"] == 1):
            add("net", number)
    return out


def _key(dev, serial):
    key = "%04x-%04x" % (dev.idVendor, dev.idProduct)
    return key + "-" + serial if serial else key


_ID_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."


def _safe(text):
    # An endpoint id is "<provider>:<local id>", so a serial can't carry ":".
    # MicroPython's str has no isalnum(), so the characters are spelled out.
    return "".join(c if c in _ID_CHARS else "_" for c in text)


class Host:
    """The devices on the host port, read again only when one comes or goes.

    Every provider `register` makes shares one, so a poll that finds a change
    reads each device once, however many kinds it serves.
    """

    def __init__(self):
        self.generation = 0
        self.found = {}   # kind -> list of (local id, label, caps, Device, interface)
        self._counters = None

    def update(self):
        """Look at the port; True when the devices changed since the last look."""
        counters = usb.core.counters()
        if counters == self._counters:
            return False
        self._counters = counters
        found = {}
        seen = {}
        for dev in usb.core.attached() if counters else ():
            try:
                blob = dev.configuration_descriptor()
                serial = dev.serial_number
                label = dev.product or "USB device %04x:%04x" % (dev.idVendor, dev.idProduct)
            except (OSError, usb.core.USBError):
                continue  # gone again, or not answering: the next change looks again
            key = _key(dev, _safe(serial) if serial else None)
            # Two of the same device without serial numbers: number the second.
            seen[key] = seen.get(key, 0) + 1
            if seen[key] > 1:
                key = "%s-%d" % (key, seen[key])
                label = "%s (%d)" % (label, seen[key])
            for kind, number in kinds_of(dev, blob):
                rows = found.setdefault(kind, [])
                local = "%s-i%d" % (key, number)
                caps = {"vid": dev.idVendor, "pid": dev.idProduct, "interface": number, "speed": dev.speed}
                rows.append((local, label, caps, dev, number))
        # A device serving one kind twice (two MIDI ports) gets its labels numbered.
        for rows in found.values():
            labels = [row[1] for row in rows]
            for j, row in enumerate(rows):
                if labels.count(row[1]) > 1:
                    rows[j] = (row[0], "%s %d" % (row[1], labels[: j + 1].count(row[1]))) + row[2:]
        self.found = found
        self.generation += 1
        return True


class UsbProvider(endpointkit.Provider):
    """One kind of what the host port has, from a shared `Host`.

    Only the first provider `register` makes (the *leader*) looks at the
    port; the registry polls providers in the order they registered, so the
    rest see what it found in the same poll.
    """

    def __init__(self, kind, host, leader=False):
        endpointkit.Provider.__init__(self, kind, "usb-" + kind.replace(".", "-"))
        self.host = host
        self.leader = leader
        self.devices = {}   # local id -> (Device, interface number)
        self.chosen = set()
        self._generation = -1

    def scan(self):
        self.host.update()
        return self._endpoints()

    def poll(self):
        if self.leader:
            self.host.update()
        if self.host.generation == self._generation:
            return None
        return self._endpoints()

    def _endpoints(self):
        self._generation = self.host.generation
        self.devices = {}
        found = []
        for local, label, caps, dev, number in self.host.found.get(self.kind, ()):
            self.devices[local] = (dev, number)
            state = endpointkit.CONNECTED if local in self.chosen else endpointkit.AVAILABLE
            found.append(self.endpoint(local, label, state, caps))
        return found

    def apply(self, endpoint, chosen):
        if chosen:
            self.chosen.add(endpoint.local_id)
            endpoint.state = endpointkit.CONNECTED
        else:
            self.chosen.discard(endpoint.local_id)
            endpoint.state = endpointkit.AVAILABLE


_registered = []


def register(registry=None, start=True, full_speed=False):
    """Register a provider for each kind a USB device can serve.

    Args:
        registry (endpointkit.Registry): where to register; endpointkit's own
            when None.
        start (bool): start the host port if it isn't running, so devices
            are found without anything calling `usb.core.find` first.
        full_speed (bool): passed to `usb.core.start` when it starts the
            port here.

    Returns:
        list: the providers, one per kind in `KINDS`.

    Raises:
        OSError: this firmware has no USB host.
    """
    if usb.core.stats() is None:
        raise OSError("this firmware has no USB host")
    if start and not usb.core.running():
        usb.core.start(full_speed=full_speed)
    for name, (count, title, icon) in NEW_KINDS.items():
        endpointkit.add_kind(name, count, title, icon)
    reg = registry if registry is not None else endpointkit
    host = Host()
    made = [UsbProvider(kind, host, leader=(kind == KINDS[0])) for kind in KINDS]
    for provider in made:
        reg.register(provider)
    if registry is None:
        _registered.extend(made)
    return made


def unregister(registry=None, providers=None):
    """Remove the providers `register` made; the host port keeps running."""
    reg = registry if registry is not None else endpointkit
    for provider in providers if providers is not None else list(_registered):
        reg.unregister(provider)
        if provider in _registered:
            _registered.remove(provider)


def device(endpoint):
    """The `usb.core.Device` behind one of these endpoints, or None once it's gone."""
    entry = getattr(endpoint.provider, "devices", {}).get(endpoint.local_id)
    return entry[0] if entry else None


def interface(endpoint):
    """The interface number the endpoint serves, for a class driver that takes one."""
    return endpoint.caps.get("interface")
