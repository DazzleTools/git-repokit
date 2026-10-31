"""v0.9.2: `.vscode/launch.json` (and `tasks.json` where a build needs one) per
preset, from the layers; none from the structure; the primary language's in a
project of several languages.

Shapes from the measure of the 143 launch.json files on the development
machine (tests/one-offs/thinking/p4-measure-launchjson/results.md): debugpy
with justMyCode false for Python, cppvsdbg (and cppdbg off Windows) with a
build task for C/C++, node for JS/TS.
Design: 2026-10-22__22-06-57__dev-workflow-process__0-9-x-parity-with-the-old-route.md (row 0.9.2).
"""
import json
from pathlib import Path

import pytest

from repokit import layers
from repokit.template_engine import RK_TOKEN, TemplateEngine, token_context
from .test_utils import RepoKitTestCase

ENGINE = TemplateEngine(verbose=0)
ROOT = layers.layers_root(ENGINE)
CTX = token_context({"project_name": "my-tool", "description": "d", "author": "A",
                     "author_email": "a@example.com", "github": {"username": "acme"}}, archetype=None)

# every built preset with something to run, and the debugger its launch.json must name
EXPECTED = {
    "python/pypi": "debugpy", "python/setuppy": "debugpy", "python/script": "debugpy",
    "python/claude-plugin": "debugpy",
    "c-cpp/cmake-app": "cppvsdbg", "c-cpp/msbuild": "cppvsdbg", "c-cpp/minimal": "cppvsdbg",
    "js-ts/node-package": "node", "js-ts/script": "node", "js-ts/claude-plugin": "node",
}
# built presets with nothing VS Code runs or debugs: a Paradox mod is loaded by
# the game itself (0.10.0), so it gets no launch.json rather than a pretend one
NO_LAUNCH = {"paradox/ck3", "paradox/jomini", "paradox/clausewitz"}


def _assembled(tmp_path, preset):
    r = layers.resolve(layers.load_manifest(ROOT), [], [preset])
    dest = tmp_path / preset.replace("/", "-")
    dest.mkdir()
    layers.assemble(ROOT, r.layers, str(dest), CTX, engine=ENGINE)
    return dest


def test_every_built_preset_is_in_the_expectations():
    m = layers.load_manifest(ROOT)
    built = {k for k, v in m["archetypes"].items() if not v.get("stub")}
    assert built == set(EXPECTED) | NO_LAUNCH, sorted(built ^ (set(EXPECTED) | NO_LAUNCH))


@pytest.mark.parametrize("preset", sorted(NO_LAUNCH))
def test_a_preset_with_nothing_to_run_writes_no_launch_json(tmp_path, preset):
    assert not (_assembled(tmp_path, preset) / ".vscode" / "launch.json").exists()


@pytest.mark.parametrize("preset,debugger", sorted(EXPECTED.items()))
def test_each_preset_writes_a_launch_json_naming_its_debugger(tmp_path, preset, debugger):
    dest = _assembled(tmp_path, preset)
    text = (dest / ".vscode" / "launch.json").read_text(encoding="utf-8")
    assert not RK_TOKEN.search(text), "a token survived"
    launch = json.loads(text)                     # strict JSON: no comments in what we ship
    assert launch["version"] == "0.2.0"
    types = {c["type"] for c in launch["configurations"]}
    assert debugger in types
    if debugger == "debugpy":
        assert all(c.get("justMyCode") is False for c in launch["configurations"])
    # a preLaunchTask names a task this preset ships
    tasks_path = dest / ".vscode" / "tasks.json"
    labels = {t["label"] for t in json.loads(tasks_path.read_text(encoding="utf-8"))["tasks"]} if tasks_path.exists() else set()
    for c in launch["configurations"]:
        if "preLaunchTask" in c:
            assert c["preLaunchTask"] in labels, f"{preset}: {c['preLaunchTask']} has no task"


def test_the_package_and_the_script_launch_their_own_entry_points(tmp_path):
    pkg = json.loads((_assembled(tmp_path, "python/pypi") / ".vscode/launch.json").read_text(encoding="utf-8"))
    assert pkg["configurations"][0]["module"] == "my_tool"
    script = json.loads((_assembled(tmp_path, "js-ts/script") / ".vscode/launch.json").read_text(encoding="utf-8"))
    assert script["configurations"][0]["program"] == "${workspaceFolder}/my-tool.js"
    hook = json.loads((_assembled(tmp_path, "python/claude-plugin") / ".vscode/launch.json").read_text(encoding="utf-8"))
    assert hook["configurations"][0]["program"].endswith("plugin/hooks/scripts/session_start.py")
    assert hook["configurations"][0]["env"] == {"MY_TOOL_DEBUG": "1"}


def test_two_languages_get_the_primarys_launch_json_and_a_report(tmp_path):
    r = layers.resolve(layers.load_manifest(ROOT), ["js-ts", "python"], ["js-ts/script", "python/pypi"])
    skipped = []
    layers.assemble(ROOT, r.layers, str(tmp_path), CTX, engine=ENGINE, primary_language="js-ts", skipped=skipped)
    launch = json.loads((tmp_path / ".vscode/launch.json").read_text(encoding="utf-8"))
    assert {c["type"] for c in launch["configurations"]} == {"node"}
    assert skipped == ["python: .vscode/launch.json"]


def test_a_shared_layers_debugger_file_is_kept_in_a_two_language_project(tmp_path):
    """Mutation V1 (0.9.2) survived without this: the rule leaves out other
    languages' files, never the shared `any` layer's."""
    root = tmp_path / "layers"
    for folder, body in (("languages/python", "py"), ("languages/js-ts", "js"), ("archetypes/any/thing", "shared")):
        p = root / folder / ".vscode" / "tasks.json"
        p.parent.mkdir(parents=True)
        p.write_text(body, encoding="utf-8")
    dest = tmp_path / "out"
    dest.mkdir()
    skipped = []
    layers.assemble(root, ["languages/python", "languages/js-ts", "archetypes/any/thing"], str(dest), {},
                    engine=ENGINE, primary_language="python", skipped=skipped)
    assert (dest / ".vscode" / "tasks.json").read_text(encoding="utf-8") == "shared"
    assert skipped == ["js-ts: .vscode/tasks.json"]


@pytest.mark.integration
class TestCreatedVsCode(RepoKitTestCase):

    def test_generic_writes_no_launch_json_and_a_two_language_create_says_whose_it_is(self):
        self.assert_repokit_success(["create", "plain", "--language", "generic", "--no-push"])
        self.assertFalse(Path(self.test_dir, "plain", ".vscode", "launch.json").exists())
        code, out, err = self.run_repokit(["create", "duo", "--language", "python,js-ts", "--no-push"])
        self.assertEqual(code, 0, out[-2000:] + err[-2000:])
        self.assertIn(".vscode/ holds python's debug configurations; js-ts's were not merged in", out)
        launch = json.loads(Path(self.test_dir, "duo", ".vscode", "launch.json").read_text(encoding="utf-8"))
        self.assertEqual(launch["configurations"][0]["module"], "duo")
