# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""Choose where audio goes, which MIDI ports are in, which network carries traffic.

endpointkit keeps one list of everything a device can connect to, by kind,
and one choice per kind for the whole device. A script lists and picks::

    import endpointkit

    for ep in endpointkit.endpoints("audio.out"):
        print(ep.id, ep.label, ep.state)
    endpointkit.select("audio.out", "a2dp:speaker")

and a program that plays, casts or connects hears when the choice moves::

    def moved(event, kind):
        if event == endpointkit.SELECTION:
            reopen(endpointkit.selected(kind))

    endpointkit.subscribe("audio.out", moved)

The five ideas
--------------
A **kind** names a role: ``audio.out``, ``audio.in``, ``midi.in``,
``midi.out``, ``net``, ``cast.target``, ``camera``, ``gamepad``, ``keys``,
``pointer``, ``assistant``. Each says whether one endpoint is chosen at a time (a camera, a
cast target, the default network) or many (MIDI inputs merge, audio can fan
out), and what a person calls it, with an icon, for a picker or a status bar
to show (`title`, `icon`). `add_kind` adds another without changing anything
here.

A **provider** is one transport for one kind: I2S, USB audio or Bluetooth
for ``audio.out``. The library that owns the transport registers it, so this
package knows no transport by name. A provider says which shared
**resources** it takes (a radio, the USB port, an I2S bus): two choices that
take the same resource can't both stand, and `select` says what a choice
would stop before it stops it.

An **endpoint** is what a provider finds: a stable ``id``, a ``label`` a
person recognises, a ``state`` and what it can do (``caps``). Finding can be
slow (a Bluetooth scan, cast discovery), so providers report in `poll`, and
the list fills as it goes.

A **selection** is the chosen endpoints of a kind, for the whole device. It
is saved when a store is set (`set_store`) and comes back after a restart. A
chosen endpoint that isn't there yet stays chosen and is used when it shows
up. A program may **pin** a kind for itself while it runs; the pin wins over
the device's choice until it's lifted.

A **subscription** calls you when a kind's endpoints, their states or its
selection change.

