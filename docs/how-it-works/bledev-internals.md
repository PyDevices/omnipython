# bledev internals: writing a backend

This page is for you if you're adding a backend (`bledev.bleak`,
`bledev.winrt`, `bledev.bluez`, `bledev.webble`, `bledev.cpble`) or changing one. What an app can rely
on is in [The rules every backend keeps](#the-rules-every-backend-keeps), below, and in the
[Bluetooth LE guide](../guides/bluetooth-le.md); this is how a backend delivers it.

## The layout

[`lib/bledev/`](https://github.com/PyDevices/omnipython/tree/main/lib/bledev) follows `audiodev` and `displaydev`: a portable base, one
standalone module per backend, and an optional selector.

| Module | What it is |
|---|---|
| `__init__.py` | The contract: `UUID`, the errors, `FLAG_*`, advertising pack/unpack, and the base classes below. Imports no backend. |
| `fake.py` | In-process loopback. The reference implementation of every hook. |
| `mpble.py` | MicroPython, over aioble. |
| `bleak.py` | CPython on Windows, Linux and macOS, over bleak. Central only. |
| `winrt.py` | CPython on Windows: `bleak.py`'s central plus a GATT server through WinRT. Both roles. |
| `bluez.py` | CPython on Linux: `bleak.py`'s central plus a GATT server through BlueZ over D-Bus. Both roles. |
| `cpble.py` | CircuitPython, over `_bleio`. Both roles. |
| `webble.py` | Web Bluetooth in a browser, central only. |
| `nus.py` | Nordic UART byte stream, built only on the contract. |
| `repl.py` | The REPL over nus: MicroPython's raw `bluetooth` API from the IRQ on the board, `nus` on the client. |
| `improv.py` | Improv Wi-Fi setup, both sides, built only on the contract. |
| `midi.py` | BLE-MIDI as a usbif-style MIDI port, both sides, built only on the contract. |
| `midi_codec.py` | The BLE-MIDI packet codec. Pure, no imports, shared by every host. |
| `filetransfer.py` | CircuitPython's BLE file-transfer protocol: `FileServer` (pure, no radio), served on the board through `repl`'s server, and a client built on the contract. |
| `battery.py`, `deviceinfo.py` | SIG services as classes over `Service` and `Characteristic`, built only on the contract. `hid.py` serves them too. |
| `heartrate.py`, `cyclingspeed.py`, `cyclingpower.py`, `runningspeed.py`, `environmental.py` | More SIG services, one class each. The cycling and running ones answer their control points through `_sig.py`, which also holds the sensor locations. |
| `hidreport.py` | HID report descriptors and reports to `events`. No Bluetooth in it. |
| `hid.py` | HID over GATT, host and device, built on the contract and `hidreport`. |
| `auto.py` | Picks a backend. Nothing imports it, and backends must not. |

A backend module imports `bledev` and whatever its host provides, and nothing
else in bledev except the base classes. `auto.BACKENDS` expects
`bledev.bleak.BleakBLE`, `bledev.winrt.WinRTBLE`, `bledev.bluez.BlueZBLE` and `bledev.webble.WebBLE`; if you name your class
differently, change that table.

Anything under `lib/` must also be listed in [`omnipython-desktop.toml`](https://github.com/PyDevices/omnipython/blob/main/omnipython-desktop.toml) (a test
checks it). A central-only host module belongs in [`mip-split.toml`](https://github.com/PyDevices/omnipython/blob/main/mip-split.toml)'s
`[bledev] host-only` list once its file exists, so it doesn't ship to boards.

## The hooks

Subclass these and fill in the hooks. Everything else in the base classes is
built on them.

**`BLE`**, the adapter:

- `backend` (class attribute): the module's short name.
- `capabilities()`: start from `BLE.capabilities(self)` and set `central`,
  `peripheral`, `mtu`, `max_mtu`, `indicate`, `pairing`, `l2cap`, and
  `advertise_name` (False where the host picks the advertised name, as
  Windows does; `bledev.advertised_name()` reads it).
- `config(*names, **settings)`: at least `mtu`; raise `UnsupportedError` for
  anything else you don't have. `addr_mode` (`ADDR_MODE_*`) only where the stack
  has private addresses: mpble passes it to NimBLE and says `UnsupportedError`
  where the stack refuses it (BTstack).
- `close()`.
- Peripheral backends: `register_services(*services)`, which sets each
  `Characteristic._impl` (see below), and
  `advertise(interval_us, *, name, services, appearance, manufacturer, connectable, timeout_ms)`,
  which returns your `Connection` with `role="peripheral"`. A central-only
  backend leaves both alone; the base raises `UnsupportedError`.
- Central backends: `scan(duration_ms, *, active, interval_us, window_us)`,
  returning a `Scanner`, and `_connect(device, timeout_ms, **options)`,
  returning your `Connection` with `role="central"`. `find()` is already
  written on top of `scan()`.

**`Scanner`**: either override `__aenter__`/`__anext__`/`cancel()` (mpble
wraps aioble's scanner that way), or keep the base's queue and call
`_push(ScanResult(...))` and `_finish()` from the event loop, starting and
stopping your scan in `_start()`/`_stop()`. bleak's detection callback runs on
the event loop, so `_push` from it is fine. From another thread it isn't: the
base uses `asyncio.Event`.

**`Device`**: construct it with your adapter, the address (six bytes, or the
host's string), and `native=` your own object, which `_connect()` gets back.

**`Connection`**: `is_connected()`, `disconnect(timeout_ms)`,
`disconnected(timeout_ms)`, `exchange_mtu(mtu, timeout_ms)` (return the
current MTU if the host negotiates on its own), the `mtu` property (override
it, or keep `self._mtu` current), and `_discover_services(uuid, timeout_ms)`,
returning a list of your `ClientService` in handle order.

**`ClientService`**: `_discover_characteristics(uuid, timeout_ms)`, a list of
your `ClientCharacteristic` in handle order.

**Pairing and descriptors** (for HID): `Connection.encrypted` and
`Connection.pair(bond, timeout_ms)`; `ClientCharacteristic._discover_descriptors(uuid, timeout_ms)`
returning your `ClientDescriptor`s, whose `read()` you fill in; and on the
server, each `Characteristic`'s `descriptors` (fixed values) and `encrypted`
flag. Report `long_read` in `capabilities()`: False if a read returns only
one packet. A backend without pairing leaves the base's `UnsupportedError`.

**`ClientCharacteristic`**: `read`, `write`, `subscribe`, `notified`,
`indicated`. `self._want_response(response)` resolves `response=None` and
checks the flags for you; `self._check(FLAG_..., what)` checks the rest.

**The server side**: `Characteristic` is backend-neutral. Your
`register_services()` gives each one an `_impl` object with `read()`,
`write(data, send_update)`, `notify(connection, data)` (synchronous),
`indicate(connection, data, timeout_ms)` and `written(timeout_ms)`. The public
methods check the flags before they call it.

## What a backend must translate

- Every timeout to `BLETimeoutError`. `bledev.wait_ms(awaitable, timeout_ms)`
  does it for you.
- A dead link to `DisconnectedError`, including an operation started after
  the drop. aioble raised `TypeError` there; bleak raises its own errors.
- A full transmit buffer to `BusyError` from `notify()`, or a wait-and-retry
  inside an async send.
- A payload over `mtu - 3` to `BLEError`, checked before it reaches the host
  stack, because NimBLE and some OS stacks truncate silently.
- A queue overflow to `BLEError` from the next read of that queue, never a
  silent drop.
- Discovery order to handle order.

## How mpble gets there

aioble is a good base with three places it loses data, and mpble works
around each rather than forking it:

- **Notifications.** aioble keeps one notification per client characteristic
  and replaces it when the next arrives. mpble swaps in a `_Queue` of
  `queue_limit` entries. It also doesn't use aioble's `notified()`, which waits
  only when the queue holds one item or fewer and assumes the flag is then
  set: true for a one-slot queue, but with a longer one it strands the last
  item of a burst. That hung the first board-to-board stream at its tail.
- **Captured writes.** aioble shares one ten-entry deque across every
  characteristic and drops the oldest. mpble registers its own IRQ handler
  beside aioble's, copies each captured write out of the value buffer in the
  IRQ, and ties it to its connection while the connection still exists.
- **Scans.** aioble's defaults (1.28 s interval, 11.25 ms window) listen less
  than 1 % of the time. On the bench a six-second scan saw one advertiser,
  while a full-duty scan saw the board forty times, so mpble defaults to
  30 ms interval and window.

Two more turned up on hardware: discovery results come back in IRQ-race
order, and a `BufferedCharacteristic` loses its initial value, because aioble
writes it and then sizes the buffer. mpble sorts the first and rewrites the
second. From reading aioble rather than from a failure: its `advertise()`
returns `None` when cancelled, and mpble turns that back into
`CancelledError`.

aioble owns the one `bluetooth.BLE()` and its IRQ, so `mpble.get()` shares
one adapter, and the capture handler is registered once per boot.

The laptop found two more:

- **Notifications before a subscription.** NimBLE's server notifies whether
  or not the central wrote the CCCD, and mpble registered its queue at
  discovery, so a board central received what a laptop never would. mpble's
  queues ignore everything until `subscribe()` opens them. The over-the-air
  check "nothing arrives before subscribe()" failed on the old code.
- **An MTU exchange before the connection.** Windows exchanges the MTU the
  moment it connects, and MicroPython 1.29 on the S3 delivers
  `_IRQ_MTU_EXCHANGED` *before* `_IRQ_CENTRAL_CONNECT` (seen every time,
  instrumented in the IRQ). aioble has no connection to give it to and drops
  it, so the board believed the MTU was 23 while the link ran at 247, and
  every notification to a Windows central carried 20 bytes. mpble's IRQ keeps
  the early value and applies it on the connect. Laptop downstream went from
  19 to 49 KB/s. Upstream's own order is worth an issue; the board-to-board
  case never showed it because the central there asks for the MTU after
  connecting.

The bless probe found two more on the P4, with the board as the
central and Windows as the peripheral:

- **The same early MTU, the other way round.** Windows exchanges the MTU the
  moment the board connects, before aioble has recorded the connection, so
  the board believed 23 on a 256 link. mpble's IRQ keeps that value too,
  and the connection's `mtu` picks it up.
- **`exchange_mtu()` after the peer already exchanged** raised `EALREADY`.
  NimBLE exchanges once per link, so mpble returns the settled MTU.
  `bledev.hid`'s host exchanges before reading the Report Map, so any
  peripheral that exchanges first (a real keyboard may) would have failed.

**Code that uses the raw API.** A board config's `ble` is an `MPBLE`,
and `MPBLE.__getattr__` hands every name it doesn't define to the raw
`bluetooth.BLE`, so `ble.active()` or `ble.gap_advertise()` still work.
`irq(handler)` is the exception: it runs the handler from mpble's IRQ rather
than replacing aioble's. Raw advertising trips aioble in two places, both
handled in mpble. aioble's peripheral IRQ calls `_connect_event.set()` on every
incoming connection and raised `AttributeError` when `aioble.advertise()` had
never run, which stopped the IRQ reaching anyone after it; mpble gives it a
flag at startup. And aioble records that connection but never forgets it,
because the task that would is started by its own `advertise()`; mpble forgets
it on the disconnect. Checked on the T-Embed: raw service, raw advertising,
a user IRQ that saw the connect and disconnect, a laptop read, then `nus` on
the same adapter.

## How bleak gets there

bleak hands each notification to a callback on the event loop. The backend
queues it per characteristic (`queue_limit`, an overflow raises) in
`_BleakClientCharacteristic._received`, and routes it to `indicated()` only
when you subscribed with `indicate=True` alone, because bleak can't tell the
two apart. On Windows that subscription passes `force_indicate`.

The OS negotiates the MTU itself. `exchange_mtu()` waits up to a second for
the value to move off 23 and returns it; against `gatt_peripheral.py`, which
asks for 185, Windows settles on 185. BlueZ always reports 23 through bleak,
so the backend also takes the largest write-without-response size it saw in
discovery, plus three.

`connect(priority="throughput")`, or an interval of 15 ms or less (what
`nus.connect()` passes on a board), calls WinRT's
`RequestPreferredConnectionParameters(ThroughputOptimized)` through bleak's
private `_backend._requester`, as the P4 measurements did. On the S3 it made
no difference to nus throughput.

After a disconnect bleak sets `client.services` to `None`, so every client call
checks the connection first and raises `DisconnectedError`.

## How winrt and bluez get there

Both subclass `BleakBLE`, so the central side is bleak's, unchanged, and add a
GATT server from the operating system: WinRT's `GattServiceProvider` through
the `winrt-*` packages bleak already installs on Windows, and BlueZ's
`GattManager1` and `LEAdvertisingManager1` through `dbus-fast`, which bleak
installs on Linux. They're separate modules because the two servers share
nothing but the contract. `bledev.auto` picks `winrt` on Windows and `bluez`
on Linux whenever bleak imports, and `bleak` everywhere else.

WinRT raises its requests on its own threads. The backend hands each one to the
event loop with `call_soon_threadsafe` and answers them one at a time, in the
order they arrived, per characteristic: with a task per request, a burst of
BLE-MIDI writes came out of order. Windows reports each advertisement start as
an abort with error `Success` before it reports it started, and its status
lags behind calls to start and stop, so the backend tracks which providers it
started itself. A `GattSession`'s `close()` leaves the link up, which is why
`Connection.disconnect()` raises rather than pretending.

BlueZ calls the exported objects' `ReadValue`, `WriteValue`, `StartNotify` and
`StopNotify` on the event loop. A notification is a `PropertiesChanged` signal
on the characteristic's `Value`, which BlueZ sends to every subscriber; that's
why `notify(connection)` refuses while more than one central is connected.
Connections come from `Device1`'s `Connected` property, matched while the
adapter advertises.

## Reconnecting fast

The REPL gate once failed one run in five: bleak couldn't subscribe on a
connection made 1.5 s after the last one closed. A loop of rapid reconnects
from the laptop ([`tests/bledev_board/reconnect_loop.py`](https://github.com/PyDevices/omnipython/blob/main/tests/bledev_board/reconnect_loop.py): log in, run a line,
close, wait 1.5 s) caught it at about one cycle in fifty, always the same
way. bleak's connect returned in 70-440 ms where a real one takes 1.7 s or
more, Windows reported the device connected and the GATT session active, the
board never saw a connection (its IRQ log shows it advertising throughout),
and the first GATT operation hung until Windows reported a drop about nine
seconds later.

It went away with the REPL's output fixes (below): against `bledev-host`'s
`repl.py` the loop failed 7 times in 465 cycles; against the fixed one, 0 in
270, 150 of them with the retry switched off. We haven't found how the
board's old timer handling produced a connection Windows believed in and the
board never saw, so `bledev.connect_and_set_up()` stays as the defence: it
bounds the setup at 4 s and tries again, up to three times. `nus.connect()`
and `midi.connect()` use it, and the contract checks both the retry and the
giving up.

## How cpble gets there

`_bleio` has no events and no async calls. An adapter hands out objects you
look at: `adapter.connections`, `connection.connected`, and the ring buffers
that a characteristic's writes and notifications land in. So every wait in
cpble is a poll of one of those every `POLL_MS` (5 ms), and each blocking
`_bleio` call (connect, discovery, a read, a write with response, making a
subscription) holds the event loop until the radio answers, which is one or
two connection intervals. A scan runs in slices of `SCAN_SLICE_MS` (100 ms),
each a fresh `start_scan()`, with the scan response merged per address the
way aioble does.

**Where writes land.** A characteristic with notify or indicate gets a
`_bleio.PacketBuffer`, which keeps each write whole but takes writes only from
the central that subscribed, and only after it did (it learns the connection
from the subscribe event). Any other writable characteristic gets a
`_bleio.CharacteristicBuffer`, a byte stream: with `capture=True`, each
`written()` returns what arrived since the last one. Both drop the oldest data
when full and don't say so; cpble checks the stream buffer's fill and raises
when it's full, and sizes it at 32 KB (`stream_buffer`), which is nus's whole
16 KB echo phase in flight twice over. `_bleio` doesn't say which central
wrote, so `written()` names the most recent live one. Every server value
buffer is `_bleio`'s largest (512 bytes), because a notification can't be
longer than the value's buffer; `max_len` is kept in Python (`read()` gives
the first `max_len` bytes) rather than by `_bleio` refusing the write.

**Notifications, and a stall in CircuitPython 10.3.** `PacketBuffer.write()`
on the ESP32 keeps a packet it couldn't get an mbuf for and retries it on the
next `BLE_GAP_EVENT_NOTIFY_TX`. NimBLE sends that event when a notification is
handed to the stack, not when it leaves the radio, so a packet that never got
an mbuf never produces one, and the next write that doesn't fit beside it
waits inside `_bleio` until the central disconnects. Writing 253-byte packets
back to back from the laptop gate delivered 10 (2,530 bytes) and stopped,
every time. So cpble passes each notification as the `header=` of an empty
write: `_bleio` copies a header only into an empty packet, and a write of
nothing never waits, but it does retry what's pending. A return of 0 means
the previous packet is still there, and `notify()` raises `BusyError`; nus,
midi and the other async senders wait and try again. A task retries the last
packet every 5 ms for 5 s after it was sent, since nothing else will. It
also keeps notifications whole, where `PacketBuffer` would append the next
write to a pending packet.

**And a hard fault.** When NimBLE refuses a notification after the mbuf was
allocated (it needs one more for the ATT header), `PacketBuffer` "undoes" by
switching to a second outgoing buffer that it allocates only for indications
and writes, and the next write copies into a null pointer: the board restarts
in safe mode. cpble can make it rarer but not impossible: notifications are
held to 244 bytes (the reported MTU is at most 247, one link-layer packet, so
NimBLE never fragments), and each new connection gets fresh packet buffers.
The fix belongs in CircuitPython, in the Espressif port's
`_bleio/PacketBuffer.c`.

**Discovery mode, without a hand.** CircuitPython's own file service
advertises to a new host only in discovery mode, which normally takes a reset
pressed during the blue blink after boot. The supervisor marks that second in
an RTC register that survives a reset, and `memorymap` can write that register
on the S3 (`RTC_CNTL_STORE0_REG`, 0x60008050), so
[`tests/bledev_board/cpfiles_discovery.py`](https://github.com/PyDevices/omnipython/blob/main/tests/bledev_board/cpfiles_discovery.py) writes the mark and resets. It also
erases the board's bonds, as the button would.

**What `_bleio` can't do here**, on the ESP32 port: a central can't receive
indications (they're ignored below Python); pairing is "just works" only
(`authenticated=True` raises); there are no long reads; the MTU is fixed at
256 when CircuitPython is built; a service has at most 10 characteristics and
a characteristic at most 2 descriptors; a peripheral doesn't learn its
central's address; `Service.deinit()` is the only way to take a service away,
which `register_services()` uses; and a read that times out inside `_bleio`
returns a full buffer as if it succeeded. A refused read or write comes back as
`BluetoothError("Unknown system firmware error: 261")`, NimBLE's 0x100 plus
the ATT code, and cpble turns that into `GattError(5)`.

## How the REPL gets there

The REPL has to work when nothing runs asyncio, at the `>>>` prompt, so the
board side doesn't use bledev's adapter at all. It registers the Nordic UART
service with the raw API (the RX buffer in append mode, 1 KB), advertises
with `gap_advertise`, and does everything else from an IRQ handler it adds to
aioble's dispatcher (or sets itself, with no aioble). `os.dupterm` reads a
`_Stream` whose `readinto` returns `None` when empty, because 0 means end of
stream and detaches it. Output goes out as notifications of `mtu - 3` bytes,
and what the controller can't take yet is retried every 5 ms by one periodic
`machine.Timer`. A program printing faster than the link carries waits in
`write()` up to two seconds, then drops the excess, because `print()` can't
fail.

Two ways that retry went wrong, both found by printing a 16,890-character
list over the link (the REPL gate does this):

- **A doubled chunk and a lost one.** The timer's callback runs between the
  main program's bytecodes, so it could land inside a `flush()` that
  `print()` had started: both sent the same chunk, then both trimmed it, and
  the next chunk never went out. Five prints out of five came back corrupt.
  `flush()` returns at once if it's already running.
- **A panic.** The retry used to be a one-shot timer re-armed on every write.
  On the esp32, `Timer.init()` on a virtual timer whose alarm is being
  dispatched clears its handler first, so `esp_timer`'s task on the other
  core calls a NULL function (`InstrFetchProhibited` in
  `timer_process_alarm`). It took the board down twice in about 45 long
  prints. The timer is started once and never re-armed; 60 long prints
  afterwards, no panic and every byte intact.

Ctrl-C works because the IRQ calls `os.dupterm_notify()` whenever a write
contains 0x03; dupterm then reads it and raises `KeyboardInterrupt`, even in
a loop that never reads stdin. It only does that for 0x03: notifying on every
write would push pasted input through the 260-byte stdin ring, which drops what
doesn't fit.

The password stage is `repl.Login`, pure and checked on both interpreters.
Nothing reaches dupterm until the password line matches, and anything sent
after a wrong one is dropped. The prompt goes out at connect, but a client
that subscribes after connecting misses it, so an empty line asks for it again
without using up the attempt.

The REPL takes a free dupterm slot on login (the highest, so slot 0 stays
WebREPL's where there are several) and frees it on disconnect. The ESP32 has
one slot, and WebREPL holds it while it has a client, so a BLE login then gets
`The REPL is busy` and a disconnect, the way WebREPL turns away a second
client. Both servers run side by side; they only take turns at the REPL.

## How file transfer gets there

The protocol is Adafruit's (`supervisor/shared/bluetooth/file_transfer.c` in
CircuitPython; the spec is in Adafruit_CircuitPython_BLE_File_Transfer):
service `0xFEBB`, a version characteristic reading 4, and one transfer
characteristic the client writes commands to and the board answers with
notifications. bledev adds one characteristic, `ADAF0300-...`, for the
password; CircuitPython has none, which is how a client tells the two apart.

`FileServer` is the protocol without a radio. It takes the client's bytes in
any split, handles every command whose bytes have all arrived (several may
share a write), and queues answers. Its `packet(n)` never lets one
notification carry the end of one answer and the start of the next, because
Adafruit's client expects a header at the start of a notification. A read's
data is streamed from the file one packet at a time rather than loaded.

On the board it's a second service on `repl`'s raw-API server, registered
in the same `gatts_register_services` call as NUS, because a registration
replaces everything before it. What differs from CircuitPython, and why:

- **File work runs on the main thread, not in the IRQ.** On the esp32 port
  the BLE IRQ runs in NimBLE's host task (`MICROPY_PY_BLUETOOTH_USE_SYNC_EVENTS`),
  whose stack is a few KB. The first build handled commands there, and a
  recursive delete took the T-Embed down. The IRQ only appends the bytes
  to an inbox and `micropython.schedule()`s the work; the REPL's 5 ms timer
  picks up anything the schedule queue refused. A disconnect in the IRQ only
  flags the reset, so the main thread never has a file closed under it.
- **The window is 4 KB, not a 512-byte sector.** Each `WRITE_PACING` offers
  `min(remaining, window)` bytes, so 20 KB is five round trips. The transfer
  characteristic's append buffer is `2 * window + 64`, room for a window, its
  header and the next command, and the board never offers more than that.
- **Truncation.** MicroPython's files can't truncate, so a write at an offset
  that leaves the file shorter copies the part that stays.
- **Locked means answered.** Before the password, every command gets its own
  answer shape with status `0x80`, so a client can parse the refusal rather
  than time out.

Adafruit's own client (`adafruit_ble_file_transfer.FileTransferClient`, with
`_bleio` stubbed and a stand-in PacketBuffer that hands it one `packet()` per
read) wrote, read, listed, moved and deleted against `FileServer` at MTU 247,
and wrote and read at MTU 23; its `listdir` can't run at 23 against any
server, because it reads a 28-byte header into one 20-byte packet. That was
a one-off check, not a test in the tree. The client against a real
CircuitPython board, whose service pairs, is described under
[How cpble gets there](#how-cpble-gets-there).

## How HID gets there

`bledev.hid` is two halves over one parser. `bledev.hidreport` reads a report
descriptor into `Report`s of `Field`s (bit offset, size, count, flags,
usages, logical range) and a `Decoder` diffs successive input reports into
events. It imports `events` and `keys` and nothing from Bluetooth.

**The keyboard decoder is usbif's, event for event.** Same order (modifier
releases, key releases, key presses, modifier presses, the new modifier mask
on all of them), same fields (`scancode` is the HID usage, `window` is
`None`), same rollover rule. [`tests/test_bledev_hid.py`](https://github.com/PyDevices/omnipython/blob/main/tests/test_bledev_hid.py) feeds 3,000 random
boot reports through both decoders when usbif's checkout is beside this one,
and they must agree. It found one difference on its first run: the ISO "# ~"
key (usage 0x32), which SDL calls `#` and usbif leaves unmapped. There is
one table, `keys.hid_keycode`, and both decoders use it: the key's code comes
from the same place whether it arrived over USB or Bluetooth.

**Mice** are the mouse and pointer collections. Relative X and Y add up to a
pointer position that starts at (0, 0) and stays inside `bounds` if you give
the decoder one; an absolute pointer's logical range spans the bounds.
Buttons are renumbered to SDL's (HID's 2 is right, SDL's 3). The wheel
(desktop 0x38) is the event's `y` and AC Pan (consumer 0x238) its `x`, which
is what the desktop's `MOUSEWHEEL` carries. usbif has no mouse decoder to
match: it hands a hosted mouse's reports to Python raw.

**Axes, hats and buttons** come only from joystick, gamepad and multi-axis
collections. Axes are
numbered by usage (desktop X to wheel, then the simulation page), so an Xbox
controller's sticks are 0 to 3 and its triggers 4 and 5. Every axis starts
at 0.0 and moves only when its value changes, as SDL's do.

**Descriptors, encryption and pairing** were added to the contract for HID.
A Report characteristic says which report it carries in its Report Reference
descriptor (0x2908), and HOGP gives the report ID nowhere else, so the host
needs `ClientCharacteristic.descriptor()`. A `Characteristic` can be
`encrypted=True`, and `Connection.pair()` encrypts a link. The host pairs
only after a read fails with insufficient encryption or authentication,
which is how a real keyboard asks. mpble pairs through `bledev.security`
("just works", `io=3`, unless a passkey is given); `ble.enable_bonding()`
loads the bond store (NVS on an ESP32, see
[how pairing gets there](#how-pairing-gets-there)) and turns bonding on, and
it has to run on both sides,
because the side that didn't start pairing stores keys too.

**MicroPython has no long read.** `gattc_read()` is one ATT Read, so a board
central gets at most `mtu - 1` bytes of any value. The host exchanges the MTU
up to 247 before reading the Report Map (246 bytes fit), and a map that fails
to parse at that length raises an error that says why. Our own map is 162
bytes; an Xbox Series controller's is 283, so a board can't host one until
MicroPython grows a long read. bleak reads long values itself, and the
fake's `long_reads=False` models the board.

**The peripheral's identity comes from its functions.** Name, appearance and
PnP product ID are derived from which of keyboard, consumer control and
gamepad it serves, so a host that cached one set never sees another set
under the same identity. The PnP vendor is the Bluetooth SIG's test company
ID (0xFFFF), because we have no vendor ID of our own.

**A laptop can't see a HID service.** Windows hides 0x1812 from apps: bleak
lists the board's GAP, GATT, Battery and Device Information services and a
22-handle gap where the HID service sits (measured against the P4). Chrome's Web Bluetooth blocklist hides it too. So
`Peripheral(service_uuid=hid.INSPECT_SERVICE)` serves the same
characteristics under a vendor UUID, and `Host(service_uuid=...)` reads them
there; that is how the laptop checks a board's HID side, with the same code
a board host runs. No host treats a board serving that UUID as a keyboard.

The host writes the keyboard's LED report once it has subscribed, as Windows
does. `Peripheral.leds()` returns those writes, which is how the gate knows
the host is listening, and how it times a round trip.

## How pairing gets there

`bledev.security` is the board side. aioble pairs, but it leaves three gaps,
and all three bit on the LCD-7:

- **The passkey step is unhandled.** aioble's `_IRQ_PASSKEY_ACTION` handler
  only logs. bledev answers it from the IRQ itself, as NimBLE's own examples
  do: a random six-digit passkey for `DISPLAY` (the board shows it), the
  caller's passkey for `INPUT` (a board as central), and numeric comparison
  through `confirm()`. Only the drawing waits for the main thread.
- **Saving keys through the scheduler fails.** aioble stores a secret in the
  IRQ and saves it with `micropython.schedule()`, which raises when the queue
  is full. The queue *is* full whenever a scheduled callback runs long while
  a timer keeps queueing: drawing the passkey (77 ms on the LCD-7) inside a
  scheduled callback while the REPL server's 5 ms timer ticks did it. The
  exception went back into NimBLE as a failed key store, and pairing stopped
  after the first key, with the host believing it had paired. bledev
  handles `_IRQ_GET_SECRET` and `_IRQ_SET_SECRET` ahead of aioble and writes
  the store inline when the queue is full (ESP-IDF's own NimBLE writes NVS
  from its host task too). Anything else deferred from an IRQ goes through
  `security.poll()` when the queue is full, which the REPL server calls every
  tick.
- **The store is a file.** bledev keeps the keys in NVS on an ESP32
  (`NVSStore`, namespace `bledev`, one blob: type, key length, key, value
  length, value, repeated) and in aioble's `ble_secrets.json` elsewhere.
  It takes over aioble's `load_secrets` and `_save_secrets`, which aioble
  looks up at call time. The store should be loaded before the radio starts,
  because NimBLE reads the board's IRK then; `repl.start()` does that. When
  the radio is already on, the board makes a new IRK, which costs nothing
  while it advertises its public address.

**Why NVS.** A filesystem reformat, a mip reinstall and "delete everything"
are routine on these boards, and a board that silently forgets its bonds
leaves every paired host with keys that no longer work. NVS survives all of
those and is lost only to a full chip erase, which is rarer and already means
setting the board up again. Not measured: an actual filesystem reformat with a
bond in NVS; what was shown is
that the bond lives outside the filesystem (no file is written) and survives
hard resets.

**The server.** With `pairing=`, the REPL's RX and the file service's
transfer and `AUTH` characteristics get `_ENC` flags (just works) or `_ENC`
plus `_AUTHN` flags (passkey, numeric), so NimBLE refuses an unpaired host
before bledev sees the request, answering ATT 0x05. bledev checks the link's
state from `_IRQ_ENCRYPTION_UPDATE` as well. `AUTH` is served even without a
password, so the table depends only on `console` and `files`, and reads 1
once pairing has unlocked it. With the password gone, the REPL opens on the
client's first line (`_Open`), so the client sees one `>>>`. A link not
paired within `PAIR_WITHIN_MS` (30 s) is hung up on, so a host that never
pairs can't hold the board's one connection. The 30 s start again when the
stack asks about a passkey (`security.passkey_asked()`): Android asks "Pair?"
before it shows the passkey box, and a person who reads that question for
twenty seconds would otherwise have ten left to type six digits. A failed
pairing isn't hung up on at once: the host would only see a dropped link, not
why.

**The laptop.** bleak 3.0.2's WinRT `pair()` accepts only `CONFIRM_ONLY`,
so bledev.bleak runs WinRT's custom pairing itself: `CONFIRM_ONLY` and
`PROVIDE_PIN`, the PIN supplied behind a deferral so the passkey provider can
be slow (a person, or the gate reading the board's console). No system dialog
appears. WinRT reports `protection_level_used` as `NONE` even after a passkey
ceremony, so bledev takes "a PIN was asked for and given" as the evidence of
an authenticated link; the board's own state agrees (authenticated, 16-byte
key). A device Windows already has paired is left alone: Windows encrypts with
the stored keys when a protected characteristic is first used.

**A lost bond, seen from the host.** When the board has forgotten the keys,
Windows' encryption fails and the link drops two milliseconds later (the
board's log: `GET_SECRET` misses, `ENCRYPTION_UPDATE` with encrypted 0,
disconnect). After a board resets, Windows also hands out links the board
never sees, for a few seconds. From the host the two look the same, so
`connect_and_set_up` backs off between attempts and, when every attempt
drops after encrypting with stored keys, says both.

## webble

`webble` reaches the page the way `audiodev.web_audio` does, through the `js`
module, which Pyodide and MicroPython's WebAssembly build both have. The
runtimes disagree on how Python values cross into JavaScript, so everything
goes through a few helpers made once with `js.Function.new()`: strings,
numbers and opaque objects cross, and bytes cross as hex. JS errors come back
as each runtime's `JsException`, and `_translate()` maps them by name.

What it takes to meet the contract in a browser, all found on hardware:

- **Chrome on Android never matches a `name` filter against a scan
  response.** A board advertising nus's 128-bit UUID has its name pushed
  there, so `find(name=, service=)` filters on the service alone and checks
  the pick's name afterwards. The check caught two wrong picks while the S3s
  were also advertising nus.
- **The MTU is invisible.** Chrome on Android asks for 517 right after
  connecting (logcat: `configureMTU() mtu: 517`, answered with 247 by a
  board), and Windows negotiates on its own, but neither tells the page.
  Writes are sized to `WebBLE(mtu=)`, default 23. A write longer than the
  link carries is cut short on Android without an error, which is what the
  mock models and `test_bledev_web.py` plants.
- **First connects fail.** Android gives status 133 / HCI 0x3E ("failed to be
  established") on about half the first attempts to the P4, so `_connect()`
  tries three times. One gate run needed two retries.
- **One GATT operation at a time.** Chrome rejects a second while one is in
  flight, so each connection serialises them behind a lock.
- **Discovery is slow the first time.** The browser walks the whole GATT
  table on the first request, which took longer than nus's 2 s from Windows,
  so discovery timeouts have a 10 s floor.
- **MicroPython's asyncio can't `wait_for()` a JS promise**, only a
  coroutine, so promises with a timeout are wrapped in one.

**The gate** is [`tests/bledev_web/`](https://github.com/PyDevices/omnipython/tree/main/tests/bledev_web): `gate.py` runs nus's three 16 KB phases
against `nus_gate_server.py` on a board, on three pages (`pyodide.html`,
`mpy.html`, `wasm.html`) served by `serve.py`, which also collects what the
pages log. `?mock=1` swaps in `mock_bluetooth.js`, and
[`tests/test_bledev_web.py`](https://github.com/PyDevices/omnipython/blob/main/tests/test_bledev_web.py) runs that in headless Chromium with two planted
faults. Against a board, the chooser is the only human step, and both ends
of it can be automated:

- **Android:** `adb reverse tcp:8765 tcp:8765` makes the page `localhost` on
  the phone, `adb shell input tap` presses the page's button (a real user
  gesture), and `uiautomator dump` finds the device's row and the Pair
  button in the chooser. Chrome needs the Nearby devices permission, and
  Android's `DeviceAccess` events never fire.
- **Desktop Chrome:** start it with `--remote-debugging-port` and its own
  `--user-data-dir`, click the button with `Runtime.evaluate(userGesture=true)`,
  and answer `DeviceAccess.deviceRequestPrompted` with
  `DeviceAccess.selectPrompt`. No person is needed at all.

Restart the board's server with a hard reset: after a Ctrl-C, a new
`nus.serve()` on the P4 twice said it was advertising while nothing was on
the air.
## The checks

Every behaviour above has a check, and each check has a planted fault that
must make it fail. Over the fake, on both interpreters:
[`tests/bledev_contract.py`](https://github.com/PyDevices/omnipython/blob/main/tests/bledev_contract.py)
is the contract, run by [`tests/test_bledev.py`](https://github.com/PyDevices/omnipython/blob/main/tests/test_bledev.py)
with five planted faults (a dropped, corrupted, reordered, truncated or
overwritten packet). A host backend that has a fake peripheral to talk to can
reuse most of it by building its adapters there instead; if you change the
fake, keep the plants failing. The pairing and file-transfer protocols have
their own scripts and plants beside it.

Over a real radio, the scripts in
[`tests/bledev_board/`](https://github.com/PyDevices/omnipython/tree/main/tests/bledev_board)
pair a serving script on one board with a client on a second board, a laptop
or a browser. Its README lists each pair, what it checks, and how to run it.

## The rules every backend keeps

These hold on every backend. The fake enforces the strict version of each, so
code that passes its tests keeps them:

- **One packet is `connection.mtu - 3` bytes.** A notification or write
  longer than that raises `BLEError`. Real NimBLE would cut the tail off and
  say nothing. `exchange_mtu()` asks for more, and the smaller side wins.
- **A characteristic holds `max_len` bytes**, 20 by default, as on
  MicroPython. Raise it for anything that takes MTU-sized writes. The fake
  raises on a longer write; a real board keeps the first `max_len` bytes and
  says nothing (measured: 29 bytes sent, 20 kept).
- **Nothing is dropped quietly.** Notifications and captured writes queue in
  order. If a queue overflows because you stopped reading, the next
  `notified()` or `written()` raises `BLEError` instead.
- **`notify()` can say `BusyError`.** It's synchronous, like aioble's, and
  the transmit buffers are finite. Wait a moment and send again, or use nus,
  which does. Every async send waits for room itself.
- **Subscribe before you expect notifications.** Browsers and bleak deliver
  nothing until you do, and the fake matches them.
- **Discovery comes back in the server's order** (by handle).
- **A dropped link ends pending client calls with `DisconnectedError`,** and
  anything that arrived before the drop is still delivered first. A server's
  `written()` serves every connection, so it doesn't end on a disconnect; give
  it a `timeout_ms` or cancel it. With `capture=True`, `written(timeout_ms=0)`
  returns a write that's already queued, or raises `BLETimeoutError` at once.
- **Every timeout is `BLETimeoutError`,** and every error is a `BLEError`:
  `UnsupportedError`, `DisconnectedError`, `BLETimeoutError`, `BusyError`,
  `GattError` (with `.status`).
- **`UUID` is one value everywhere.** `UUID(0x180F)`, `UUID("180f")` and the
  128-bit string are equal. `str()` is always the 128-bit form, which bleak
  and browsers use, and `to_bytes()` is the little-endian wire form.

## Details the guide leaves out

Behaviour an app meets now and then, which the [Bluetooth LE guides](../guides/bluetooth-le.md) leave short.

### The REPL over Bluetooth

Any terminal that speaks Nordic UART works too: send an empty line, and the
board answers `Password: `. A wrong password gets `Access denied` and a
disconnect, and nothing sent with it reaches the REPL. The link isn't
encrypted, as with WebREPL, so someone nearby with a sniffer can read the
password, unless you [pair](../guides/bluetooth-le-services.md#pairing-and-bonding).

It runs beside WebREPL. On a board with one console slot (the ESP32), the
two take turns: while a WebREPL client is connected, a Bluetooth login gets
`The REPL is busy` and a disconnect, the way WebREPL turns away a second
client, and the other way round.

While it runs, the REPL owns the radio: it registers its own service and
advertises whenever nobody is connected. Call `bledev.repl.stop()` to give the
radio back to your app.

### Files over Bluetooth

It's locked the way the REPL is. CircuitPython uses pairing; bledev uses the
REPL's password by default (or [pairing](../guides/bluetooth-le-services.md#pairing-and-bonding)), sent to one
extra characteristic, and until it's right
every command is refused. One attempt per connection, and a wrong one is hung
up on. Logging in to the REPL over the same connection unlocks files too,
which is what [mcuctl](https://github.com/PyDevices/mcuctl) does. The protocol
has no checksum beyond the radio's own, so check what matters (mcuctl compares
SHA-256 after every transfer).

`start()` serves the REPL beside the files; `console=False` serves files
alone. It's MicroPython only, and like the REPL it owns the radio while it
runs.

How fast: 20 KB from a laptop to an ESP32-S3 in about 2 s and back in about
1.5 s, or about 1.2 s and 0.5 s when the laptop connects with
`priority="throughput"`.

### MIDI ports

The port is the contract the [`midiports`](https://github.com/PyDevices/omnipython/blob/main/packages/midiports/README.md) package
documents: `read(nbytes)` returns MIDI bytes or `None` and never blocks,
`readinto(buf, nbytes)` does the same into your buffer without allocating,
`any()` says how many bytes are waiting, and `write(buf, nbytes)` sends.
Every message comes out whole, with its status byte, and a read takes only
the whole messages that fit. Give `adafruit_midi` an `in_buf_size` bigger than
your longest SysEx: its 1.6.0 parser throws away a SysEx that reaches it in
two reads.

If you'd rather have messages than bytes, with the sender's timestamp, use
`ts, message = await port.receive()` or `async for ts, message in port`.
Messages you write go out from a task, packed as many to a packet as fit, and
`await port.drain()` waits for them.

On a board, ask for the shortest connection interval when you connect:
`midi.connect(ble, name="synth", min_conn_interval_us=7500,
max_conn_interval_us=7500)`. The latency that buys is in
[How fast it goes](../guides/bluetooth-le.md#how-fast-it-goes).

### HID host and bonding

A keyboard that wants an encrypted link gets one: the first read it refuses
pairs the link ("just works", no passkey) and tries again. On a board, call
`ble.enable_bonding()` once before connecting so the keys are kept, and the
next connect doesn't pair from scratch. The keys live in NVS on an ESP32
(see [where the keys live](../guides/bluetooth-le-services.md#pairing-and-bonding)), so a full chip erase
forgets them, and a keyboard that remembers the board may then need putting
back into pairing mode.

### HID device details

Install `adafruit_hid` on MicroPython with
`mip.install("github:PyDevices/omnipython/bledev_hid")`: it fetches
Adafruit's files at a release tag, with one file patched so
`consumer_control` imports on MicroPython, and micropython-lib's
`__future__`. Each `send_report()` returns once the radio has the report,
waiting briefly if its buffers are full. The keyboard's LED report (Caps
Lock and friends) reaches `kb.led_on(Keyboard.LED_CAPS_LOCK)` the way it does
over USB.

`adafruit_hid` has had no gamepad since 5.0, so `bledev.hid_gamepad` gives
one in the shape of Adafruit's `hid_gamepad.py` example, for a
`Peripheral(ble, gamepad=True)`: `press_buttons()`, `move_joysticks()`,
`set_hat()`, and `set()` for everything in one report.

Its name, appearance and Report Map come from which functions you ask for,
the same way every time, because hosts cache a device against its identity.
Change the set, and a host that paired with the board before must forget it
and pair again. Pass `encrypted=True` to make hosts pair first, as real
keyboards do.

### HID presence key and the parser

**A paired phone as a presence key.** A phone reconnects to a bonded HID
device by itself whenever its Bluetooth comes back in range, so a board can
tell when you walk up, with no app on the phone. Pair once from the phone's
Bluetooth settings, then wait for each arrival:

```python
ble = bledev.auto.adapter()
ble.enable_bonding()
per = hid.Peripheral(ble, keyboard=False, mouse=False, encrypted=True, name="Presence")
while True:
    conn = await per.serve()                # the phone is here
    screen_on()
    await conn.disconnected()               # the phone has gone
    screen_off()
```

Android gives the phone a new random address over time, so watching
advertisements for a known address doesn't work; the bonded reconnect does.
`conn.encrypted` is still False at the moment `serve()` returns. A bonded
phone re-encrypts the link about 0.3 s later, so wait for it before you treat
the visitor as the phone you paired.

**Don't pair a test board with the computer you're testing from.** Once
paired, Windows and phones use it as a real keyboard, and it types into
them.

The parser underneath, `bledev.hidreport`, knows nothing about Bluetooth.
Give it any HID report descriptor and it decodes that device's reports, so a
USB host can use it the same way. How it numbers axes, what it does with a
rollover, and what a board central can't read are in
[bledev-internals.md](../how-it-works/bledev-internals.md#how-hid-gets-there).

### A changing address, watching it

A scanner sees the new address each time the old one expires, so keep scans
going for a quarter of an hour to watch it change. Closing the adapter puts the
mode back to the stack's default.

### Pairing, in detail

The first time a computer connects, the board draws a six-digit passkey on its
screen (and prints it to the console) and the computer asks for it. The board
asks for pairing as soon as a host connects, so a phone puts up its pairing
dialog straight away; that's how Workbench in Chrome on Android pairs. After that
the two are bonded: they reconnect encrypted, with no passkey, until one of
them forgets. `password=False` means the passkey is the only lock; keep a
password as well if you like.

From a laptop or another board, pair when you connect, and pass the passkey,
or a function that asks for it:

```python
link = await bledev.repl.connect(ble, name="rack", pair=True, passkey=lambda: input("Passkey: "))
files = await bledev.filetransfer.connect(ble, name="rack", passkey=ask)    # pairs when the board asks it to
```

On Windows that's WinRT's own pairing, with no system dialog, and it pairs
before the link comes up. Once a link is up, Windows answers the board's
request to pair on its own, out of sight, and pairing then fails without asking
for the passkey, so on Windows pass `pair=True` rather than waiting for the
board to ask. To pair a
computer once for tools that don't pair themselves (mcuctl),
`python -m bledev.bleak pair rack` asks for the passkey in the terminal, and
`python -m bledev.bleak unpair rack` undoes it. Windows Settings, Add device,
works too.

Just works on its own would let anyone in range pair and get a REPL, so it
needs the password too; what it adds is that nobody sniffing can read the
password or the session. A board draws the passkey on `board_config.display_drv`;
pass `show(passkey)` and `hide()` to put it somewhere else.

A board's name, and the services it serves, follow from what you start: the
name you pass, or [the board's name](../guides/board-name.md) when you pass none, is both
the advertised name and the one a paired computer lists
(the GAP name, which would otherwise be MicroPython's "MPY ESP32"), and the
same `console` and `files` give the same table every time, whatever the lock,
because hosts cache a paired device's table. Serving something else on the same
board (HID, say) changes it under the same address, and MicroPython doesn't tell
bonded hosts, so a host that kept the old table may need the board unpaired and
paired again.

### Standard services

Register your own service in the same call: `register_services()` replaces what
came before. The [HID peripheral](../guides/bluetooth-le-services.md#keyboards-mice-and-gamepads-hid) serves
Battery and Device Information itself. These are plain GATT tables, so any
backend that can be a peripheral serves them. `examples/bledev_battery_simpletest.py`
shows both running.

The cycling and running services each have a control point that a central
writes and the board answers by indication. Run `sensor.run()` as a task to
answer it. MicroPython waits for the central's acknowledgement; CircuitPython
sends the indication but `_bleio` doesn't report the acknowledgement, so
`indicate()` returns once it's queued. Each module's docstring lists what the
measurement carries and which flags it sets, and each has an example under
`examples/` named `bledev_<service>.py` that a phone fitness or sensor app can
read.

### File transfer speed and offsets

`write()` takes an `offset`, and the file ends after what you wrote.
`read()` takes one too. The board paces every write with a free-space count,
so it never receives more than it can hold.

How fast: 20 KB from a laptop to an ESP32-S3 in about 2 s and back in about
1.5 s, or about 1.2 s and 0.5 s when the laptop connects with
`priority="throughput"`.

### BLE-MIDI packets

The packet format lives in `bledev.midi_codec`, pure Python with no
imports: timestamps, running status, SysEx split across packets, and clock
slipped into a SysEx. Its test vectors ([`tests/bledev_midi_vectors.json`](https://github.com/PyDevices/omnipython/blob/main/tests/bledev_midi_vectors.json)) were
worked out by hand from the specification, and every interpreter checks
against the same file.
