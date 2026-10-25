import pytest

from hyprmouse import hotkeys
from hyprmouse.dialogs import validate_command, validate_shortcut


@pytest.mark.parametrize("text, combo", [
    ("ctrl+shift+t", "CTRL+SHIFT+T"),
    ("Shift + Ctrl + t", "CTRL+SHIFT+T"),
    ("super w", "SUPER+W"),
    ("alt+left", "ALT+Left"),
    ("F5", "F5"),
    ("ctrl+pgup", "CTRL+Page_Up"),
])
def test_shortcuts_parse(text, combo):
    assert validate_shortcut(text)[0] == combo


@pytest.mark.parametrize("text", ["", "ctrl", "ctrl+a+b", "ctrl+banana"])
def test_bad_shortcuts_rejected(text):
    assert validate_shortcut(text)[0] is None


def test_command_trimmed():
    assert validate_command("  nautilus ")[0] == "nautilus"
    assert validate_command("   ")[0] is None


def test_hotkey_normalization_matches_lua():
    assert hotkeys.normalize("Shift + SUPER + code:10") == "SUPER+SHIFT+CODE:10"
    assert hotkeys.pretty_combo("SUPER+SHIFT+CODE:10") == "Super + Shift + 1"
