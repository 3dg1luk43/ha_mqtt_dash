import types


class FakeRegistry:
    def __init__(self, entries):
        self.entries = {e.entity_id: e for e in entries}

    def async_get(self, entity_id):
        return self.entries.get(entity_id)

    def async_update_entity(self, entity_id, new_entity_id):
        e = self.entries.pop(entity_id)
        e.entity_id = new_entity_id
        self.entries[new_entity_id] = e


def _ent(entity_id, unique_id):
    return types.SimpleNamespace(entity_id=entity_id, unique_id=unique_id)


def test_reload_button_gets_new_entity_id(monkeypatch):
    import importlib
    integ = importlib.import_module("custom_components.ha_mqtt_dash")

    reg = FakeRegistry([
        _ent("button.kitchen_reload_device", "ha_mqtt_dash:kitchen:btn_reload"),
        _ent("button.hall_reload_device", "ha_mqtt_dash:hall:btn_reload"),
        _ent("button.hall_reload", "other:thing"),            # target taken: leave it
        _ent("button.my_custom_name", "ha_mqtt_dash:den:btn_reload"),  # user-chosen id: leave it
    ])
    monkeypatch.setattr(integ.er, "async_get", lambda hass: reg)
    monkeypatch.setattr(integ.er, "async_entries_for_config_entry", lambda r, eid: list(r.entries.values()))
    integ._migrate_entity_ids(object(), types.SimpleNamespace(entry_id="e1"))
    assert set(reg.entries) == {"button.kitchen_reload", "button.hall_reload_device", "button.hall_reload", "button.my_custom_name"}
