"""Razer mice: the 90-byte HID feature-report protocol used by Razer Synapse.

Command classes and ids follow OpenRazer's driver (driver/razermouse_driver.c,
razerchromacommon.c). Button remapping (class 0x02) was verified on a
DeathAdder Essential (2021) by writing every button and reading it back.

Profile options ([razer] table):
  interface       USB interface carrying the feature report (usually 0)
  transaction_id  { buttons = .., misc = .., lighting = .. } per command family
Button ids are the profile's `id` per button; lighting zones carry `led`.
"""

import fcntl
import glob
import os
import time

from . import DEFAULT, DISABLED, MEDIA_KEYS, ButtonSetting, Driver, DriverError, media, register

VARSTORE = 0x01  # persist in the mouse's flash
NOSTORE = 0x00  # what the mouse is doing right now

STATUS_BUSY, STATUS_OK = 0x01, 0x02

ACTION_DISABLED, ACTION_MOUSE, ACTION_MEDIA = 0x00, 0x01, 0x0A

EFFECTS = {"off": 0x00, "static": 0x01, "breathing": 0x02}
POLL_RATES = {1000: 0x01, 500: 0x02, 125: 0x08}

DEFAULT_TIDS = {"buttons": 0x1F, "misc": 0xFF, "lighting": 0x3F}


def build_report(tid, cls, cid, args=b"", size=None):
    """The 90-byte request: status, transaction id, ..., size, class, id, args, crc."""
    report = bytearray(90)
    report[1] = tid
    report[5] = len(args) if size is None else size
    report[6], report[7] = cls, cid
    report[8:8 + len(args)] = args
    crc = 0
    for byte in report[2:88]:
        crc ^= byte
    report[88] = crc
    return bytes(report)


def _ioc(nr, size):
    return (3 << 30) | (size << 16) | (ord("H") << 8) | nr


def _usb_interface(sysfs_path):
    for part in reversed(os.path.realpath(sysfs_path).split("/")):
        if ":" in part and "-" in part:
            return int(part.split(".")[-1])
    return None


