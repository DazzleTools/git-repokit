"""`repokit create` with the code-type layers: --language as a list, --archetype,
failure before anything is created, and the wiring with the structure
(the vault's ignore lines survive the layers' appends).

Design: the Phase 2 v2 analysis of 2026-10-09 (units U2.4, U2.5) in the
project's private notes. Each test runs the real CLI into the test's temp
directory; git-repokit-common is vendored from a local checkout or switched
off by tests/conftest.py, never from the network.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from .test_utils import RepoKitTestCase

REPO = Path(__file__).resolve().parents[1]
LAYERS = REPO / "repokit" / "templates" / "layers"
TOKEN = re.compile(rb"__RK_[A-Z_]+?__")

REQUIREMENTS = (
    "# Project dependencies\n# Add your dependencies here\n\n# Development dependencies\n"
    "pytest>=7.0.0\nblack>=23.0.0\nflake8>=6.0.0\nmypy>=1.0.0\n"
)


def _tokens_left(root):
    hits = []
    for p in Path(root).rglob("*"):
        if ".git" in p.parts or "repokit-common" in p.parts or not p.is_file():
            continue
        if TOKEN.search(p.name.encode()) or TOKEN.search(p.read_bytes()):
            hits.append(p.relative_to(root).as_posix())
    return hits


class TestLanguageLayers(RepoKitTestCase):

    def test_setuppy_keeps_todays_output_and_the_vaults_ignore_lines(self):
        """U3.2's pin at the CLI: --archetype python/setuppy still produces setup.py
        and requirements.txt with the project's names (the output a bare --language
        python gave before 0.7.0); the Python ignore lines are appended and the
        vault's lines, written after the layers, are still there."""
        self.assert_repokit_success(["create", "demo", "--archetype", "python/setuppy", "--no-push"])
        repo = Path(self.test_dir, "demo")
        setup = (repo / "setup.py").read_text(encoding="utf-8")
        self.assertIn('name="demo"', setup)
        self.assertIn("author=", setup)
        self.assertEqual((repo / "requirements.txt").read_text(encoding="utf-8"), REQUIREMENTS)
        ignore = (repo / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn(".ruff_cache/", ignore)      # the python layer's append
        self.assertIn("/private/", ignore)         # the vault's line, re-applied after the layers
        self.assertIn("CLAUDE.local.md", ignore)
        self.assertEqual(_tokens_left(repo), [])
        meta = json.loads((repo / ".repokit.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["languages"], ["python"])
        self.assertEqual(meta["archetype"], "python/setuppy")
        self.assertEqual(meta["language"], "python")

    def test_languages_stack_in_the_order_given(self):
        """--language c-cpp,python: both language layers land, the first language's
        default archetype (cmake-app) applies and the second's does not, the C
        header's path token is resolved, the layer's .repokit-common.toml names it
        with the archetype's extra target appended, and the workflow file is
        byte-identical to its source. Reversed, python is primary: setuppy's
        setup.py, no CMake."""
        self.assert_repokit_success(["create", "demo", "--language", "c-cpp,python", "--no-push"])
        repo = Path(self.test_dir, "demo")
        for rel in ("CMakeLists.txt", "include/demo/version.h", "src/app.rc", "vcpkg.json"):
            self.assertTrue((repo / rel).is_file(), rel)
        self.assertFalse((repo / "pyproject.toml").exists())          # python's archetype does not apply
        settings = (repo / ".repokit-common.toml").read_text(encoding="utf-8")
        self.assertIn('version-source = "include/demo/version.h"', settings)
        self.assertIn('languages = ["c-cpp"]', settings)
        self.assertIn("extra-targets", settings)          # the archetype's .rkappend onto the language's file
        ignore = (repo / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("cmake-build-*/", ignore)
        self.assertIn(".ruff_cache/", ignore)             # python's language layer still contributes
        src = LAYERS / "archetypes/c-cpp/cmake-app/.github/workflows/ci.yml"
        self.assertEqual((repo / ".github/workflows/ci.yml").read_bytes(), src.read_bytes())
        self.assertEqual(_tokens_left(repo), [])
        meta = json.loads((repo / ".repokit.json").read_text(encoding="utf-8"))
        self.assertEqual((meta["languages"], meta["archetype"]), (["c-cpp", "python"], "c-cpp/cmake-app"))

        rc, out, err = self.run_repokit(["create", "demo2", "--language", "python,c-cpp", "--no-push"])
        self.assertEqual(rc, 0, out + err)
        repo2 = Path(self.test_dir, "demo2")
        self.assertTrue((repo2 / "setup.py").is_file() and (repo2 / "include/demo2/version.h").is_file())
        self.assertFalse((repo2 / "CMakeLists.txt").exists())
        meta2 = json.loads((repo2 / ".repokit.json").read_text(encoding="utf-8"))
        self.assertEqual((meta2["languages"], meta2["archetype"]), (["python", "c-cpp"], "python/setuppy"))

    def test_an_archetype_implies_its_language_and_shares_the_guids(self):
        self.assert_repokit_success(["create", "demo", "--archetype", "c-cpp/msbuild", "--no-push"])
        repo = Path(self.test_dir, "demo")
        sln = (repo / "demo.sln").read_text(encoding="utf-8", errors="replace")
        vcx = (repo / "demo.vcxproj").read_text(encoding="utf-8", errors="replace")
        guids = set(re.findall(r"[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}", sln))
        self.assertTrue(guids and guids & set(re.findall(r"[0-9A-F]{8}-(?:[0-9A-F]{4}-){3}[0-9A-F]{12}", vcx)))
        self.assertEqual(_tokens_left(repo), [])
        meta = json.loads((repo / ".repokit.json").read_text(encoding="utf-8"))
        self.assertEqual((meta["languages"], meta["archetype"]), (["c-cpp"], "c-cpp/msbuild"))

    def test_unknown_names_and_stubs_fail_before_anything_is_created(self):
        """U2.4: the failure names what is known and leaves no folder behind."""
        cases = [
            (["--language", "cobol"], "unknown language 'cobol'; known: generic, c-cpp, javascript, python"),
            (["--language", "javascript"], "language javascript is not built yet"),
            (["--archetype", "python/django"], "archetype python/django is not built yet"),
            (["--archetype", "python/nope"], "unknown archetype 'python/nope'; known:"),
        ]
        for extra, message in cases:
            rc, out, err = self.run_repokit(["create", "demo", *extra, "--no-push"])
            self.assertNotEqual(rc, 0, extra)
            self.assertIn(message, out + err, extra)
            self.assertFalse(os.path.exists(os.path.join(self.test_dir, "demo")), extra)

    def test_generic_lays_down_no_code_type_files(self):
        self.assert_repokit_success(["create", "demo", "--no-push"])
        repo = Path(self.test_dir, "demo")
        for rel in ("setup.py", "requirements.txt", "CMakeLists.txt", ".github/workflows"):
            self.assertFalse((repo / rel).exists(), rel)
        self.assertNotIn("workflows/", (repo / "README.md").read_text(encoding="utf-8"))
        self.assertTrue((repo / ".gitattributes").is_file() and (repo / "CHANGELOG.md").is_file())
        meta = json.loads((repo / ".repokit.json").read_text(encoding="utf-8"))
        self.assertEqual((meta["languages"], meta["archetype"]), (["generic"], None))
