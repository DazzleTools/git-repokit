"""0.9.6: what a created project's README, badges, manifests and labels say.

The live golden (2026-10-24) and a real consumer's create found the README a
skeleton, its badges hard-coded (version 1.0.0, Python >=3.7, MIT), the
pypi preset's licence fixed at GPL, keywords empty, and labels the project's
own files name missing from the repository. These are the unit checks of the
pieces that now say what the project is.
"""
import json
import re
from pathlib import Path

from repokit import licenses, readme_blocks
from repokit.github_setup import GhSetup, referenced_labels
from repokit.template_engine import token_context

LAYERS = Path(__file__).resolve().parents[1] / "repokit" / "templates" / "layers" / "archetypes"

# PyPI's licence classifiers, from https://pypi.org/pypi?%3Aaction=list_classifiers on 2026-10-24
PYPI_LICENSE_CLASSIFIERS = {
    "License :: CC0 1.0 Universal (CC0 1.0) Public Domain Dedication",
    "License :: OSI Approved :: Apache Software License",
    "License :: OSI Approved :: BSD License",
    "License :: OSI Approved :: Boost Software License 1.0 (BSL-1.0)",
    "License :: OSI Approved :: Eclipse Public License 2.0 (EPL-2.0)",
    "License :: OSI Approved :: GNU Affero General Public License v3",
    "License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)",
    "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
    "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
    "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
    "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
    "License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)",
    "License :: OSI Approved :: ISC License (ISCL)",
    "License :: OSI Approved :: MIT License",
    "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)",
    "License :: OSI Approved :: The Unlicense (Unlicense)",
    "License :: OSI Approved :: Zero-Clause BSD (0BSD)",
}


def _min_matrix_python(workflow: Path) -> str:
    versions = re.findall(r"'(3\.\d+)'", re.search(r"python-version:\s*\[([^\]]*)\]", workflow.read_text()).group(1))
    return min(versions, key=lambda v: tuple(int(p) for p in v.split(".")))


# --- the floors the badges and prerequisites state come from the layer files ---

def test_pypi_floor_is_the_pyprojects_requires_python():
    text = (LAYERS / "python/pypi/pyproject.toml").read_text(encoding="utf-8")
    assert f'requires-python = ">={readme_blocks.floors("python/pypi")["python"]}"' in text


def test_setuppy_floor_is_setup_pys_python_requires():
    text = (LAYERS / "python/setuppy/setup.py").read_text(encoding="utf-8")
    assert f'python_requires=">={readme_blocks.floors("python/setuppy")["python"]}"' in text


def test_script_and_plugin_floors_are_their_ci_matrices_oldest_python():
    for preset in ("python/script", "python/claude-plugin"):
        ci = LAYERS / preset / ".github/workflows/ci-python.yml"
        assert _min_matrix_python(ci) == readme_blocks.floors(preset)["python"], preset


def test_node_floor_is_package_json_engines():
    engines = json.loads((LAYERS / "js-ts/node/package.json").read_text(encoding="utf-8"))["engines"]["node"]
    for preset in ("js-ts/node-package", "js-ts/script", "js-ts/claude-plugin"):
        assert engines == ">=" + readme_blocks.floors(preset)["node"], preset


# --- the licence: SPDX ids and PyPI classifiers ---

def test_spdx_ids_come_from_the_catalogue():
    assert licenses.spdx("gpl-3.0") == "GPL-3.0"
    assert licenses.spdx("MIT") == "MIT"
    assert licenses.spdx("gpl-3.0-or-later") == "GPL-3.0-or-later"
    assert licenses.spdx("all-rights-reserved").startswith("LicenseRef")
    assert licenses.spdx("no-such-licence") is None


def test_every_classifier_is_one_pypi_accepts():
    for lid, classifier in licenses.CLASSIFIERS.items():
        assert classifier in PYPI_LICENSE_CLASSIFIERS, f"{lid}: {classifier!r} is not a PyPI classifier"
        assert lid in licenses.known(), f"{lid} is not a catalogue id"


# --- the README and CONTRIBUTING sections ---

