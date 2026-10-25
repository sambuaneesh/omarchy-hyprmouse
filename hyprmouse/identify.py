"""Wait for one mouse-button press, holding the mouse so the press does nothing else."""

import select
import time

import evdev
from evdev import ecodes



def wait_for_button(mouse, cancelled, timeout=20):
    """Linux button code of the next press, or None on timeout/cancel/no access.

    Buttons a mouse has turned into media keys arrive as key codes on its
    keyboard node; the caller maps those back with drivers.media_usage_for_key.
    """
    devices = []
    try:
        for path in mouse.event_nodes:
            try:
                device = evdev.InputDevice(path)
                device.grab()
                devices.append(device)
            except OSError:
                continue
        if not devices:
            return None

        deadline = time.monotonic() + timeout
        while not cancelled.is_set() and time.monotonic() < deadline:
            ready, _, _ = select.select(devices, [], [], 0.1)
            for device in ready:
                for event in device.read():
                    if event.type == ecodes.EV_KEY and event.value == 1:
                        return event.code
        return None
    finally:
        for device in devices:
            try:
                device.ungrab()
            except OSError:
                pass
            device.close()

