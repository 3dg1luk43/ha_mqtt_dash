import json
import re
import subprocess
import sys

from conftest import ROOT

COMP = ROOT / "custom_components" / "ha_mqtt_dash"


def test_manifest():
    m = json.loads((COMP / "manifest.json").read_text())
    assert m["domain"] == "ha_mqtt_dash"
    assert re.match(r"^\d+\.\d+\.\d+", m["version"])
    # The editor panel needs these; hassfest also checks they are declared
    assert {"frontend", "http", "mqtt", "panel_custom", "websocket_api"} <= set(m["dependencies"])


def test_editor_bundle_matches_sources():
    sys.path.insert(0, str(ROOT / "tools"))
    from editor_hash import source_hash

    manifest = json.loads((COMP / "editor" / "build-manifest.json").read_text())
    assert manifest["source_hash"] == source_hash(), "editor bundle is stale: run tools/build_editor.sh and commit it"
    assert (COMP / "editor" / "index.html").is_file()
    assert (COMP / "frontend" / "mqttdash-editor-panel.js").is_file()


def test_panel_module_is_valid_js():
    node = subprocess.run(["node", "--check", str(COMP / "frontend" / "mqttdash-editor-panel.js")], capture_output=True, text=True)
    assert node.returncode == 0, node.stderr


def test_hacs_json():
    h = json.loads((ROOT / "hacs.json").read_text())
    assert h.get("name")
