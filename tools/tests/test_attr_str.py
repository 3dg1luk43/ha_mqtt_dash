import datetime

from helpers import make_bridge


def test_attribute_encoding():
    mb, *_ = make_bridge()
    s = mb._attr_str
    assert s(None) == ""
    assert s(True) == "true" and s(False) == "false"
    assert s(["onoff"]) == '["onoff"]'
    assert s(("a", 1)) == '["a", 1]'
    assert s({"x": 1}) == '{"x": 1}'
    assert s(22.5) == "22.5" and s("heat") == "heat"
    assert s(datetime.datetime(2026, 10, 30, 12, 0, 0)) == "2026-10-30T12:00:00"


def test_device_id_validation():
    mb, *_ = make_bridge()
    assert mb._valid_device_id("kitchen_ipad-1")
    for bad in ("", "a/b", "x#", "a+b", "with space", "x" * 65, None):
        assert not mb._valid_device_id(bad)
