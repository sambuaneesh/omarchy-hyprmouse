"""Command line entry point."""

import argparse
import os
import sys

from . import __version__


def repair():
    """Re-wire Hyprland after `omarchy refresh hyprland` or an update (no UI)."""
    from . import devices, hypr, integration
    from .store import Store

    before = open(hypr.MAIN).read() if os.path.exists(hypr.MAIN) else None
    hypr.ensure_wiring()
    integration.ensure()
    store = Store()
    wanted = hypr.render(store.buttons, devices.BUTTON_NAMES)
    current = open(hypr.MODULE).read() if os.path.exists(hypr.MODULE) else None
    if current != wanted or open(hypr.MAIN).read() != before:
        if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
            errors = hypr.apply(store.buttons, devices.BUTTON_NAMES)
        else:
            hypr.write_module(store.buttons, devices.BUTTON_NAMES)
            errors = []
        suffix = f" ({'; '.join(errors)})" if errors else ""
        print(f"omarchy-hyprmouse: restored mouse button bindings{suffix}")


def uninstall():
    from . import hypr, integration

    hypr.remove_wiring()
    integration.remove()
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        hypr.reload()
    print("omarchy-hyprmouse: removed its Hyprland wiring, menu entry and hooks.")
    print("Settings stored inside your mouse stay as they are; your choices are kept in")
    print("~/.config/omarchy-hyprmouse in case you reinstall.")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="omarchy-hyprmouse",
        description="Mouse buttons, lighting and sensitivity for Omarchy / Hyprland. "
        "Run without options to open the app.",
    )
    parser.add_argument("--version", action="version", version=f"omarchy-hyprmouse {__version__}")
    parser.add_argument("--doctor", action="store_true", help="show detected mice, profiles and wiring")
    parser.add_argument("--scan", action="store_true", help="with --doctor: also dump raw device state")
    parser.add_argument("--repair", action="store_true", help="re-wire Hyprland (used by Omarchy hooks)")
    parser.add_argument("--udev-rules", action="store_true", help="print udev rules for all known mice")
    parser.add_argument("--uninstall", action="store_true",
                        help="remove the Hyprland wiring, menu entry and hooks from your config")
    args = parser.parse_args(argv)

    if args.doctor:
        from . import doctor

        print(doctor.report(scan=args.scan))
    elif args.repair:
        repair()
    elif args.udev_rules:
        from . import permissions

        sys.stdout.write(permissions.local_rules())
    elif args.uninstall:
        uninstall()
    else:
        from .app import HyprMouse

        HyprMouse().run()
