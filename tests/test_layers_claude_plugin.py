"""v0.9.1: the Claude plugin purpose for more than one language, the
pseudo-language that holds its shared files, the second language's hint, a
two-language composition, and what a created project's push runs.

Design: 2026-10-22__22-06-57__dev-workflow-process__0-9-x-parity-with-the-old-route.md
(row 0.9.1); the proof tests/one-offs/thinking/p4-poc-neutral-purpose/.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from repokit import layers
from repokit.template_engine import TemplateEngine, token_context
from .test_utils import RepoKitTestCase

ENGINE = TemplateEngine(verbose=0)
ROOT = layers.layers_root(ENGINE)
NEUTRAL = [".claude-plugin/marketplace.json", "plugin/.claude-plugin/plugin.json", "plugin/README.md"]


def _m():
    return layers.load_manifest(ROOT)


# --- the pseudo-language and the purpose for two languages ------------------

def test_a_bare_claude_plugin_resolves_to_each_languages_own_preset():
    for lang, own in (("python", "python/claude-plugin"), ("js-ts", "js-ts/claude-plugin")):
        r = layers.resolve(_m(), [lang], ["claude-plugin"])
        assert r.languages == [lang]
        assert own in r.names and "any/claude-plugin" in r.names
        assert r.archetype == own
        assert r.notes == []


def test_any_is_not_a_project_language():
    m = _m()
    with pytest.raises(layers.LayerError, match="not a project language"):
        layers.resolve(m, ["any"], None)
    assert "any" not in layers.known_languages(m)
    assert not any(line.startswith("any:") for line in layers.catalogue_lines(m))
    # implied through a language, the shared layer adds no language either
    assert layers.resolve(m, ["python"], ["any/claude-plugin"]).languages == ["python"]


def test_two_languages_and_a_bare_purpose_stay_ambiguous_between_the_real_ones():
    with pytest.raises(layers.LayerError) as e:
        layers.resolve(_m(), ["python", "js-ts"], ["claude-plugin"])
    assert "ambiguous" in str(e.value)
    assert "js-ts/claude-plugin" in str(e.value) and "python/claude-plugin" in str(e.value)
    assert "any/" not in str(e.value)


def test_repokit_list_python_shows_the_plugin_under_purpose():
    lines = layers.catalogue_lines(_m(), "python")
    assert any(l.strip().startswith("python/claude-plugin") for l in lines)
    assert any("purpose" in l and "claude-plugin" in l for l in lines)


# --- the second language's hint (Q261022-02) --------------------------------

def test_a_second_language_left_bare_is_said_out_loud():
    r = layers.resolve(_m(), ["python", "js-ts"], None)
    assert r.archetype == "python/pypi"
    assert any(n.startswith("js-ts got no preset of its own") and "repokit list js-ts" in n for n in r.notes)
    assert not any(n.startswith("python got no preset") for n in r.notes)


def test_the_primary_language_is_hinted_too_when_only_the_other_ones_layers_are_named():
    """Mutation P8 (0.9.1) survived without this: the first language left bare
    by a --with that names only the second language's layers."""
    r = layers.resolve(_m(), ["python", "js-ts"], ["js-ts/claude-plugin"])
    assert any(n.startswith("python got no preset of its own") for n in r.notes)
    assert not any(n.startswith("js-ts got no preset") for n in r.notes)


def test_no_hint_when_every_language_has_its_own_layers():
    assert layers.resolve(_m(), ["python"], None).notes == []
    r = layers.resolve(_m(), ["python", "js-ts"], ["js-ts/claude-plugin", "python/script"])
    assert not any("got no preset" in n for n in r.notes)


# --- a two-language composition ---------------------------------------------

def test_python_and_js_ts_with_the_js_plugin_and_the_python_script_assemble(tmp_path):
    m = _m()
    r = layers.resolve(m, ["python", "js-ts"], ["js-ts/claude-plugin", "python/script"])
    ctx = token_context({"project_name": "duo", "description": "two languages", "author": "A",
                         "author_email": "a@example.com", "github": {"username": "acme"}}, archetype=None)
    layers.assemble(ROOT, r.layers, str(tmp_path), ctx, engine=ENGINE)
    settings = (tmp_path / ".repokit-common.toml").read_text(encoding="utf-8")
    # the js plugin's settings win (purpose ranks after build): both manifests in step, npm test on push
    assert 'path = "package.json"' in settings and 'path = "plugin/.claude-plugin/plugin.json"' in settings
    assert "npm test" in settings
    assert (tmp_path / "VERSION").read_text(encoding="utf-8") == "0.1.0\n"
    for rel in NEUTRAL + ["duo.py", "package.json", ".github/workflows/ci-python.yml", ".github/workflows/ci-js-ts.yml"]:
        assert (tmp_path / rel).exists(), rel
    # every file two layers write ends with a writer that declared the override,
    # or both wrote the same bytes (VERSION, from two languages)
    writers = {}
    for folder, name in zip(r.layers, r.names):
        base = ROOT / folder
        for p in base.rglob("*"):
            if p.is_file() and not p.name.endswith(layers.APPEND) and "__pycache__" not in p.parts:
                writers.setdefault(p.relative_to(base).as_posix(), []).append((name, p))
    undeclared = []
    for rel, ws in writers.items():
        if len(ws) > 1:
            last_name, last = ws[-1]
            declared = set(m["layers"].get(last_name, {}).get("overrides", []))
            if rel not in declared and any(p.read_bytes() != last.read_bytes() for _, p in ws[:-1]):
                undeclared.append(rel)
    assert undeclared == []


