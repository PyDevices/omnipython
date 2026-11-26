# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Lazy end-device binding for board_peripherals -> board_config.

``board_peripherals.load_peripherals(globals())`` typically calls
``bind_lazy(ns, this_module)``. Apps normally use ``board_config.PERIPHERALS``
and attribute access instead of importing this module.

It also carries the one thing neither ``audiodev`` nor a board can answer on
its own: whether this machine's audio comes from a board or from a host
backend. See `pcm_out`.

And it is where the portable environment helpers live -- `env_get`,
`env_int`, `env_float`, `env_bool` and `env_set` --
because a board config, an app and every OmniPython package read their
``OMNIPYTHON_*`` settings through them, on interpreters where ``os.environ``
may not exist::

    from boarddev import env_int, env_set

    env_set("OMNIPYTHON_WIDTH", 800)   # before board_config is imported
    period = env_int("OMNIPYTHON_REFRESH_MS", 0)

This module imports nothing at module scope, so any package -- ``displaydev``
included -- can import from it without a cycle. Keep it that way.
"""


def bind_lazy(ns, peripherals_mod):
    """Install module ``__getattr__`` / ``__dir__`` on *ns* for lazy roles.

    Each name in ``peripherals_mod.PERIPHERALS`` maps to
    ``peripherals_mod.<name>``. Names in optional
    ``peripherals_mod.FACTORY_ROLES`` (a subset of ``PERIPHERALS``) are
    bound as the factory callable itself — first access does not invoke it.
    That is the audio pattern: ``board_config.audio_out(format=...)`` matches
    ``audiodev.auto.audio_out``. Every other role stays construct-on-getattr:
    first access calls the zero-arg factory, caches the object into
    ``ns[name]``, and further access hits the module dict (no ``__getattr__``).
    """
    roles = peripherals_mod.PERIPHERALS
    factory_roles = frozenset(getattr(peripherals_mod, "FACTORY_ROLES", ()))

    def __getattr__(name):
        if name not in roles:
            raise AttributeError("module has no attribute {!r}".format(name))
        factory = getattr(peripherals_mod, name)
        if name in factory_roles:
            ns[name] = factory
            return factory
        obj = factory()
        ns[name] = obj
        return obj

    def __dir__():
        names = list(ns.keys())
        for role in roles:
            if role not in ns:
                names.append(role)
        return sorted(names)

    ns["__getattr__"] = __getattr__
    ns["__dir__"] = __dir__


# The module constant each audio role publishes its capability as, beside
# ``role.capability``.
_CAPABILITY_NAMES = {"audio_out": "AUDIO_OUT", "pcm_out": "AUDIO_OUT", "pcm_in": "AUDIO_IN"}


def replace_role(peripherals_mod, name, role):
    """Put *role* in place of the board's *name* role, for every caller.

    Assigning ``board_peripherals.audio_out = ...`` already reaches code
    that calls ``board_peripherals.audio_out()``. This does that and keeps
    the rest of the board's story true, so code that discovers roles or
    reads a capability sees the replacement too:

    - *name* joins ``PERIPHERALS`` and ``FACTORY_ROLES``, so
      ``"audio_out" in board_config.PERIPHERALS`` is true and
      ``board_config.audio_out`` is *role* itself, never a call of it.
      Pass what callers should get: the factory for an audio role, the
      object for a constructed one such as ``sdcard``.
    - The board's ``AUDIO_OUT`` becomes ``role.capability``, or None when
      *role* has none, once neither ``audio_out`` nor ``pcm_out`` is the
      board's own; ``AUDIO_IN`` the same for ``pcm_in``. A capability with
      a ``wire`` describes the board's codec, and an app that drives that
      wire itself would otherwise keep playing there. Replace
      ``audio_out`` and ``pcm_out`` together: the board's own roles read
      ``AUDIO_OUT``, so it stays while either is left.
    - ``board_config`` gets the same changes when it's already imported.

    Call it in ``main.py`` before the app is imported, and before anything
    has opened the old role.

    Args:
        peripherals_mod: The board's ``board_peripherals`` module.
        name: The role's name, such as ``"audio_out"``.
        role: What callers get in its place.

    Example:
        import board_peripherals
        import boarddev
        from usb.host import audio

        boarddev.replace_role(board_peripherals, "audio_out", audio.audio_out)
    """
    import sys

    replaced = getattr(peripherals_mod, "_replaced_roles", None)
    if replaced is None:
        replaced = set()
        peripherals_mod._replaced_roles = replaced
    original = getattr(peripherals_mod, "PERIPHERALS", ())
    replaced.add(name)
    cap_name = _CAPABILITY_NAMES.get(name)
    if cap_name is not None:
        for other, other_cap in _CAPABILITY_NAMES.items():
            if other_cap == cap_name and other in original and other not in replaced:
                cap_name = None     # a board role still reads the constant
                break
    cap = getattr(role, "capability", None)
    targets = [peripherals_mod]
    config = sys.modules.get("board_config")
    if config is not None and config is not peripherals_mod:
        targets.append(config)
    for mod in targets:
        setattr(mod, name, role)
        for listing in ("PERIPHERALS", "FACTORY_ROLES"):
            names = getattr(mod, listing, None)
            if names is None and listing == "FACTORY_ROLES" and mod is peripherals_mod:
                names = frozenset()
            if names is not None and name not in names:
                setattr(mod, listing, frozenset(names) | frozenset((name,)))
        if cap_name is not None:
            setattr(mod, cap_name, cap)


# --- host-or-board audio resolution ---------------------------------------
#
# An app that runs on both a board and a desktop used to write this by hand::
#
#     try:
#         from audiodev.auto import audio_out
#         pcm = audio_out(fmt, latency="low")
#         pcm = getattr(pcm, "transport", pcm)     # which type did I get?
#     except (ImportError, OSError):
#         import board_config
#         pcm = board_config.audio_out.transport
#
# Both getattrs there are symptoms. The second is this question -- host or
# board -- and it cannot be answered inside ``audiodev``: importing board
# configs from there would cost audiodev its standalone-ness, and audiodev is
# meant to be usable with no OmniPython board tree at all. ``boarddev`` is
# already the seam between the two, so it answers here.
#
# Note it resolves to ``board_peripherals``, never ``board_config``. On some
# boards importing ``board_config`` initialises the display -- on the
# ESP32-P4 that means MIPI DSI, which stalls the VM -- and a headless audio
# app has no use for a display anyway. That is the whole point of the
# non-graphics idiom.


def audio_provider():
    """Return the module supplying this machine's audio factories.

    ``board_peripherals`` when this machine has one, else
    ``audiodev.auto``. A desktop ``board_peripherals`` forwards to
    ``audiodev.auto`` itself, so preferring the board module is right in
    both cases.
    """
    try:
        import board_peripherals

        return board_peripherals
    except ImportError:
        from audiodev import auto

        return auto


def _role(name, format, kwargs):
    provider = audio_provider()
    factory = getattr(provider, name, None)
    if factory is None:
        raise AttributeError(
            "{} provides no {!r} role".format(
                getattr(provider, "__name__", provider), name
            )
        )
    return factory(format, **kwargs)


def pcm_out(format=None, **kwargs):
    """Raw `PCMOutput <audiodev.PCMOutput>` from board or host, same call.

    Push bytes at it with ``write()``; no sample graph is pulled, so this
    needs no audiodsp in firmware.
    """
    return _role("pcm_out", format, kwargs)


def pcm_in(format=None, **kwargs):
    """Raw `PCMInput <audiodev.PCMInput>` from board or host, same call."""
    return _role("pcm_in", format, kwargs)


def audio_out(format=None, **kwargs):
    """`AudioOut <audiodev.sample_out.AudioOut>` sample player, board or host."""
    return _role("audio_out", format, kwargs)


# --- portable environment variables ---------------------------------------
#
# CPython has ``os.environ``; MicroPython and CircuitPython have ``getenv``
# and sometimes ``putenv``, and some ports have neither. ``env_set`` records
# every value in a process-local table as well as in whatever the host
# offers, so a value a page or a board config sets is visible to every
# reader in the same process, on every interpreter.

# Process-local overrides for ports without ``os.environ`` / ``os.putenv``.
_overrides = {}


def env_set(name, value):
    """Set an environment variable portably (CPython, MicroPython, CircuitPython).

    Always records a process-local override so ``env_bool`` sees the value even
    when the host ``os`` module has no ``environ``. When available, also updates
    ``os.environ`` or calls ``os.putenv``.
    """
    text = "" if value is None else str(value)
    _overrides[name] = text

    import os

    environ = getattr(os, "environ", None)
    if environ is not None:
        try:
            environ[name] = text
            return
        except Exception:
            pass
    putenv = getattr(os, "putenv", None)
    if putenv is not None:
        try:
            putenv(name, text)
        except Exception:
            pass


def env_bool(name, default=False):
    """Read a truthy/falsey environment variable with a portable fallback chain."""
    raw = _env_raw(name)
    if raw is None:
        return bool(default)
    text = str(raw).strip().lower()
    if text in ("1", "true", "yes", "on"):
        return True
    if text in ("0", "false", "no", "off"):
        return False
    return bool(default)


def env_get(name, default=None):
    """Read a string environment variable portably (honors ``env_set`` overrides)."""
    raw = _env_raw(name)
    if raw is None:
        return default
    return raw


def env_int(name, default=0):
    """Read an integer environment variable portably (honors ``env_set`` overrides)."""
    raw = _env_raw(name)
    if raw is None:
        return int(default)
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return int(default)


def env_float(name, default=0.0):
    """Read a floating-point environment variable portably."""
    raw = _env_raw(name)
    if raw is None:
        return float(default)
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError):
        return float(default)


def _env_raw(name):
    if name in _overrides:
        return _overrides[name]

    import os

    environ = getattr(os, "environ", None)
    if environ is not None:
        try:
            value = environ.get(name)
        except Exception:
            value = None
        if value is not None:
            return value
    getenv = getattr(os, "getenv", None)
    if getenv is None:
        return None
    try:
        return getenv(name)
    except Exception:
        return None


# --- the board's name ------------------------------------------------------
#
# One name for everything a board shows: its hostname, its BLE and Bluetooth
# names, its mDNS services and its setup access point. A saved name lives
# where wifi_manager keeps networks, so the two survive the same things.

#: The environment variable (a desktop, a browser) and the ``settings.toml``
#: key (CircuitPython) that hold a saved name.
NAME_KEY = "OMNIPYTHON_BOARD_NAME"
#: What a board's default name starts with, before the last three bytes of
#: its unique ID in hex.
NAME_PREFIX = "omnipython-"
#: The longest name `name` takes.
NAME_MAX = 20

_NVS_NAMESPACE = "omnipython"
_NVS_KEY = "board_name"
_NAME_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
_DESKTOPS = ("linux", "darwin", "win32", "cygwin", "freebsd", "openbsd", "netbsd")
_BROWSERS = ("webassembly", "emscripten")
_GET = object()  # name() with no argument
_random_name = None  # a browser's, made once per page load


def name(new=_GET):
    """The board's name, or give it a new one.

    Every stack that shows a name and is given none uses this one: the
    hostname `wifi_manager` sets before it joins (so DHCP, mDNS and
    Bluetooth Classic see it), the setup access point, bledev's services,
    medialink and hmilink.

    With no saved name, a board is ``omnipython-`` plus the last three bytes
    of its unique ID in hex (``omnipython-a1b2c3``; of its Wi-Fi MAC on an
    ESP32), a desktop is the
    computer's name, and a browser is ``omnipython-`` plus six random hex
    digits, new on each page load.

    A new name is saved where `wifi_manager` keeps networks: ``esp32.NVS``
    on an ESP32, ``OMNIPYTHON_BOARD_NAME`` in ``settings.toml`` on
    a CircuitPython board, ``/omnipython.json`` on other boards (``/flash`` on an
    STM32). On a desktop or in a browser it sets the
    ``OMNIPYTHON_BOARD_NAME`` environment variable for this process only;
    it never renames the computer. Stacks that already started keep the old
    name until the next start.

    Example::

        import boarddev

        boarddev.name()            # "omnipython-a1b2c3"
        boarddev.name("kitchen")   # saved; the board is "kitchen" from the next start
        boarddev.name(None)        # back to the default

    Args:
        new (str): The new name: one label of letters, digits and hyphens,
            not starting or ending with a hyphen, 1 to 20 characters, so it
            works unchanged as a hostname and as a BLE name. None forgets a
            saved name.

    Returns:
        str: The name, when called with no argument. Otherwise None.

    Raises:
        ValueError: The new name breaks one of the rules above.
        OSError: CircuitPython can't write ``settings.toml`` while a
            computer has the CIRCUITPY drive mounted.
    """
    import sys

    store = _name_store(sys.implementation.name, sys.platform)
    if new is _GET:
        return _name_read(store) or _name_default(sys.implementation.name, sys.platform)
    if new is not None:
        check_name(new)
    _name_write(store, new)
    return None


def check_name(text):
    """Raise `ValueError` unless ``text`` can be a board's name (see `name`)."""
    if not isinstance(text, str):
        raise ValueError("a board name is a string, not %r" % (text,))
    if not text:
        raise ValueError("a board name can't be empty")
    if len(text) > NAME_MAX:
        raise ValueError("a board name is at most %d characters: %r has %d" % (NAME_MAX, text, len(text)))
    for c in text:
        if c not in _NAME_CHARS:
            raise ValueError("a board name holds only letters, digits and hyphens: %r has %r" % (text, c))
    if text[0] == "-" or text[-1] == "-":
        raise ValueError("a board name can't start or end with a hyphen: %r" % (text,))