def test_pypi_sections_install_from_pypi_and_from_the_owners_repository():
    s = readme_blocks.sections("python/pypi", "python", "my-tool", "someorg", True)
    assert "pip install my-tool" in s["install_section"]
    assert "https://github.com/someorg/my-tool.git" in s["install_section"]
    assert "my-tool --help" in s["usage_section"] and "python -m my_tool --version" in s["usage_section"]
    assert "install-hooks.sh" in s["setup_block"]
    assert "pytest" in s["test_block"]
    assert "Python 3.10+" in s["prerequisites"]


def test_a_project_without_a_preset_gets_no_install_or_usage_heading():
    s = readme_blocks.sections(None, "generic", "thing", "me", False)
    assert s["install_section"] == "" and s["usage_section"] == ""
    assert "install-hooks.sh" not in s["setup_block"]
    assert "https://github.com/me/thing.git" in s["setup_block"]


def test_cmake_sections_build_and_run_ctest():
    s = readme_blocks.sections("c-cpp/cmake-app", "c-cpp", "app", "me", False)
    assert "cmake --build build" in s["setup_block"] and "ctest" in s["test_block"]


def test_plugin_sections_install_through_the_marketplace():
    s = readme_blocks.sections("js-ts/claude-plugin", "js-ts", "plug", "me", False)
    assert "/plugin marketplace add me/plug" in s["install_section"]
    assert "/plugin install plug@plug" in s["install_section"]


# --- the layer tokens ---

def test_tokens_carry_the_owner_the_licence_and_the_keywords():
    ctx = token_context({"project_name": "p", "github_org": "someorg", "github_user": "me",
                         "license_expression": "MIT",
                         "license_classifier": "License :: OSI Approved :: MIT License",
                         "topics": ["cli", "demo"]})
    assert ctx["RK_ORG"] == "someorg"
    assert ctx["RK_LICENSE"] == "MIT"
    assert ctx["RK_LICENSE_CLASSIFIER"] == '"License :: OSI Approved :: MIT License",'
    assert ctx["RK_KEYWORDS"] == '"cli", "demo"'


def test_no_topics_and_no_classifier_leave_valid_empty_values():
    ctx = token_context({"project_name": "p"})
    assert ctx["RK_KEYWORDS"] == "" and ctx["RK_LICENSE_CLASSIFIER"] == ""
    assert ctx["RK_LICENSE"] == "UNLICENSED"


# --- the labels the project's own files name ---

def test_referenced_labels_reads_the_issue_templates_and_dependabot(tmp_path):
    gh = tmp_path / ".github"
    (gh / "ISSUE_TEMPLATE").mkdir(parents=True)
    (gh / "ISSUE_TEMPLATE" / "bug-report.md").write_text("---\nname: Bug\nlabels: bug\n---\n", encoding="utf-8")
    (gh / "ISSUE_TEMPLATE" / "feature-request.md").write_text("---\nlabels: enhancement\n---\n", encoding="utf-8")
    (gh / "dependabot.yml").write_text(
        'version: 2\nupdates:\n  - package-ecosystem: "pip"\n    labels:\n      - "pip"\n      - "dependencies"\n'
        '  - package-ecosystem: "github-actions"\n    labels:\n      - "github-actions"\n      - "dependencies"\n',
        encoding="utf-8")
    assert referenced_labels(str(tmp_path)) == ["bug", "enhancement", "pip", "dependencies", "github-actions"]


def test_labels_creates_the_referenced_ones_the_repository_lacks():
    calls = []

    def run(cmd):
        calls.append(cmd)
        if cmd[1:3] == ["label", "list"]:
            return 0, json.dumps([{"name": "pinned"}, {"name": "bug"}])
        return 0, ""

    report = GhSetup(["gh"], "me/p", run).labels(["bug", "enhancement", "pinned", "custom"])
    made = [c[3] for c in calls if c[1:3] == ["label", "create"]]
    assert "bug" not in made and "pinned" not in made
    assert {"enhancement", "custom", "evergreen"} <= set(made)
    enh = next(c for c in calls if c[1:4] == ["label", "create", "enhancement"])
    assert enh[enh.index("--color") + 1] == "a2eeef"
    assert report[0].startswith("labels: created")
