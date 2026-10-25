"""Mouse profiles: one TOML file per mouse model, describing what it can do.

Built-in profiles live in hyprmouse/profiles/<vendor>/. Your own go in
~/.config/omarchy-hyprmouse/profiles/ and win over built-in ones for the same USB id,
so a new mouse can be tried without touching the installed package.
See CONTRIBUTING.md for the format.
"""

import glob
import os
import tomllib
from dataclasses import dataclass, field

BUILTIN_DIR = os.path.join(os.path.dirname(__file__), "profiles")
USER_DIR = os.path.expanduser("~/.config/omarchy-hyprmouse/profiles")

# Linux button codes and the mouse button number (1-based) each one is.
BUTTON_NUMBERS = {272: 1, 273: 2, 274: 3, 275: 4, 276: 5, 277: 6, 278: 7, 279: 8}
KNOWN_EFFECTS = ("static", "breathing", "off")
KNOWN_ZONES = ("logo", "scroll")  # drawn on the mouse picture


class ProfileError(Exception):
    pass


@dataclass(frozen=True)
class Button:
    code: int  # Linux button code it sends by default
    name: str
    id: int  # the driver's own id for it
    native: int  # mouse button number (4 = back, 5 = forward, ...)


@dataclass(frozen=True)
class Zone:
    key: str
    name: str
    options: dict


@dataclass
class Profile:
    path: str
    name: str
    driver: str
    usb: list  # [(vendor, product)]
    buttons: dict = field(default_factory=dict)  # code -> Button
    zones: list = field(default_factory=list)
    effects: list = field(default_factory=list)
    dpi: tuple | None = None  # (min, max, step)
    dpi_presets: list = field(default_factory=list)
    poll_rates: list = field(default_factory=list)
    options: dict = field(default_factory=dict)  # the [<driver>] table

    @property
    def id(self):
        return os.path.splitext(os.path.basename(self.path))[0]

    def zone(self, key):
        return next(z for z in self.zones if z.key == key)

    @property
    def has_lighting(self):
        return bool(self.zones)

    @property
    def has_performance(self):
        return self.dpi is not None or bool(self.poll_rates)


def _usb(value):
    vendor, _, product = str(value).partition(":")
    try:
        return int(vendor, 16), int(product, 16)
    except ValueError:
        raise ProfileError(f'usb ids look like "1532:0098", got {value!r}')


def parse(path, data):
    """Build a Profile from parsed TOML, with errors a contributor can act on."""
    for key in ("name", "driver", "usb"):
        if key not in data:
            raise ProfileError(f"missing `{key}`")
    usb = [_usb(v) for v in data["usb"]]
    if not usb:
        raise ProfileError("`usb` needs at least one id")

    buttons = {}
    for code, entry in data.get("buttons", {}).items():
        try:
            code = int(code)
        except ValueError:
            raise ProfileError(f"button keys are Linux button codes (274, 275...), got {code!r}")
        if code not in BUTTON_NUMBERS:
            raise ProfileError(f"button {code}: not a mouse button code (272-279)")
        if code in (272, 273):
            raise ProfileError("left and right click (272, 273) can't be remapped")
        if "id" not in entry or "name" not in entry:
            raise ProfileError(f"button {code}: needs `name` and `id`")
        buttons[code] = Button(code, entry["name"], entry["id"], entry.get("native", BUTTON_NUMBERS[code]))

    lighting = data.get("lighting", {})
    zones = []
    for entry in lighting.get("zones", []):
        if entry.get("key") not in KNOWN_ZONES:
            raise ProfileError(f"lighting zone `key` must be one of {', '.join(KNOWN_ZONES)}")
        options = {k: v for k, v in entry.items() if k not in ("key", "name")}
        zones.append(Zone(entry["key"], entry.get("name", entry["key"].title()), options))
    effects = lighting.get("effects", list(KNOWN_EFFECTS) if zones else [])
    unknown = [e for e in effects if e not in KNOWN_EFFECTS]
    if unknown:
        raise ProfileError(f"unknown lighting effects {unknown}; known: {', '.join(KNOWN_EFFECTS)}")

    performance = data.get("performance", {})
    dpi = performance.get("dpi")
    if dpi is not None and (len(dpi) != 3 or not dpi[0] < dpi[1]):
        raise ProfileError("performance.dpi is [min, max, step]")

    return Profile(
        path=path,
        name=data["name"],
        driver=data["driver"],
        usb=usb,
        buttons=buttons,
        zones=zones,
        effects=effects,
        dpi=tuple(dpi) if dpi else None,
        dpi_presets=performance.get("dpi_presets", []),
        poll_rates=performance.get("poll_rates", []),
        options=data.get(data["driver"], {}),
    )


def load(path):
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as error:
        raise ProfileError(f"not valid TOML: {error}")
    return parse(path, data)


def files(include_user=True):
    paths = sorted(glob.glob(os.path.join(BUILTIN_DIR, "**", "*.toml"), recursive=True))
    if include_user:
        paths += sorted(glob.glob(os.path.join(USER_DIR, "**", "*.toml"), recursive=True))
    return paths


def load_all(include_user=True):
    """(profiles by usb id, {path: error}) — later files (user ones) win."""
    by_usb, errors = {}, {}
    for path in files(include_user):
        try:
            profile = load(path)
        except ProfileError as error:
            errors[path] = str(error)
            continue
        for usb in profile.usb:
            by_usb[usb] = profile
    return by_usb, errors


def udev_rules(profiles):
    """udev rules giving the signed-in user access to these mice (never keyboards)."""
    by_vendor = {}
    for profile in profiles:
        for vendor, product in profile.usb:
            by_vendor.setdefault(vendor, set()).add(product)

    lines = [
        "# Generated by omarchy-hyprmouse (`omarchy-hyprmouse --udev-rules`). Lets the signed-in user",
        "# configure supported mice and see which mouse button is pressed.",
        "",
    ]
    for vendor in sorted(by_vendor):
        products = "|".join(f"{p:04x}" for p in sorted(by_vendor[vendor]))
        lines += [
            f'SUBSYSTEM=="hidraw", ATTRS{{idVendor}}=="{vendor:04x}", ATTRS{{idProduct}}=="{products}", TAG+="uaccess"',
            f'SUBSYSTEM=="input", KERNEL=="event*", ATTRS{{idVendor}}=="{vendor:04x}", ATTRS{{idProduct}}=="{products}", TAG+="uaccess"',
        ]
    lines += [
        "",
        "# Any mouse: read button presses (\"press the button you want to change\").",
        'SUBSYSTEM=="input", KERNEL=="event*", ENV{ID_INPUT_MOUSE}=="1", ENV{ID_INPUT_KEYBOARD}!="1", '
        'ENV{ID_INPUT_TOUCHPAD}!="1", TAG+="uaccess"',
    ]
    return "\n".join(lines) + "\n"