def test_a_bare_claude_plugin_with_no_language_is_the_js_ts_one():
    r = layers.resolve(_m(), [], ["claude-plugin"])
    assert r.archetype == "js-ts/claude-plugin" and r.languages == ["js-ts"]


# --- created projects --------------------------------------------------------

def _git_bash():
    """Git's own bash (on Windows, `bash` on PATH can be WSL's, which has no
    Python and no project tools); elsewhere the PATH's."""
    if sys.platform == "win32":
        exec_path = subprocess.run(["git", "--exec-path"], capture_output=True, text=True).stdout.strip()
        candidate = Path(exec_path).parents[2] / "bin" / "bash.exe"
        if candidate.is_file():
            return str(candidate)
    return shutil.which("bash")


BASH = _git_bash()


def _run_pre_push(repo: Path) -> str:
    sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    refs = f"refs/heads/main {sha} refs/heads/main {'0' * 40}\n"
    r = subprocess.run([BASH, "scripts/repokit-common/hooks/pre-push", "origin", "https://example.invalid/x.git"],
                       cwd=str(repo), input=refs, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=300)
    return r.stdout + r.stderr


@pytest.mark.integration
class TestCreatedPlugins(RepoKitTestCase):

    def test_the_python_plugin_is_nested_and_its_own_tests_pass(self):
        self.assert_repokit_success(["create", "py-plug", "--language", "python", "--with", "claude-plugin",
                                     "--description", "a plugin", "--no-push"])
        repo = Path(self.test_dir, "py-plug")
        for rel in NEUTRAL + ["plugin/hooks/hooks.json", "plugin/hooks/scripts/run-hook.mjs",
                              "plugin/hooks/scripts/session_start.py", "plugin/tests/test_manifest.py", "VERSION"]:
            self.assertTrue((repo / rel).exists(), rel)
        self.assertFalse((repo / "pyproject.toml").exists())          # a plugin, not a package
        meta = json.loads((repo / ".repokit.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["languages"], ["python"])
        self.assertEqual(meta["archetype"], "python/claude-plugin")
        self.assertIn("any/claude-plugin", meta["layers"])
        r = subprocess.run([sys.executable, "-m", "pytest", "plugin/tests", "-q", "-p", "no:cacheprovider"],
                           cwd=str(repo), capture_output=True, text=True, timeout=300)
        self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-2000:])

    @pytest.mark.skipif(BASH is None or shutil.which("node") is None or shutil.which("npm") is None,
                        reason="bash, node and npm are needed to run a js-ts project's push hook")
    def test_a_js_ts_plugins_push_runs_its_node_tests_and_no_python_tests(self):
        self.assert_repokit_success(["create", "js-plug", "--language", "js-ts", "--with", "claude-plugin", "--no-push"])
        out = _run_pre_push(Path(self.test_dir, "js-plug"))
        self.assertIn("Product languages: javascript", out)
        self.assertIn("node --test", out)                   # npm test ran the plugin's node tests
        self.assertNotIn("No Python package directory", out)
        self.assertNotIn("tests/test_*.py", out)            # the pytest default no longer stands in
        self.assertIn("Pre-push validation complete", out)

    @pytest.mark.xfail(strict=True, reason="git-repokit-common 0.4.1 prints its Python syntax check for every "
                                            "project; a repokit-common change, booked for djdarcy (0.9.x goal, "
                                            "read-only there). When it lands this test passes and the marker goes.")
    @pytest.mark.skipif(BASH is None, reason="bash runs the push hook")
    def test_a_js_ts_projects_push_prints_no_python_line(self):
        self.assert_repokit_success(["create", "js-def", "--language", "js-ts", "--no-push"])
        out = _run_pre_push(Path(self.test_dir, "js-def"))
        self.assertIn("Product languages: typescript", out)
        self.assertNotIn("Python", out)
