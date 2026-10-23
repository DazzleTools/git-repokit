"""The plugin's manifests parse, agree with VERSION, and the hook answers --
directly and through the node launcher Claude Code runs."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1]
ROOT = PLUGIN.parent
SCRIPTS = PLUGIN / "hooks" / "scripts"
EVENT = json.dumps({"hook_event_name": "SessionStart", "source": "startup"})


def test_plugin_json_names_the_plugin_and_carries_version():
    manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "__RK_PROJECT__"
    assert manifest["version"] == (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def test_marketplace_lists_this_plugin_from_plugin_folder():
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    assert any(p["source"] == "./plugin" and p["name"] == "__RK_PROJECT__" for p in market["plugins"])


def test_the_session_start_hook_returns_json():
    hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    assert "SessionStart" in hooks["hooks"]
    r = subprocess.run([sys.executable, str(SCRIPTS / "session_start.py")], input=EVENT,
                       capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    json.loads(r.stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not on PATH")
def test_the_node_launcher_runs_the_python_hook():
    r = subprocess.run(["node", str(SCRIPTS / "run-hook.mjs"), "session_start.py"], input=EVENT,
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    json.loads(r.stdout)
