"""What the user chose, kept in ~/.config/omarchy-hyprmouse/settings.json.

Button actions are keyed by Linux button code because Hyprland binds them for
every mouse at once (mouse:275 is the same on all mice). Settings that live in
a mouse itself (onboard button settings, DPI, lighting) are read back from the
mouse instead of being stored here.
"""

import json
import os

PATH = os.path.expanduser("~/.config/omarchy-hyprmouse/settings.json")

# Button action kinds:
#   {"kind": "hotkey",  "keys": "SUPER+CTRL+TAB", "label": "Former workspace"}
#   {"kind": "command", "command": "notify-send hi"}
#   {"kind": "shortcut", "keys": "CTRL+SHIFT+T"}
#   {"kind": "disabled"}


class Store:
    def __init__(self):
        try:
            with open(PATH) as f:
                self.data = json.load(f)
        except (OSError, ValueError):
            self.data = {}
        self.data.setdefault("version", 1)
        self.data.setdefault("buttons", {})

    def save(self):
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        tmp = PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.data, f, indent=2)
        os.replace(tmp, PATH)

    @property
    def buttons(self):
        return {int(code): action for code, action in self.data["buttons"].items()}

    def button(self, code):
        return self.data["buttons"].get(str(code))

    def set_button(self, code, action):
        if action is None:
            self.data["buttons"].pop(str(code), None)
        else:
            self.data["buttons"][str(code)] = action
        self.save()
