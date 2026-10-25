"""Omarchy integration: the "Setup > Mouse" menu entry and the repair hooks.

Applied when the app starts (so a package install needs no manual steps) and
undone by `omarchy-hyprmouse --uninstall`. Everything here is per-user config.
"""

import os

OMARCHY = os.path.expanduser("~/.config/omarchy")
MENU = os.path.join(OMARCHY, "extensions", "omarchy-menu.jsonc")
HOOKS = os.path.join(OMARCHY, "hooks")
HOOK_DIRS = ("post-boot.d", "post-update.d")

MENU_KEY = '"setup.mouse"'
MENU_LINES = [
    "  // omarchy-hyprmouse: mouse buttons, lighting and sensitivity",
    '  "setup.mouse": {"icon":"󰍽","label":"Mouse","description":"Buttons, lighting and sensitivity",'
    '"aliases":["mouse","hyprmouse"],"action":"omarchy-launch-or-focus-tui --app-id=org.omarchy.hyprmouse omarchy-hyprmouse"},',
]

HOOK = """#!/bin/sh
# omarchy-hyprmouse: keep mouse button bindings wired into Hyprland after updates
# and `omarchy refresh hyprland`. Removed by `omarchy-hyprmouse --uninstall`.
command -v omarchy-hyprmouse >/dev/null 2>&1 && exec omarchy-hyprmouse --repair
exit 0
"""


def omarchy_present():
    return os.path.isdir(OMARCHY)


def ensure():
    """Add the menu entry and hooks if missing. Returns a list of what was added."""
    if not omarchy_present():
        return []
    added = []
    try:
        text = open(MENU).read() if os.path.exists(MENU) else "{\n}\n"
    except OSError:
        text = None
    if text is not None and MENU_KEY not in text:
        end = text.rstrip().rindex("}")
        text = text[:end].rstrip() + "\n\n" + "\n".join(MENU_LINES) + "\n}\n"
        os.makedirs(os.path.dirname(MENU), exist_ok=True)
        with open(MENU, "w") as f:
            f.write(text)
        added.append("Omarchy menu entry (Setup > Mouse)")

    for directory in HOOK_DIRS:
        path = os.path.join(HOOKS, directory, "omarchy-hyprmouse")
        if os.path.isdir(os.path.dirname(path)) and (not os.path.exists(path) or open(path).read() != HOOK):
            with open(path, "w") as f:
                f.write(HOOK)
            os.chmod(path, 0o755)
            if directory == HOOK_DIRS[0]:
                added.append("repair hooks")
    return added


def remove():
    if os.path.exists(MENU):
        lines = open(MENU).read().split("\n")
        keep = [line for line in lines if MENU_KEY not in line and line.strip() != MENU_LINES[0].strip()]
        if keep != lines:
            with open(MENU, "w") as f:
                f.write("\n".join(keep))
    for directory in HOOK_DIRS:
        path = os.path.join(HOOKS, directory, "omarchy-hyprmouse")
        if os.path.exists(path):
            os.remove(path)