def _name_store(impl, platform):
    """Where a saved name lives here: "env", "toml", "nvs" or "file"."""
    if platform in _BROWSERS or platform.startswith(_DESKTOPS):
        return "env"  # includes CircuitPython's unix port, which has no CIRCUITPY drive
    if impl == "circuitpython":
        return "toml"
    try:
        import esp32

        if hasattr(esp32, "NVS"):
            return "nvs"
    except ImportError:
        pass
    return "file"


def _name_file():
    import sys

    return ("/flash" if sys.platform == "pyboard" else "") + "/omnipython.json"


def _name_read(store):
    if store == "env":
        return env_get(NAME_KEY) or None
    if store == "toml":
        import os

        return os.getenv(NAME_KEY) or None
    if store == "nvs":
        import esp32

        buf = bytearray(NAME_MAX)
        try:
            n = esp32.NVS(_NVS_NAMESPACE).get_blob(_NVS_KEY, buf)
        except OSError:  # ESP_ERR_NVS_NOT_FOUND: nothing saved
            return None
        return bytes(buf[:n]).decode() or None
    import json

    try:
        with open(_name_file()) as f:
            return json.load(f).get("board_name") or None
    except (OSError, ValueError, AttributeError):
        return None


def _name_write(store, new):
    if store == "env":
        env_set(NAME_KEY, new)
        return
    if store == "toml":
        _toml_write("/settings.toml", NAME_KEY, new)
        return
    if store == "nvs":
        import esp32

        nvs = esp32.NVS(_NVS_NAMESPACE)
        if new is None:
            try:
                nvs.erase_key(_NVS_KEY)
            except OSError:
                pass
        else:
            nvs.set_blob(_NVS_KEY, new.encode())
        nvs.commit()
        return
    import json

    path = _name_file()
    if new is None:
        import os

        try:
            os.remove(path)
        except OSError:
            pass
        return
    with open(path, "w") as f:
        json.dump({"board_name": new}, f)


