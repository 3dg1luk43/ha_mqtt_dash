from helpers import FakeState, make_bridge


def _widgets(doc):
    return {w["id"]: w for pg in doc["ui"]["pages"] for w in pg["widgets"]}


def _build(states=None):
    mb, bridge, hass, _ = make_bridge(states)
    return mb, bridge, _widgets(bridge._build_config_for_device(bridge.cfg["devices"][0], bridge.cfg))


def test_light_gets_attr_base_and_brightness_topic():
    _, _, w = _build()
    assert w["l1"]["attr_base"] == "mqttdash/statestream/light/living/attributes"
    assert w["l1"]["attr_topic"].endswith("/attributes/brightness")
    assert w["l2"]["dimmable"] is False and "attr_topic" not in w["l2"]


def test_mediaplayer_art_topic():
    _, _, w = _build()
    assert w["m1"]["art_topic"] == "mqttdash/art/media_player.spotify"
    assert w["m1"]["attr_base"].endswith("media_player/spotify/attributes")


def test_camera_entity_frame_topic_and_interval_clamped():
    _, _, w = _build()
    assert w["cam"]["camera_entity"] == "camera.printer"
    assert w["cam"]["frame_topic"] == "mqttdash/camera/camera.printer/frame"
    assert w["cam"]["refresh_interval"] == 0.2  # clamped to the minimum
    assert w["cam"]["overlay"]["command_topic"] == "mqttdash/cmd/light.printer"


def test_printer_extra_topics():
    _, _, w = _build()
    assert w["p1"]["preview_topic"] == "mqttdash/art/image.k1c_preview"
    assert w["p1"]["layer_topic"] == "mqttdash/statestream/sensor/k1c_layer/state"
    assert w["p1"]["nozzle_target_topic"] == "mqttdash/statestream/number/k1c_nozzle_target/state"


def test_timer_presets_sanitised_and_climate_step():
    _, _, w = _build()
    assert w["t1"]["presets"] == [60, 300]
    assert w["c1"]["temp_step"] == 0.5


def test_appliance_siblings_inferred_only_when_they_exist():
    _, _, w = _build({"sensor.washer_progress": FakeState("42")})
    assert w["a1"]["progress_topic"] == "mqttdash/statestream/sensor/washer_progress/state"
    assert "phase_topic" not in w["a1"]  # sensor.washer_current_phase does not exist


def test_mirror_includes_inferred_siblings():
    mb, _, hass, _ = make_bridge({"sensor.washer_current_phase": FakeState("rinse")})
    from helpers import sample_profiles
    ents = mb._extract_entities_from_profiles(sample_profiles(), hass)
    assert "sensor.washer_current_phase" in ents
    assert "sensor.k1c_layer" in ents and "number.k1c_nozzle_target" in ents


def test_relay_entities():
    mb, *_ = make_bridge()
    from helpers import sample_profiles
    art, cams = mb._relay_entities(sample_profiles())
    assert art == {"media_player.spotify", "image.k1c_preview"}
    assert cams == {"camera.printer"}
