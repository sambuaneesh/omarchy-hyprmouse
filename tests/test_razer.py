from hyprmouse import drivers
from hyprmouse.drivers import razer


def test_report_layout_and_crc():
    report = razer.build_report(0x1F, 0x02, 0x8C, bytes([0x01, 0x04, 0x00]), size=0x0A)
    assert len(report) == 90
    assert report[1] == 0x1F and report[5] == 0x0A and report[6:8] == b"\x02\x8c"
    assert report[8:11] == b"\x01\x04\x00"
    crc = 0
    for byte in report[2:88]:
        crc ^= byte
    assert report[88] == crc


def test_button_settings_round_trip():
    for setting in (drivers.DEFAULT, drivers.DISABLED, drivers.media(0x00CD)):
        action, params = razer.RazerDriver._encode(setting, 4)
        assert razer.RazerDriver._decode(action, params, 4) == setting


def test_vendor_software_mappings_are_reported_not_lost():
    other = razer.RazerDriver._decode(razer.ACTION_MOUSE, bytes([5]), 4)
    assert other.kind == "other" and "5" in other.label
