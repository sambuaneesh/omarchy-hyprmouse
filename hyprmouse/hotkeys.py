"""The hotkeys defined in the user's Omarchy/Hyprland config, for the action picker."""

import os
import subprocess
from dataclasses import dataclass

EXTRACTOR = os.path.join(os.path.dirname(__file__), "data", "extract_hotkeys.lua")

MODIFIERS = ("SUPER", "CTRL", "ALT", "SHIFT")

# Hyprland keycode binds (layout independent number row etc.).
KEYCODES = {**{f"CODE:{10 + i}": str((i + 1) % 10) for i in range(10)},
            "CODE:20": "-", "CODE:21": "=", "CODE:34": "[", "CODE:35": "]"}
HIDDEN = {"CODE:201"}  # Copilot key, duplicates another binding

PRETTY_KEYS = {
    "RETURN": "Enter", "ESCAPE": "Esc", "BACKSPACE": "Backspace", "DELETE": "Delete",
    "SPACE": "Space", "TAB": "Tab", "PRINT": "Print", "HOME": "Home",
    "LEFT": "←", "RIGHT": "→", "UP": "↑", "DOWN": "↓",
    "COMMA": ",", "PERIOD": ".", "SLASH": "/", "MINUS": "-", "EQUAL": "=",
    "XF86AUDIORAISEVOLUME": "Volume up key", "XF86AUDIOLOWERVOLUME": "Volume down key",
    "XF86AUDIOMUTE": "Mute key", "XF86AUDIOMICMUTE": "Mic mute key",
    "XF86AUDIOPLAY": "Play key", "XF86AUDIOPAUSE": "Pause key",
    "XF86AUDIONEXT": "Next key", "XF86AUDIOPREV": "Previous key",
    "XF86MONBRIGHTNESSUP": "Brightness up key", "XF86MONBRIGHTNESSDOWN": "Brightness down key",
    "XF86KBDBRIGHTNESSUP": "Keyboard light up key", "XF86KBDBRIGHTNESSDOWN": "Keyboard light down key",
    "XF86KBDLIGHTONOFF": "Keyboard light key", "XF86TOUCHPADTOGGLE": "Touchpad key",
    "XF86TOUCHPADON": "Touchpad on key", "XF86TOUCHPADOFF": "Touchpad off key",
    "XF86CALCULATOR": "Calculator key", "XF86EJECT": "Eject key", "XF86POWEROFF": "Power key",
}

# Shown first in the picker, in this order, when the user's config has them.
SUGGESTED = [
    "Former workspace", "Next workspace", "Previous workspace", "Close window",
    "Full screen", "Toggle window floating/tiling", "Omarchy menu", "Launch apps",
    "Universal copy", "Universal paste", "Screenshot", "Toggle scratchpad",
    "Play", "Next track", "Previous track", "Mute",
]


@dataclass(frozen=True)
class Hotkey:
    keys: str  # normalized, e.g. "SUPER+CTRL+TAB"
    description: str

    @property
    def combo(self):
        return pretty_combo(self.keys)


def normalize(keys):
    """Same normalization as data/capture.lua."""
    parts = [p.strip().upper() for p in keys.replace(" ", "+").split("+") if p.strip()]
    parts = ["CTRL" if p == "CONTROL" else p for p in parts]
    mods = sorted({p for p in parts if p in MODIFIERS}, key=MODIFIERS.index)
    rest = [p for p in parts if p not in MODIFIERS]
    return "+".join(mods + rest[-1:])


def pretty_key(key):
    if key in KEYCODES:
        return KEYCODES[key]
    if key in PRETTY_KEYS:
        return PRETTY_KEYS[key]
    return key if len(key) <= 3 else key.title()


def pretty_combo(keys):
    parts = keys.split("+")
    return " + ".join([p.title() for p in parts[:-1]] + [pretty_key(parts[-1])])


def load():
    """All described hotkeys, de-duplicated by description, in config order."""
    try:
        out = subprocess.run(["lua", EXTRACTOR], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    seen, hotkeys = set(), []
    for line in out.splitlines():
        keys, _, description = line.partition("\t")
        if not description or keys.split("+")[-1] in HIDDEN or description in seen:
            continue
        seen.add(description)
        hotkeys.append(Hotkey(keys, description))
    return hotkeys


def suggested(hotkeys):
    by_description = {h.description: h for h in hotkeys}
    return [by_description[d] for d in SUGGESTED if d in by_description]
