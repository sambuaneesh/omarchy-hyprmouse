"""Hardware drivers: talk to the settings stored inside a mouse.

Everything that works through Hyprland (remapping buttons that send normal
button events) needs no driver. A driver adds what only the mouse itself can
do: re-enabling or reprogramming buttons in its memory, lighting, DPI and
polling rate. One driver covers one vendor protocol; individual mice are
described by profiles (see hyprmouse/profiles/ and CONTRIBUTING.md).

To add a driver: subclass Driver, decorate it with @register, import the
module at the bottom of this file, and write a profile with `driver = "<name>"`.
"""

from dataclasses import dataclass


class DriverError(Exception):
    """The mouse refused or didn't answer a request."""


@dataclass(frozen=True)
class ButtonSetting:
    """What a button is set to inside the mouse.

    kind:
      "default"  - sends its own normal button (Hyprland can then remap it)
      "disabled" - sends nothing at all
      "media"    - sends a media key; value is the HID consumer usage
      "other"    - anything else (set by vendor software); label describes it
    """

    kind: str
    value: int | None = None
    label: str = ""


DEFAULT = ButtonSetting("default")
DISABLED = ButtonSetting("disabled")


def media(usage):
    return ButtonSetting("media", usage)


# Standard HID consumer-control usages a mouse can send by itself, with the
# Linux key code each arrives as (used to recognise the press).
MEDIA_KEYS = {
    0x00CD: ("Play / pause", 164),
    0x00B5: ("Next track", 163),
    0x00B6: ("Previous track", 165),
    0x00E9: ("Volume up", 115),
    0x00EA: ("Volume down", 114),
    0x00E2: ("Mute", 113),
}


def describe(setting):
    if setting.kind == "default":
        return "default (sends its own button)"
    if setting.kind == "disabled":
        return "disabled"
    if setting.kind == "media":
        label = MEDIA_KEYS.get(setting.value, ("unknown",))[0]
        return f"media key {setting.value:#06x} ({label})"
    return setting.label or "other"


def media_usage_for_key(key_code):
    return next((usage for usage, (_, code) in MEDIA_KEYS.items() if code == key_code), None)


class Driver:
    """Base class for hardware drivers. Unsupported features raise NotImplementedError;
    the UI only offers what the mouse's profile declares."""

    name = ""

    def __init__(self, mouse):
        self.mouse = mouse
        self.profile = mouse.profile

    @classmethod
    def control_node(cls, mouse):
        """Device node the driver talks through (e.g. /dev/hidraw0), or None."""
        raise NotImplementedError

    def close(self):
        pass

    # Buttons: keyed by the Linux button code the button sends by default.

    def media_keys(self):
        """Consumer usages this mouse can store on a button."""
        return {}

    def get_button(self, code):
        raise NotImplementedError

    def set_button(self, code, setting):
        raise NotImplementedError

    # Lighting: zones and effects come from the profile.

    def get_lighting(self, zone):
        """(effect name or None, brightness 0-100)."""
        raise NotImplementedError

    def set_effect(self, zone, effect):
        raise NotImplementedError

    def set_brightness(self, zone, percent):
        raise NotImplementedError

    # Performance

    def get_dpi(self):
        raise NotImplementedError

    def set_dpi(self, dpi):
        """Returns the DPI the mouse actually took."""
        raise NotImplementedError

    def get_poll_rate(self):
        raise NotImplementedError

    def set_poll_rate(self, hz):
        raise NotImplementedError

    # Diagnostics for `omarchy-hyprmouse --doctor --scan`

    def scan(self):
        """Lines describing raw device state, to help write a new profile."""
        return []


DRIVERS = {}


def register(cls):
    DRIVERS[cls.name] = cls
    return cls


def get(name):
    return DRIVERS.get(name)


from . import razer  # noqa: E402,F401  (registers itself)
