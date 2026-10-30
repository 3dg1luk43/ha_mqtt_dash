import json
import re

from conftest import ROOT

COMP = ROOT / "custom_components" / "ha_mqtt_dash"


def _strings():
    return json.loads((COMP / "strings.json").read_text(encoding="utf-8"))


def test_strings_and_english_translation_identical():
    assert _strings() == json.loads((COMP / "translations" / "en.json").read_text(encoding="utf-8"))


def _flow_sections():
    src = (COMP / "config_flow.py").read_text(encoding="utf-8")
    cut = src.index("class OptionsFlowHandler")
    return {"config": src[:cut], "options": src[cut:]}


def test_every_flow_step_menu_item_and_abort_has_text():
    strings = _strings()
    for section, src in _flow_sections().items():
        t = strings[section]
        for step in set(re.findall(r'step_id="(\w+)"', src)):
            assert step in t["step"], f"{section}.step.{step} missing in strings.json"
        for reason in set(re.findall(r'async_abort\(reason="(\w+)"', src)):
            assert reason in t.get("abort", {}), f"{section}.abort.{reason} missing in strings.json"
        for block in re.findall(r"menu_options=\[(.*?)\]", src, re.S):
            for item in re.findall(r'"(\w+)"', block):
                assert item in t["step"]["init"]["menu_options"], f"{section} menu item {item} missing"
                assert item in t["step"], f"menu item {item} has no step text"


def test_description_placeholders_are_provided():
    strings = _strings()["options"]["step"]
    src = _flow_sections()["options"]
    for step_id, body in re.findall(r'step_id="(\w+)"[^)]*?description_placeholders=\{([^}]*)\}', src, re.S):
        provided = set(re.findall(r'"(\w+)":', body))
        used = set(re.findall(r"\{(\w+)\}", strings.get(step_id, {}).get("description", "")))
        assert used <= provided, f"{step_id}: placeholders {used - provided} not provided"
