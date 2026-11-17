# Tested boards

A board is tested when someone has run its smoke test on the real hardware and
the board's config has a record of the run. This page lists those records.
It is written from them every time the docs build, so a board can't appear
here without one.

Any other board config still works to the extent its drivers do: it installs
from the untested index, and moves to the main index once someone adds its
record. [Board configs](board-configs.md) lists every config, tested or not.

## What a record says

The smoke test runs on the board. It checks that `board_config` imports, that
the display draws, that touch reads, and that each peripheral the config lists
answers: the factory builds one without raising. Roles that would take the
board away, such as `sleep`, are looked up but never called. A role the board
can't exercise at the time, such as `sdcard` with no card in the slot, is
skipped, and the record names it under **Left out**.

A record keeps the hardware, the firmware the board reported, the date and
each check that passed. It is the file `tested.json` beside the board's
`manifest.py`, written by `tools/mark_tested.py`. A record only says what ran
on the day it was made, on the firmware it names. "Passed" means every check
that ran answered, not that every feature of the board works.

## The boards

```{include} _tested-boards.inc
```

## Install one

A tested board's config is on the main index:

```python
import mip
mip.install("esp32-s3-touch-lcd-4_3", index="https://lib.omnipython.org")
```

A board with no record yet is on the untested index, which also carries what
it depends on:

```python
import mip
mip.install("pico-lcd-1.8", index="https://lib.omnipython.org/untested")
```

A config a tested board requires comes with it on the main index.

## Get a board on this list

Install its package from the untested index, run `tools/mark_tested.py` from a
checkout of [omnipython](https://github.com/PyDevices/omnipython) against the
board, and open a pull request with the `tested.json` it writes. Nothing is
written if a check fails. The steps are in
[CONTRIBUTING](https://github.com/PyDevices/omnipython/blob/main/CONTRIBUTING.md#add-a-board-or-a-driver).