@register
class RazerDriver(Driver):
    name = "razer"

    @classmethod
    def control_node(cls, mouse):
        interface = mouse.profile.options.get("interface", 0)
        for node in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
            device = node + "/device"
            if os.path.realpath(device).startswith(mouse.usb_path + "/") and _usb_interface(device) == interface:
                return "/dev/" + os.path.basename(node)
        return None

    def __init__(self, mouse):
        super().__init__(mouse)
        self.tids = {**DEFAULT_TIDS, **self.profile.options.get("transaction_id", {})}
        self.fd = os.open(mouse.control, os.O_RDWR)  # PermissionError until access is set up

    def close(self):
        os.close(self.fd)

    def _command(self, family, cls, cid, args=b"", size=None):
        report = build_report(self.tids[family], cls, cid, args, size)
        resp = b"\0" * 90
        for _ in range(3):
            fcntl.ioctl(self.fd, _ioc(0x06, 91), bytes(1) + report)
            for _ in range(30):
                time.sleep(0.008)
                buf = bytearray(91)
                fcntl.ioctl(self.fd, _ioc(0x07, 91), buf)
                resp = bytes(buf[1:])
                if resp[0] != STATUS_BUSY:
                    break
            if resp[0] == STATUS_OK and resp[6] == cls and resp[7] == cid:
                return resp[8:88]
        raise DriverError(f"mouse rejected command {cls:02x}:{cid:02x} (status {resp[0]:#x})")

    # Buttons

    def _button(self, code):
        button = self.profile.buttons[code]
        return button.id, button.native

    def media_keys(self):
        return {usage: label for usage, (label, _) in MEDIA_KEYS.items()}

    def _read_raw(self, button_id, profile=VARSTORE):
        args = self._command("buttons", 0x02, 0x8C, bytes([profile, button_id, 0]), size=0x0A)
        return args[3], bytes(args[5:5 + args[4]])

    def get_button(self, code):
        button_id, native = self._button(code)
        action, params = self._read_raw(button_id)
        return self._decode(action, params, native)

    @staticmethod
    def _decode(action, params, native):
        if action == ACTION_DISABLED:
            return DISABLED
        if action == ACTION_MOUSE and params:
            if params[0] == native:
                return DEFAULT
            return ButtonSetting("other", label=f"Acts as mouse button {params[0]}")
        if action == ACTION_MEDIA and len(params) >= 2:
            return media(int.from_bytes(params[:2], "big"))
        return ButtonSetting("other", label="Custom (set by Razer Synapse)")

    @staticmethod
    def _encode(setting, native):
        if setting.kind == "default":
            return ACTION_MOUSE, bytes([native])
        if setting.kind == "disabled":
            return ACTION_DISABLED, b""
        if setting.kind == "media":
            return ACTION_MEDIA, setting.value.to_bytes(2, "big")
        raise ValueError(f"can't store {setting.kind!r} in a Razer mouse")

    def set_button(self, code, setting):
        button_id, native = self._button(code)
        action, params = self._encode(setting, native)
        args = bytes([button_id, 0, action, len(params)]) + params
        # Keep what the mouse does now (0) and after replugging (1) in step.
        for profile in (NOSTORE, VARSTORE):
            self._command("buttons", 0x02, 0x0C, bytes([profile]) + args, size=0x0A)
        if self.get_button(code) != setting:
            raise DriverError("the mouse did not keep the new button setting")

    # Lighting

    def _led(self, zone):
        return self.profile.zone(zone).options["led"]

    def get_lighting(self, zone):
        led = self._led(zone)
        args = self._command("lighting", 0x0F, 0x82, bytes([VARSTORE, led]), size=0x0C)
        effect = {code: name for name, code in EFFECTS.items()}.get(args[2])
        args = self._command("lighting", 0x0F, 0x84, bytes([VARSTORE, led]), size=0x03)
        return effect, round(args[2] * 100 / 255)

    def set_effect(self, zone, effect):
        led = self._led(zone)
        # Keep the colour the mouse already has (single-colour mice ignore it).
        current = self._command("lighting", 0x0F, 0x82, bytes([VARSTORE, led]), size=0x0C)
        rgb = bytes(current[6:9]) if any(current[6:9]) else b"\x00\xff\x00"
        args = bytearray([VARSTORE, led, EFFECTS[effect], 0, 0, 0, 0, 0, 0])
        if effect == "static":
            args[5] = 0x01
            args[6:9] = rgb
        elif effect == "breathing":
            args[3], args[5] = 0x01, 0x01
            args[6:9] = rgb
        self._command("lighting", 0x0F, 0x02, bytes(args), size=0x06 if effect == "off" else 0x09)

    def set_brightness(self, zone, percent):
        value = round(max(0, min(100, percent)) * 255 / 100)
        self._command("lighting", 0x0F, 0x04, bytes([VARSTORE, self._led(zone), value]), size=0x03)

    # Performance

    def get_dpi(self):
        args = self._command("misc", 0x04, 0x85, bytes([NOSTORE]), size=0x07)
        return int.from_bytes(args[1:3], "big")

    def set_dpi(self, dpi):
        low, high, _ = self.profile.dpi
        dpi = max(low, min(high, int(dpi)))
        value = dpi.to_bytes(2, "big")
        self._command("misc", 0x04, 0x05, bytes([VARSTORE]) + value + value + b"\0\0", size=0x07)
        return dpi

    def get_poll_rate(self):
        args = self._command("misc", 0x00, 0x85, size=0x01)
        return {code: hz for hz, code in POLL_RATES.items()}.get(args[0])

    def set_poll_rate(self, hz):
        self._command("misc", 0x00, 0x05, bytes([POLL_RATES[hz]]), size=0x01)

    # Diagnostics

    def scan(self):
        lines = []
        try:
            args = self._command("misc", 0x00, 0x81, size=0x02)
            lines.append(f"firmware: v{args[0]}.{args[1]}")
        except DriverError as error:
            lines.append(f"firmware: {error}")
        lines.append("onboard buttons that answer (id: action params):")
        for button_id in range(0x01, 0x70):
            try:
                action, params = self._read_raw(button_id)
            except DriverError:
                continue
            lines.append(f"  {button_id:#04x}: action {action:#04x} params {params.hex(' ') or '-'}")
        lines.append("lighting LEDs that answer (led: effect, brightness):")
        for led in (0x00, 0x01, 0x04, 0x05, 0x0A, 0x0B, 0x0C, 0x0D):
            try:
                effect = self._command("lighting", 0x0F, 0x82, bytes([VARSTORE, led]), size=0x0C)[2]
                bright = self._command("lighting", 0x0F, 0x84, bytes([VARSTORE, led]), size=0x03)[2]
            except DriverError:
                continue
            lines.append(f"  {led:#04x}: effect {effect:#04x}, brightness {bright}")
        return lines
