# bledev board checks

**Pairing, without a radio**, on both interpreters: [`tests/bledev_pairing.py`](../bledev_pairing.py)
serves the file service over the fake the way CircuitPython does (encrypted,
no `AUTH`) and the way a passkey board does, and checks that clients pair when
they must, refuse what they must, and move 20 KB intact; plus the NVS blob
codec. [`tests/test_bledev_pairing.py`](../test_bledev_pairing.py) runs four plants, each of which must fail.

**The file-transfer protocol**, on both interpreters:
[`tests/bledev_filetransfer.py`](../bledev_filetransfer.py) wires the client to a `FileServer` through a
loopback that splits both directions at the MTU (23, 185 and 247, windows
from 512 to 4096), and [`tests/test_bledev_filetransfer.py`](../test_bledev_filetransfer.py) runs it with a
flipped bit and a lost packet, each of which must fail.

**Against the fake**, on both interpreters: [`tests/bledev_contract.py`](../bledev_contract.py).
Its `pair()` and `nus_pair()` helpers build two fake adapters. A host backend
that has a fake peripheral to talk to can reuse most checks by building its
adapters there instead. [`tests/test_bledev.py`](../test_bledev.py) also runs five planted faults
(a dropped, corrupted, reordered, truncated or overwritten packet), and each
must fail the contract; if you change the fake, keep that true.

**Over a real radio**, [`tests/bledev_board/`](.). Run the serving script with
`mcuctl run` on one board and the other with `mcuctl probe --capture` on a
second, or run the client on the laptop with the Windows Python:

```bash
PYTHONPATH="$(wslpath -w lib)" python.exe "$(wslpath -w tests/bledev_board/gatt_central.py)"
```

The serving scripts have a `PLANT` switch, and a planted run must fail:

| Scripts | What they check |
|---|---|
| `gatt_peripheral.py` + `gatt_central.py` | The contract over the air: find, MTU exchange, discovery order, read, 200 notifications in order, 100 captured writes in order, the MTU refusal, an indication, a disconnect from the far side |
| `gatt_peripheral.py` + `gatt_latency.py` | Per-operation latency of reads and writes-with-response, with the stall count |
| `nus_server.py` + `nus_client.py` | 16 KB up, down and echoed over nus, byte for byte, timed. On a laptop, `--fast` asks for throughput parameters and `--plant` flips a bit |
| `repl_server.py` + `repl_client.py` | The REPL: the right password evaluates `123 * 456`, a wrong one sent with code that would create `/pwned` is refused and hung up on and the code never runs, and Ctrl-C stops `while True`. `repl_server.py` runs from `/main.py`, because mcuctl soft-resets the board, which turns Bluetooth off |
| `midi_server.py` + `midi_client.py` | BLE-MIDI. `gate`: 1,000 mixed messages up, checked by the server, then down, checked by the client; `--plant` on the client and `PLANT = "drop"` or `"flip"` on the server must FAIL. `latency`: note-on round trips through an echo, `--fast` for a 7.5 ms interval (throughput parameters on a laptop). The server also runs on a Windows or Linux laptop through `bledev.auto`, under the PC's own name on Windows; give the client `--service` to find it by the MIDI service instead of the name. A board client reads its arguments from `/midi_client_args.py` |
| `reconnect_loop.py` (laptop) against `repl_server.py` | Rapid reconnects: log in, run a line, close, wait 1.5 s, N times; `--no-retry` turns `connect_and_set_up`'s retry off |
| `improv_server.py` + `improv_client.py` | Improv: `--wrong` must get "unable to connect" and a return to "authorized"; without it, on a board, the network comes from that board's own `secrets.py` and must end "provisioned" with a URL |
| `coex_server.py` + `tcp_pull.py` + `nus_client.py` | Wi-Fi and BLE on one S3: a TCP source on Wi-Fi beside the nus gate |
| `files_server.py` + `files_client.py` | File transfer: no password and a wrong one refused; 20 KB up and down byte for byte and timed (`--runs N`, `--fast` for throughput parameters), a read at an offset, mkdir, listdir, move, a recursive delete. `--plant` on the client, or `PLANT = "flip"` on the server, must FAIL. `files_server.py` runs from `/main.py` |
| `hid_peripheral.py` + `hid_central.py` | HID: the device types `hid_script.py`'s text, chords, media keys and gamepad moves; the host's events must equal `hid_script.expected()` and spell the text. Then key-press round trips. `PLANT` drops one Shift. The host also runs on a laptop, where it refuses to pair |
| `bless_peripheral.py` + `bless_probe.py` | The laptop as a peripheral, through bless, probed by a board |
| `pair_server.py` + `pair_client.py` (laptop) | Pairing. `pair`: a passkey read off the board's console, then the REPL and 20 KB through the file service on the paired link. `reconnect`: from the bond, nobody asked for a passkey. `wrong`: a passkey one off must fail pairing and leave Windows unpaired. `unpaired`: every protected characteristic refuses reads and writes. Plants on the server: `forget`, `justworks`, `open`. `uart_say.py` reads the board's state without mcuctl's soft reset |
| `pair_server.py` + `files_pair_client.py` (board) | Board to board: the client pairs on its own, 20 KB both ways byte for byte, then reconnects from the bond. `plant="flip"` and `plant="nopair"` must FAIL |
| `nus_server.py` + `nus_client.py` | 16 KB up, down and echoed over nus, byte for byte, timed |
| [`tests/bledev_web/nus_gate_server.py`](../bledev_web/nus_gate_server.py) + a gate page | The same, from a browser through webble |

`gatt_peripheral.py` is also the peripheral to point a host backend at: it
advertises as `bledev-radio`, and a central steers it by writing commands.
