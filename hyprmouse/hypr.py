"""Hyprland side: turn button actions into ~/.config/hypr/hyprmouse.lua."""

import os
import shutil
import subprocess
import time

from . import hotkeys

HYPR = os.path.expanduser("~/.config/hypr")
MAIN = os.path.join(HYPR, "hyprland.lua")
MODULE = os.path.join(HYPR, "hyprmouse.lua")
CAPTURE = os.path.join(HYPR, "hyprmouse_capture.lua")
CAPTURE_SOURCE = os.path.join(os.path.dirname(__file__), "data", "capture.lua")

CAPTURE_REQUIRE = 'require("hypr.hyprmouse_capture")'
MODULE_REQUIRE = 'require("hypr.hyprmouse")'
OMARCHY_REQUIRE = 'require("default.hypr.omarchy")'

HEADER = """\
-- Mouse buttons, managed by omarchy-hyprmouse (Omarchy menu > Setup > Mouse, or
-- run `omarchy-hyprmouse`). This file is rewritten by the app; change buttons there.

local function hotkey(keys)
  return hyprmouse and hyprmouse.action(keys)
end

local function command(cmd)
  return hl.dsp.exec_cmd(cmd)
end

-- Press and release a key combination in the focused window (same approach as
-- Omarchy's universal clipboard bindings).
local function shortcut(mods, key)
  return function()
    hl.dispatch(hl.dsp.send_key_state({ mods = mods, key = key, state = "down" }))
    hl.timer(function()
      hl.dispatch(hl.dsp.send_key_state({ mods = mods, key = key, state = "up" }))
    end, { timeout = 50, type = "oneshot" })
  end
end

local function disabled()
  return function() end
end

local function button(name, description, action)
  if action then
    hl.bind(name, action, { description = description })
  end
end

-- The app's own window (Omarchy's window helper; skipped on plain Hyprland).
if o and o.window then
  o.window("org.omarchy.hyprmouse", { float = true })
  o.window("org.omarchy.hyprmouse", { center = true })
  o.window("org.omarchy.hyprmouse", { size = { 960, 600 } })
end
"""


def lua_string(value):
    out = ['"']
    for ch in str(value):
        if ch in '"\\':
            out.append("\\" + ch)
        elif ch == "\n":
            out.append("\\n")
        elif ord(ch) < 32:
            out.append("\\%03d" % ord(ch))
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def describe(action):
    """Short human description of a stored action."""
    kind = action.get("kind")
    if kind == "hotkey":
        return action.get("label") or hotkeys.pretty_combo(action["keys"])
    if kind == "command":
        return f"Run: {action['command']}"
    if kind == "shortcut":
        return f"Press {hotkeys.pretty_combo(action['keys'])}"
    if kind == "disabled":
        return "Does nothing"
    return "?"


def _expression(action):
    kind = action.get("kind")
    if kind == "hotkey":
        return f"hotkey({lua_string(action['keys'])})"
    if kind == "command":
        return f"command({lua_string(action['command'])})"
    if kind == "shortcut":
        *mods, key = action["keys"].split("+")
        return f"shortcut({lua_string(' '.join(mods))}, {lua_string(key)})"
    if kind == "disabled":
        return "disabled()"
    return None


def render(actions, names):
    lines = [HEADER]
    for code in sorted(actions):
        expression = _expression(actions[code])
        if expression:
            description = f"Mouse {names.get(code, f'button {code}').lower()}: {describe(actions[code])}"
            lines.append(f"button({lua_string(f'mouse:{code}')}, {lua_string(description)}, {expression})")
    return "\n".join(lines) + "\n"


def ensure_wiring():
    """Make sure hyprland.lua loads our two modules (survives `omarchy refresh hyprland`)."""
    if not os.path.exists(CAPTURE) or open(CAPTURE).read() != open(CAPTURE_SOURCE).read():
        shutil.copyfile(CAPTURE_SOURCE, CAPTURE)
    if not os.path.exists(MODULE):
        write_module({}, {})

    text = open(MAIN).read()
    changed = text
    if CAPTURE_REQUIRE not in changed and OMARCHY_REQUIRE in changed:
        changed = changed.replace(
            OMARCHY_REQUIRE,
            "-- hyprmouse: remember hotkey actions so mouse buttons can reuse them.\n"
            f"{CAPTURE_REQUIRE}\n\n{OMARCHY_REQUIRE}",
            1,
        )
    if MODULE_REQUIRE not in changed:
        changed = changed.rstrip("\n") + (
            "\n\n-- Mouse buttons configured with hyprmouse (Omarchy menu > Setup > Mouse).\n"
            f"{MODULE_REQUIRE}\n"
        )
    if changed != text:
        shutil.copyfile(MAIN, f"{MAIN}.bak.hyprmouse.{int(time.time())}")
        with open(MAIN, "w") as f:
            f.write(changed)


def write_module(actions, names):
    with open(MODULE + ".tmp", "w") as f:
        f.write(render(actions, names))
    os.replace(MODULE + ".tmp", MODULE)


def reload():
    """Reload Hyprland; returns a list of config errors (empty when all is well)."""
    try:
        subprocess.run(["hyprctl", "reload"], capture_output=True, timeout=10)
        out = subprocess.run(["hyprctl", "configerrors"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired) as error:
        return [str(error)]
    return [line for line in out.splitlines() if line.strip()]


def apply(actions, names):
    """Write the module and reload. On a config error, put the old module back."""
    previous = open(MODULE).read() if os.path.exists(MODULE) else None
    write_module(actions, names)
    errors = reload()
    if errors and previous is not None:
        with open(MODULE, "w") as f:
            f.write(previous)
        reload()
    return errors


def remove_wiring():
    """Undo ensure_wiring (for `omarchy-hyprmouse --uninstall`). Leaves a backup of hyprland.lua."""
    if os.path.exists(MAIN):
        lines = open(MAIN).read().split("\n")
        keep = [line for line in lines
                if line.strip() not in (CAPTURE_REQUIRE, MODULE_REQUIRE) and "hyprmouse" not in line]
        if keep != lines:
            shutil.copyfile(MAIN, f"{MAIN}.bak.hyprmouse.{int(time.time())}")
            with open(MAIN, "w") as f:
                f.write("\n".join(keep))
    for path in (MODULE, CAPTURE):
        if os.path.exists(path):
            os.remove(path)
