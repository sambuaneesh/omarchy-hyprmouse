import os

import pytest

from hyprmouse import drivers, profiles

ROOT = os.path.dirname(os.path.dirname(__file__))
PACKAGED_RULES = os.path.join(ROOT, "packaging", "70-omarchy-hyprmouse.rules")


def builtin():
    return [profiles.load(p) for p in profiles.files(include_user=False)]


def test_builtin_profiles_load_and_use_known_drivers():
    loaded = builtin()
    assert loaded, "no built-in profiles found"
    for profile in loaded:
        assert drivers.get(profile.driver), f"{profile.path}: unknown driver {profile.driver}"


def test_usb_ids_are_unique_across_builtin_profiles():
    seen = {}
    for profile in builtin():
        for usb in profile.usb:
            assert usb not in seen, f"{usb} in both {seen.get(usb)} and {profile.path}"
            seen[usb] = profile.path


def test_packaged_udev_rules_match_profiles():
    """Regenerate with: python -m hyprmouse --udev-rules > packaging/70-omarchy-hyprmouse.rules
    (from a checkout with no user profiles)."""
    assert open(PACKAGED_RULES).read() == profiles.udev_rules(builtin())


def test_udev_rules_only_tag_listed_products():
    rules = profiles.udev_rules(builtin())
    assert 'ATTRS{idVendor}=="1532", ATTRS{idProduct}=="006e|0071|0098"' in rules
    assert "RUN" not in rules


@pytest.mark.parametrize("data, message", [
    ({"driver": "razer", "usb": ["1532:0098"]}, "missing `name`"),
    ({"name": "x", "driver": "razer", "usb": ["nope"]}, "usb ids look like"),
    ({"name": "x", "driver": "razer", "usb": ["1532:0098"], "buttons": {"272": {"name": "L", "id": 1}}},
     "can't be remapped"),
    ({"name": "x", "driver": "razer", "usb": ["1532:0098"], "buttons": {"275": {"name": "B"}}},
     "needs `name` and `id`"),
    ({"name": "x", "driver": "razer", "usb": ["1532:0098"], "lighting": {"zones": [{"key": "tail"}]}},
     "lighting zone"),
    ({"name": "x", "driver": "razer", "usb": ["1532:0098"], "performance": {"dpi": [800, 100, 50]}},
     "performance.dpi"),
])
def test_bad_profiles_get_helpful_errors(data, message):
    with pytest.raises(profiles.ProfileError, match=message):
        profiles.parse("test.toml", data)


def test_user_profiles_override_builtin(tmp_path, monkeypatch):
    user = tmp_path / "profiles"
    user.mkdir()
    (user / "mine.toml").write_text('name = "My test mouse"\ndriver = "razer"\nusb = ["1532:0098"]\n')
    monkeypatch.setattr(profiles, "USER_DIR", str(user))
    by_usb, errors = profiles.load_all()
    assert not errors
    assert by_usb[(0x1532, 0x0098)].name == "My test mouse"