def _toml_write(path, key, value):
    """Set or remove ``key = "value"`` in a settings.toml, keeping every other line."""
    try:
        with open(path) as f:
            lines = f.read().split("\n")
    except OSError:
        lines = []
    kept = [line for line in lines if line.split("=", 1)[0].strip() != key]
    while kept and not kept[-1].strip():
        kept.pop()
    if value is not None:
        kept.append('%s = "%s"' % (key, value))
    try:
        with open(path, "w") as f:
            f.write("\n".join(kept) + "\n")
    except OSError as e:
        raise OSError("can't save the board name in %s: is CIRCUITPY mounted on a computer? (%s)" % (path, e))


def _name_default(impl, platform):
    if platform in _BROWSERS:
        return _name_random()
    if platform.startswith(_DESKTOPS):  # CircuitPython's unix port too: no microcontroller module
        return _computer_name() or _name_random()
    if impl == "circuitpython":
        import microcontroller

        return _name_from_id(microcontroller.cpu.uid)
    if platform == "esp32":
        # On a chip with an 802.15.4 radio (C6, H2, S31) unique_id() is the
        # 8-byte EUI-64 cut to six bytes, ending ff:fe and one byte of the
        # MAC, so boards from one batch would share a name. The station's MAC
        # is the base MAC, which is unique_id() on every other ESP32.
        try:
            import network

            return _name_from_id(network.WLAN(network.STA_IF).config("mac"))
        except (ImportError, AttributeError):
            pass  # firmware without Wi-Fi: the H2, or a build with network left out
    import machine

    return _name_from_id(machine.unique_id())


def _name_from_id(uid):
    return NAME_PREFIX + "".join("%02x" % b for b in bytes(uid)[-3:])


def _name_random():
    global _random_name
    if _random_name is None:
        import random

        _random_name = NAME_PREFIX + "%06x" % random.getrandbits(24)
    return _random_name


def _computer_name():
    """The computer's name without its domain, or None where it can't be read."""
    text = None
    try:
        import socket

        text = socket.gethostname()
    except (ImportError, AttributeError, OSError):
        pass
    if not text:
        # MicroPython's unix and Windows ports have no gethostname().
        text = env_get("COMPUTERNAME") or env_get("HOSTNAME")
    if not text:
        for path in ("/proc/sys/kernel/hostname", "/etc/hostname"):
            try:
                with open(path) as f:
                    text = f.read().strip()
            except OSError:
                continue
            if text:
                break
    return text.split(".")[0] if text else None
