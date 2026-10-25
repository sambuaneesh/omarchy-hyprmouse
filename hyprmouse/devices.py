"""Find connected mice from sysfs (no root needed) and match them to profiles."""

import glob
import os
from dataclasses import dataclass, field

from . import drivers, profiles

BTN_LEFT, BTN_RIGHT, BTN_MIDDLE = 272, 273, 274
REL_X, REL_Y = 0, 1

# Friendly names for the Linux button codes Hyprland calls mouse:<code>.
BUTTON_NAMES = {
    272: "Left click",
    273: "Right click",
    274: "Wheel click",
    275: "Side button (back)",
    276: "Side button (forward)",
    277: "Forward button",
    278: "Back button",
    279: "Task button",
}

# What each button does when left alone.
DEFAULT_ACTIONS = {274: "Middle click", 275: "Back", 276: "Forward", 277: "Forward", 278: "Back", 279: "Task"}

LOCKED = (BTN_LEFT, BTN_RIGHT)  # never remapped: you'd lose the ability to click


@dataclass
class Mouse:
    name: str
    vendor: int
    product: int
    usb_path: str
    event_nodes: list = field(default_factory=list)
    buttons: set = field(default_factory=set)
    profile: profiles.Profile | None = None
    control: str | None = None  # node the hardware driver talks through

    @property
    def id(self):
        return f"{self.vendor:04x}:{self.product:04x}@{self.usb_path}"

    @property
    def driver_class(self):
        return drivers.get(self.profile.driver) if self.profile else None

    @property
    def supported(self):
        """True when hyprmouse can change settings inside this mouse."""
        return self.driver_class is not None and self.control is not None

    def button_name(self, code):
        if self.profile and code in self.profile.buttons:
            return self.profile.buttons[code].name
        return BUTTON_NAMES.get(code, f"Button {code - BTN_LEFT + 1}")

    def button_codes(self):
        return sorted(self.buttons)


def _bits(path):
    try:
        words = open(path).read().split()
    except OSError:
        return set()
    bits = set()
    for index, word in enumerate(reversed(words)):
        value = int(word, 16)
        for bit in range(64):
            if value >> bit & 1:
                bits.add(index * 64 + bit)
    return bits


def _read(path, default=""):
    try:
        return open(path).read().strip()
    except OSError:
        return default


def _usb_device_path(sysfs_path):
    """Path of the USB device (not interface) a sysfs node belongs to."""
    parts = os.path.realpath(sysfs_path).split("/")
    for index in range(len(parts) - 1, 0, -1):
        if ":" in parts[index] and "-" in parts[index] and "." in parts[index].split(":")[-1]:
            return "/".join(parts[:index])  # parent of "1-2:1.0" is the device "1-2"
    return None


def find_mice(known=None):
    """Connected mice with something to configure. `known` = profiles by usb id."""
    if known is None:
        known, _ = profiles.load_all()
    mice = {}
    for event in sorted(glob.glob("/sys/class/input/event*")):
        device = event + "/device"
        name = _read(device + "/name")
        if "touchpad" in name.lower():
            continue
        real = os.path.realpath(device)
        if "/virtual/" in real:  # software devices (ydotool, remappers)
            continue
        # One physical mouse exposes several nodes; group them by USB device,
        # or by HID device for Bluetooth mice.
        usb = _usb_device_path(device) or os.path.dirname(os.path.dirname(real))
        vendor = int(_read(device + "/id/vendor", "0"), 16)
        product = int(_read(device + "/id/product", "0"), 16)
        keys = _bits(device + "/capabilities/key")
        rel = _bits(device + "/capabilities/rel")

        mouse = mice.get(usb)
        if mouse is None:
            mouse = mice[usb] = Mouse(name, vendor, product, usb)
        mouse.event_nodes.append("/dev/input/" + os.path.basename(event))
        if REL_X in rel and REL_Y in rel and BTN_LEFT in keys:
            mouse.name = name
            mouse.buttons |= {code for code in keys if BTN_LEFT <= code < BTN_LEFT + 16}

    # Skip pointers with nothing to configure (e.g. a touchpad's mouse node).
    found = [m for m in mice.values() if m.buttons - set(LOCKED)]
    for mouse in found:
        mouse.profile = known.get((mouse.vendor, mouse.product))
        if mouse.profile:
            mouse.name = mouse.profile.name
            if mouse.driver_class:
                mouse.control = mouse.driver_class.control_node(mouse)
    return found


def sysfs_nodes(mouse):
    """sysfs paths of every device node of this mouse, for udev to re-check."""
    paths = []
    for node in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        if _usb_device_path(node + "/device") == mouse.usb_path:
            paths.append(node)
    for event in mouse.event_nodes:
        paths.append("/sys/class/input/" + os.path.basename(event))
    return paths


def needs_permission(mouse):
    if mouse.supported and not os.access(mouse.control, os.R_OK | os.W_OK):
        return True
    return not any(os.access(node, os.R_OK) for node in mouse.event_nodes)