Nothing here runs on its own: call `poll` from a timer (appkit's Shell does)
so slow providers can report. Nothing here draws either: the picker is
appkit's, and a script uses these calls directly.
"""

import sys

try:
    import json
except ImportError:  # a CircuitPython build without json
    json = None

try:
    import os
except ImportError:
    os = None

__version__ = "0.0.2"

#: One endpoint of the kind is chosen at a time.
ONE = 1
#: Any number of endpoints of the kind are chosen at once.
MANY = 0

#: The kinds every device knows, and how many of each can be chosen.
KINDS = {
    "audio.out": MANY,
    "audio.in": ONE,
    "midi.in": MANY,
    "midi.out": MANY,
    "net": ONE,
    "cast.target": ONE,
    "camera": ONE,
    "gamepad": MANY,
    "keys": MANY,
    "pointer": MANY,
    "assistant": ONE,
}

#: What a person calls each kind, and its icon: a Material Symbols name, which
#: the ``icons`` package draws. `add_kind` adds to it.
NAMES = {
    "audio.out": ("Audio out", "volume_up"),
    "audio.in": ("Audio in", "mic"),
    "midi.in": ("MIDI in", "piano"),
    "midi.out": ("MIDI out", "music_note"),
    "net": ("Network", "wifi"),
    "cast.target": ("Cast to", "cast"),
    "camera": ("Camera", "photo_camera"),
    "gamepad": ("Gamepads", "sports_esports"),
    "keys": ("Keyboards", "keyboard"),
    "pointer": ("Pointers", "mouse"),
    "assistant": ("Assistant", "smart_toy"),
}
#: The icon of a kind added with none.
OTHER_ICON = "cable"

# The kinds in the order they became known: a picker lists them this way.
# Written out, because a MicroPython dict keeps no order.
_ORDER = [
    "audio.out", "audio.in", "midi.in", "midi.out", "net", "cast.target",
    "camera", "gamepad", "keys", "pointer", "assistant",
]

AVAILABLE = "available"
CONNECTED = "connected"
NEEDS_PAIRING = "needs pairing"
UNAVAILABLE = "unavailable"

#: Subscription events: the list of a kind's endpoints changed.
ENDPOINTS = "endpoints"
#: An endpoint's state changed.
STATE = "state"
#: The kind's selection, or the pin on it, changed.
SELECTION = "selection"
#: A provider failed to start or stop a chosen endpoint; see `Endpoint.error`.
ERROR = "error"


def add_kind(name, count=ONE, title=None, icon=None):
    """Make a new kind known, choosing `ONE` or `MANY` endpoints at a time.

    *title* is what a person calls it ("Storage"), and *icon* a Material
    Symbols name ("sd_card"); a picker shows the kind's name and `OTHER_ICON`
    without them. Adding a kind that exists with the same count changes
    nothing but a title or icon given.

    Raises:
        ValueError: the kind exists with the other count.
    """
    if name in KINDS and KINDS[name] != count:
        raise ValueError("kind %r already chooses %s" % (name, "one" if KINDS[name] == ONE else "many"))
    KINDS[name] = count
    if name not in _ORDER:
        _ORDER.append(name)
    old = NAMES.get(name, (name, OTHER_ICON))
    NAMES[name] = (title or old[0], icon or old[1])


def kinds():
    """Every kind known, in the order they became known: the built-in ones first."""
    return list(_ORDER)


def title(kind):
    """What a person calls *kind*: "Audio out" for ``audio.out``, or the kind's own name."""
    return NAMES.get(kind, (kind, OTHER_ICON))[0]


def icon(kind):
    """*kind*'s icon, a Material Symbols name; `OTHER_ICON` when it has none."""
    return NAMES.get(kind, (kind, OTHER_ICON))[1]


class Conflict(Exception):
    """A choice would stop endpoints that are using the same resources.

    ``stops`` lists those endpoints, and ``resources`` the resources they share
    with the choice. Ask the person, then call `select` again with
    ``confirm=True`` to go ahead.
    """

    def __init__(self, kind, stops, resources):
        self.kind = kind
        self.stops = stops
        self.resources = resources
        super().__init__(
            "choosing %s stops %s (shares %s)"
            % (kind, ", ".join(ep.label for ep in stops), ", ".join(resources)),
        )


class Endpoint:
    """Something a provider found that the device can connect to.

    Attributes:
        id (str): stable across restarts, ``"<provider>:<local id>"``.
        label (str): what a person recognises: "Living room speaker".
        kind (str): the kind it belongs to.
        provider (Provider): the provider that found it.
        state (str): `AVAILABLE`, `CONNECTED`, `NEEDS_PAIRING` or `UNAVAILABLE`.
        caps (dict): what it can do, in the kind's own terms (rates,
            channels, a resolution); empty when the provider says nothing.
        resources (tuple): the shared resources it takes when chosen; the
            provider's own unless the endpoint names others.
        error (str or None): why the provider last failed to start or stop it.
    """

    def __init__(self, provider, local_id, label, state=AVAILABLE, caps=None, resources=None):
        self.provider = provider
        self.local_id = local_id
        self.id = "%s:%s" % (provider.name, local_id)
        self.kind = provider.kind
        self.label = label
        self.state = state
        self.caps = caps if caps is not None else {}
        self.resources = tuple(resources) if resources is not None else tuple(provider.resources)
        self.error = None

    def __repr__(self):
        return "<Endpoint %s %r %s>" % (self.id, self.label, self.state)


class Provider:
    """One transport for one kind. Subclass it in the library that owns the transport.

    Set ``kind``, ``name`` (unique on the device, the first part of every
    endpoint id) and ``resources``, and write `scan`. A transport whose
    finding is slow writes `poll` too, and one that must do something when
    an endpoint is chosen or let go writes `apply`.
    """

    kind = None
    name = None
    resources = ()

    def __init__(self, kind=None, name=None, resources=None):
        if kind is not None:
            self.kind = kind
        if name is not None:
            self.name = name
        if resources is not None:
            self.resources = tuple(resources)
        if not self.kind or not self.name:
            raise ValueError("a provider needs a kind and a name")
        if ":" in self.name:
            raise ValueError("a provider's name can't hold ':': %r" % self.name)

    def endpoint(self, local_id, label, state=AVAILABLE, caps=None, resources=None):
        """An `Endpoint` of this provider, for `scan` and `poll` to return."""
        return Endpoint(self, local_id, label, state, caps, resources)

    def scan(self):
        """The endpoints known now, as a list. It must return quickly; start
        anything slow here and report what it finds from `poll`."""
        return []

    def poll(self):
        """A new list of endpoints when something changed since the last
        call, or None. Called from the registry's `poll`."""
        return None

    def apply(self, endpoint, chosen):
        """Start using *endpoint* when *chosen* is True, stop when False.

        Raise to refuse; the registry records the message on the endpoint.
        """

    def stop(self):
        """Release whatever the provider holds; called by `Registry.unregister`."""


class Registry:
    """Every provider's endpoints, the device's choices, the pins and the subscribers.

    Most programs use the module's own registry through the module-level
    functions. Make another for a test, or to keep a second set of choices.

    Args:
        store (str or None): a JSON file the choices are saved in and loaded
            from. `set_store` sets it later.
    """

    def __init__(self, store=None):
        self._providers = []
        self._found = {}  # provider name -> list of Endpoint
        self._chosen = {}  # kind -> list of ids, the device's choice
        self._pins = {}  # kind -> list of (owner, ids), the newest last
        self._applied = {}  # kind -> list of ids the providers have started
        self._subs = []  # (kind or None, callback)
        self._store = None
        if store:
            self.set_store(store)

    # -- providers -------------------------------------------------------------

    def register(self, provider):
        """Add *provider*, list what it knows now, and start any choice waiting on it.

        Raises:
            ValueError: another provider has the same name, or the kind is unknown.
        """
        if provider.kind not in KINDS:
            raise ValueError("unknown kind %r; add it with add_kind" % provider.kind)
        for p in self._providers:
            if p.name == provider.name:
                raise ValueError("a provider named %r is already registered" % provider.name)
        self._providers.append(provider)
        self._found[provider.name] = []
        self._update(provider, provider.scan())
        return provider

    def unregister(self, provider):
        """Remove *provider* and its endpoints, stopping any that were chosen.

        Their ids stay chosen, so they're used again when the provider returns.
        """
        if provider not in self._providers:
            return
        self._update(provider, [])
        self._providers.remove(provider)
        del self._found[provider.name]
        try:
            provider.stop()
        except Exception as exc:  # noqa: BLE001 - a provider's failure is reported, not raised
            _report("stop", provider.name, exc)

    def providers(self, kind=None):
        """The registered providers, of *kind* or of every kind."""
        return [p for p in self._providers if kind is None or p.kind == kind]

    def poll(self):
        """Ask each provider for news; returns True when anything changed.

        Call it from a timer. A provider that raises is reported and skipped.
        """
        changed = False
        for provider in list(self._providers):
            try:
                found = provider.poll()
            except Exception as exc:  # noqa: BLE001
                _report("poll", provider.name, exc)
                continue
            if found is not None:
                changed = self._update(provider, found) or changed
        return changed

    def refresh(self, kind=None):
        """Scan again now, every provider of *kind* or of every kind."""
        for provider in self.providers(kind):
            try:
                found = provider.scan()
            except Exception as exc:  # noqa: BLE001
                _report("scan", provider.name, exc)
                continue
            self._update(provider, found)

    # -- endpoints -------------------------------------------------------------

    def endpoints(self, kind):
        """The endpoints of *kind* found so far, provider by provider in the
        order they registered."""
        _known(kind)
        out = []
        for provider in self._providers:
            if provider.kind == kind:
                out.extend(self._found[provider.name])
        return out

    def find(self, endpoint_id):
        """The `Endpoint` with this id, or None while it isn't found."""
        name = endpoint_id.split(":", 1)[0]
        for ep in self._found.get(name, ()):
            if ep.id == endpoint_id:
                return ep
        return None

    # -- choices ---------------------------------------------------------------

    def chosen(self, kind):
        """The device's choice for *kind* as a list of ids, found or not, ignoring pins."""
        _known(kind)
        return list(self._chosen.get(kind, ()))

    def pinned(self, kind):
        """``(owner, ids)`` of the pin in force on *kind*, or None."""
        _known(kind)
        pins = self._pins.get(kind)
        if not pins:
            return None
        owner, ids = pins[-1]
        return owner, list(ids)

    def selection(self, kind):
        """The ids in force for *kind*: the newest pin's, or the device's choice."""
        pin = self.pinned(kind)
        return pin[1] if pin else self.chosen(kind)

    def selected(self, kind):
        """The chosen endpoints of *kind* that are found, in choice order.

        For a `ONE` kind this is a list of at most one; take ``[0]`` when it isn't empty.
        """
        out = []
        for i in self.selection(kind):
            ep = self.find(i)
            if ep is not None:
                out.append(ep)
        return out

    def conflicts(self, kind, ids):
        """What choosing *ids* for *kind* would stop: ``(endpoints, resources)``.

        Only found endpoints count, on both sides.
        """
        ids = self._ids(kind, ids)
        taking = []
        for i in ids:
            ep = self.find(i)
            if ep is not None:
                taking.extend(r for r in ep.resources if r not in taking)
        stops = []
        shared = []
        replacing = self.selection(kind)
        for other in KINDS:
            for i in self.selection(other):
                if other == kind and (i in ids or i in replacing):
                    continue
                ep = self.find(i)
                if ep is None:
                    continue
                hit = [r for r in ep.resources if r in taking]
                if hit:
                    stops.append(ep)
                    shared.extend(r for r in hit if r not in shared)
        # Two endpoints of one choice that need the same resource can't both run.
        seen = []
        for i in ids:
            ep = self.find(i)
            if ep is None:
                continue
            for r in ep.resources:
                if r in seen and ep not in stops:
                    stops.append(ep)
                    if r not in shared:
                        shared.append(r)
                seen.append(r)
        return stops, shared

    def select(self, kind, ids, confirm=False):
        """Choose *ids* (one id, a list, or None for nothing) for *kind*, for the whole device.

        The providers start the new endpoints and stop the old ones, the
        choice is saved, and subscribers hear about it. While a pin is in
        force the choice is saved but the pin's endpoints stay in use.

        Args:
            confirm (bool): go ahead even when the choice stops other endpoints.

        Raises:
            Conflict: the choice stops endpoints using the same resources,
                and *confirm* is False. Nothing has changed.
            ValueError: more than one id for a `ONE` kind.
        """
        ids = self._ids(kind, ids)
        self._make_room(kind, ids, confirm)
        self._chosen[kind] = ids
        self._save()
        self._settle(kind)

    def pin(self, kind, ids, owner, confirm=False):
        """Use *ids* for *kind* while *owner* (an app's name) runs, whatever the device's choice.

        The newest pin on a kind wins. Raises as `select` does.
        """
        ids = self._ids(kind, ids)
        self._make_room(kind, ids, confirm)
        pins = [p for p in self._pins.get(kind, ()) if p[0] != owner]
        pins.append((owner, ids))
        self._pins[kind] = pins
        self._settle(kind)

    def unpin(self, owner, kind=None):
        """Lift *owner*'s pin on *kind*, or all of its pins; the device's choice returns."""
        for k in list(self._pins):
            if kind is not None and k != kind:
                continue
            pins = [p for p in self._pins[k] if p[0] != owner]
            if len(pins) != len(self._pins[k]):
                if pins:
                    self._pins[k] = pins
                else:
                    del self._pins[k]
                self._settle(k)

    # -- subscriptions ---------------------------------------------------------

    def subscribe(self, kind, callback):
        """Call ``callback(event, kind)`` when *kind* changes, or every kind when None.

        The event is `ENDPOINTS`, `STATE`, `SELECTION` or `ERROR`. Returns
        *callback*, for `unsubscribe`.
        """
        if kind is not None:
            _known(kind)
        self._subs.append((kind, callback))
        return callback

    def unsubscribe(self, callback):
        """Stop calling *callback*, for every kind it was subscribed to."""
        self._subs = [s for s in self._subs if s[1] is not callback]

    # -- the store -------------------------------------------------------------

    def set_store(self, path):
        """Save choices in *path* (JSON), and load the ones saved there.

        Loaded choices replace the ones in memory for the kinds they name,
        and providers start them as their endpoints are found.
        """
        self._store = path
        saved = _load(path)
        for kind, ids in saved.get("selection", {}).items():
            if kind in KINDS and isinstance(ids, list):
                if KINDS[kind] == ONE:
                    ids = ids[:1]
                self._chosen[kind] = [str(i) for i in ids]
                self._settle(kind)

    # -- inside ----------------------------------------------------------------

    def _ids(self, kind, ids):
        _known(kind)
        if ids is None:
            ids = []
        elif isinstance(ids, str):
            ids = [ids]
        else:
            ids = list(ids)
        if KINDS[kind] == ONE and len(ids) > 1:
            raise ValueError("%s takes one endpoint at a time, not %d" % (kind, len(ids)))
        out = []
        for i in ids:
            if i not in out:
                out.append(i)
        return out

    def _make_room(self, kind, ids, confirm):
        stops, shared = self.conflicts(kind, ids)
        if not stops:
            return
        if not confirm:
            raise Conflict(kind, stops, shared)
        for ep in stops:
            if ep.id in ids:
                raise ValueError("%s and another choice of %s need %s" % (ep.label, kind, ", ".join(shared)))
            k = ep.kind
            if ep.id in self._chosen.get(k, ()):
                self._chosen[k] = [i for i in self._chosen[k] if i != ep.id]
            if k in self._pins:
                for idx, (owner, pids) in enumerate(self._pins[k]):
                    if ep.id in pids:
                        self._pins[k][idx] = (owner, [i for i in pids if i != ep.id])
            if k != kind:
                self._settle(k)
        self._save()

    def _settle(self, kind):
        """Start and stop endpoints so the providers match the selection, then tell subscribers."""
        want = [i for i in self.selection(kind) if self.find(i) is not None]
        had = self._applied.get(kind, [])
        errors = False
        for i in had:
            if i not in want:
                ep = self.find(i)
                if ep is not None:
                    errors = self._apply(ep, False) or errors
        applied = []
        for i in want:
            ep = self.find(i)
            if i in had:
                applied.append(i)
            elif not self._apply(ep, True):
                applied.append(i)
            else:
                errors = True
        self._applied[kind] = applied
        self._notify(SELECTION, kind)
        if errors:
            self._notify(ERROR, kind)

    def _apply(self, ep, chosen):
        """Have the provider start or stop *ep*; True when it failed."""
        try:
            ep.provider.apply(ep, chosen)
        except Exception as exc:  # noqa: BLE001
            ep.error = str(exc) or exc.__class__.__name__
            return True
        ep.error = None
        return False

    def _update(self, provider, found):
        """Take a provider's new list, keeping Endpoint objects for ids it still has."""
        old = self._found.get(provider.name, [])
        olds = {ep.id: ep for ep in old}
        new = []
        list_changed = len(found) != len(old)
        state_changed = False
        for ep in found:
            prev = olds.get(ep.id)
            if prev is None:
                list_changed = True
                new.append(ep)
                continue
            if prev.state != ep.state:
                state_changed = True
            if prev.label != ep.label:
                list_changed = True
            prev.state = ep.state
            prev.label = ep.label
            prev.caps = ep.caps
            prev.resources = ep.resources
            new.append(prev)
        if not list_changed:
            list_changed = [e.id for e in new] != [e.id for e in old]
        # Endpoints that went away are stopped before they're forgotten.
        gone = [ep for ep in old if ep.id not in [e.id for e in new]]
        kind = provider.kind
        for ep in gone:
            if ep.id in self._applied.get(kind, ()):
                self._apply(ep, False)
                self._applied[kind] = [i for i in self._applied[kind] if i != ep.id]
        self._found[provider.name] = new
        if list_changed:
            self._notify(ENDPOINTS, kind)
            if gone or any(e.id in self.selection(kind) for e in new):
                self._settle(kind)
        if state_changed:
            self._notify(STATE, kind)
        return list_changed or state_changed

    def _notify(self, event, kind):
        for k, callback in list(self._subs):
            if k is None or k == kind:
                try:
                    callback(event, kind)
                except Exception as exc:  # noqa: BLE001 - one subscriber can't stop the rest
                    _report("subscriber", kind, exc)

    def _save(self):
        if self._store:
            _dump(self._store, {"selection": self._chosen})


def _known(kind):
    if kind not in KINDS:
        raise ValueError("unknown kind %r" % kind)


def _report(what, who, exc):
    if hasattr(sys, "print_exception"):
        sys.print_exception(exc)
    print("endpointkit: %s %s failed: %r" % (who, what, exc))


def _load(path):
    if json is None:
        return {}
    try:
        with open(path) as f:
            data = json.load(f)
    except OSError:
        return {}
    except ValueError:
        print("endpointkit: %s isn't JSON; starting with no saved choices" % path)
        return {}
    return data if isinstance(data, dict) else {}


def _dump(path, data):
    if json is None:
        raise OSError("this build has no json module, so choices can't be saved")
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    replace = getattr(os, "replace", None)
    if replace is not None:
        replace(tmp, path)
        return
    # MicroPython's rename overwrites on littlefs and FAT alike, but not on
    # every host, so clear the old file first when it refuses.
    try:
        os.rename(tmp, path)
    except OSError:
        os.remove(path)
        os.rename(tmp, path)


#: The device's registry, which the functions below use.
registry = Registry()

register = registry.register
unregister = registry.unregister
providers = registry.providers
poll = registry.poll
refresh = registry.refresh
endpoints = registry.endpoints
find = registry.find
chosen = registry.chosen
pinned = registry.pinned
selection = registry.selection
selected = registry.selected
conflicts = registry.conflicts
select = registry.select
pin = registry.pin
unpin = registry.unpin
subscribe = registry.subscribe
unsubscribe = registry.unsubscribe
set_store = registry.set_store
