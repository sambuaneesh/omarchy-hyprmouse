"""`omarchy-hyprmouse --doctor`: what's detected and wired, for bug reports and new profiles."""

import os

from . import __version__, devices, hypr, integration, profiles
from .drivers import DriverError, describe
from .store import Store


def _mark(ok):
    return "ok " if ok else "-- "


def report(scan=False):
    lines = [f"omarchy-hyprmouse {__version__}", ""]

    main = open(hypr.MAIN).read() if os.path.exists(hypr.MAIN) else ""
    lines += [
        "Hyprland",
        f"  {_mark(hypr.CAPTURE_REQUIRE in main)}hotkey capture required in hyprland.lua",
        f"  {_mark(hypr.MODULE_REQUIRE in main)}button module required in hyprland.lua",
        f"  {_mark(os.path.exists(hypr.MODULE))}{hypr.MODULE}",
        f"  {_mark(integration.omarchy_present())}Omarchy config found",
        "",
    ]

    by_usb, errors = profiles.load_all()
    lines.append("Profiles")
    for path in profiles.files():
        where = "user" if path.startswith(profiles.USER_DIR) else "built-in"
        if path in errors:
            lines.append(f"  !! {path}: {errors[path]}")
        else:
            profile = profiles.load(path)
            ids = ", ".join(f"{v:04x}:{p:04x}" for v, p in profile.usb)
            lines.append(f"  ok {profile.name} [{profile.driver}] {ids} ({where})")
    lines.append("")

    mice = devices.find_mice(by_usb)
    lines.append("Mice")
    if not mice:
        lines.append("  none with configurable buttons")
    for mouse in mice:
        lines.append(f"  {mouse.name}  {mouse.vendor:04x}:{mouse.product:04x}")
        lines.append(f"    buttons (Linux codes): {', '.join(map(str, mouse.button_codes()))}")
        lines.append(f"    input nodes: {', '.join(mouse.event_nodes)}")
        readable = any(os.access(n, os.R_OK) for n in mouse.event_nodes)
        lines.append(f"    {_mark(readable)}can see button presses")
        if not mouse.profile:
            lines.append("    no profile: buttons can be remapped through Hyprland; nothing stored in the mouse")
            lines.append("    (see CONTRIBUTING.md to add one)")
            continue
        lines.append(f"    profile: {mouse.profile.path}")
        if not mouse.driver_class:
            lines.append(f"    !! no driver named {mouse.profile.driver!r}")
            continue
        lines.append(f"    control node: {mouse.control or 'not found'}")
        if not mouse.control:
            continue
        access = os.access(mouse.control, os.R_OK | os.W_OK)
        lines.append(f"    {_mark(access)}can talk to the mouse")
        if not access:
            continue
        try:
            driver = mouse.driver_class(mouse)
        except OSError as error:
            lines.append(f"    !! {error}")
            continue
        try:
            for code in sorted(mouse.profile.buttons):
                lines.append(f"    button {code} ({mouse.button_name(code)}): {_safe(lambda c: describe(driver.get_button(c)), code)}")
            for zone in mouse.profile.zones:
                lines.append(f"    lighting {zone.key}: {_safe(driver.get_lighting, zone.key)}")
            if mouse.profile.dpi:
                lines.append(f"    dpi: {_safe(driver.get_dpi)}")
            if mouse.profile.poll_rates:
                lines.append(f"    polling rate: {_safe(driver.get_poll_rate)}")
            if scan:
                lines.append("    raw scan:")
                lines += [f"      {line}" for line in driver.scan()]
        finally:
            driver.close()
    lines.append("")

    buttons = Store().buttons
    lines.append("Button actions (Hyprland)")
    lines += [f"  mouse:{code}: {hypr.describe(action)}" for code, action in sorted(buttons.items())] or ["  none"]
    return "\n".join(lines)


def _safe(call, *args):
    try:
        return call(*args)
    except (OSError, DriverError, NotImplementedError) as error:
        return f"error: {error}"
