import shutil
import subprocess

import pytest

from hyprmouse import devices, hypr

ACTIONS = {
    275: {"kind": "hotkey", "keys": "SUPER+CTRL+TAB", "label": "Former workspace"},
    276: {"kind": "command", "command": 'notify-send "hi \\ there"'},
    277: {"kind": "shortcut", "keys": "CTRL+SHIFT+T"},
    278: {"kind": "disabled"},
}


def test_render_binds_each_button():
    lua = hypr.render(ACTIONS, devices.BUTTON_NAMES)
    assert 'button("mouse:275", "Mouse side button (back): Former workspace", hotkey("SUPER+CTRL+TAB"))' in lua
    assert 'shortcut("CTRL SHIFT", "T")' in lua
    assert "disabled()" in lua


def test_lua_string_escapes():
    assert hypr.lua_string('a"b\\c\nd') == '"a\\"b\\\\c\\nd"'


@pytest.mark.skipif(not shutil.which("luac"), reason="luac not installed")
def test_generated_lua_and_capture_module_parse(tmp_path):
    module = tmp_path / "module.lua"
    module.write_text(hypr.render(ACTIONS, devices.BUTTON_NAMES))
    for path in (module, hypr.CAPTURE_SOURCE):
        subprocess.run(["luac", "-p", str(path)], check=True)
