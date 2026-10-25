"""Access to mouse device nodes without a password, via udev `uaccess` rules.

The package installs a rule for the built-in profiles (70-omarchy-hyprmouse.rules).
For mice described only by your own profiles, or when running from a git
checkout, the app offers a one-time setup that writes 71-omarchy-hyprmouse-local.rules
with a single polkit password prompt. Only mice are covered, never keyboards.
"""

import os
import re
import subprocess
import sys
import tempfile

from . import profiles

LOCAL_RULE = "/etc/udev/rules.d/71-omarchy-hyprmouse-local.rules"

# A generated rule only ever matches devices and adds the uaccess tag.
_SAFE_LINE = re.compile(r'^(#.*|\s*|(SUBSYSTEM|KERNEL|ATTRS\{\w+\}|ENV\{\w+\})[!=]="[^"]*"(, (SUBSYSTEM|KERNEL|ATTRS\{\w+\}|ENV\{\w+\})[!=]="[^"]*")*, TAG\+="uaccess")$')


def local_rules():
    by_usb, _ = profiles.load_all()
    unique = {p.path: p for p in by_usb.values()}.values()
    return profiles.udev_rules(unique)


def install(sysfs_paths):
    """Run as the user: one polkit prompt, then the rule applies to these nodes."""
    with tempfile.NamedTemporaryFile("w", suffix=".rules", delete=False) as f:
        f.write(local_rules())
        rule_file = f.name
    try:
        command = ["pkexec", sys.executable, "-I", os.path.abspath(__file__), "install", rule_file, *sysfs_paths]
        result = subprocess.run(command, capture_output=True, text=True)
    finally:
        os.unlink(rule_file)
    if result.returncode in (126, 127):
        return "Permission was not granted."
    if result.returncode != 0:
        return (result.stderr or result.stdout).strip() or "Setup failed."
    return None


def _root_install(rule_file, paths):
    text = open(rule_file).read()
    if not all(_SAFE_LINE.match(line) for line in text.splitlines()):
        sys.exit("refusing to install: unexpected content in rules")
    with open(LOCAL_RULE, "w") as f:
        f.write(text)
    os.chmod(LOCAL_RULE, 0o644)
    subprocess.run(["udevadm", "control", "--reload-rules"], check=True)
    safe = [p for p in paths if p.startswith(("/sys/class/hidraw/", "/sys/class/input/")) and ".." not in p]
    if safe:
        subprocess.run(["udevadm", "trigger", "--action=change", *safe], check=True)
        subprocess.run(["udevadm", "settle", "--timeout=5"])


if __name__ == "__main__" and len(sys.argv) >= 3 and sys.argv[1] == "install":
    if os.geteuid() != 0:
        sys.exit("must run as root")
    _root_install(sys.argv[2], sys.argv[3:])
