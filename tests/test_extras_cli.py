"""`repokit create --extras` (0.9.0, U3): the structure's optional files are
off by default, on by name or `all`, taken from the global config and
overridden by --no-extras, recorded in .repokit.json, and an unknown name is
refused. FUNDING.yml renders the GitHub user from the config.

Design: 2026-10-22__22-06-57__dev-workflow-process__0-9-x-parity-with-the-old-route.md.
"""
import json
import os
from pathlib import Path
from unittest import mock

from repokit.repo_manager import RepoManager
from .test_utils import RepoKitTestCase

ALL_FILES = [".github/FUNDING.yml", ".github/dependabot.yml", ".github/stale.yml",
             ".github/pull_request_template.md", ".github/release-template.md", "ROADMAP.md",
             "docs/platform-support.md", ".vscode/settings.json", "docs/.gitkeep",
             "tests/one-offs/README.md", "tests/output/.gitkeep"]


class TestExtrasFlag(RepoKitTestCase):

    def _meta(self, name):
        return json.loads((Path(self.test_dir, name) / ".repokit.json").read_text(encoding="utf-8"))

    def test_off_by_default(self):
        self.assert_repokit_success(["create", "demo", "--language", "generic", "--no-push"])
        repo = Path(self.test_dir, "demo")
        for rel in ALL_FILES:
            if rel.endswith(".gitkeep") and (repo / rel).parent.name in ("docs",):
                continue   # docs/ is a structure directory; its gitkeep comes from the directory walk
            self.assertFalse((repo / rel).exists(), rel)
        self.assertEqual(self._meta("demo")["extras"], [])

    def test_all_writes_every_extra_and_records_them(self):
        self.assert_repokit_success(["create", "demo", "--language", "generic", "--extras", "all", "--no-push"])
        repo = Path(self.test_dir, "demo")
        for rel in ALL_FILES:
            self.assertTrue((repo / rel).exists(), rel)
        self.assertEqual(self._meta("demo")["extras"], list(RepoManager.EXTRAS))
        release = (repo / ".github/release-template.md").read_text(encoding="utf-8")
        self.assertIn("pip install demo", release)
        self.assertIn("$NEXT_VERSION", release)        # left for the release-notes writer, on purpose
        self.assertIn("/issues/1", (repo / "ROADMAP.md").read_text(encoding="utf-8"))

    def test_named_extras_only_in_the_tables_order(self):
        self.assert_repokit_success(["create", "demo", "--language", "generic", "--extras", "stale,funding", "--no-push"])
        repo = Path(self.test_dir, "demo")
        self.assertTrue((repo / ".github/stale.yml").exists())
        self.assertTrue((repo / ".github/FUNDING.yml").exists())
        self.assertFalse((repo / ".github/dependabot.yml").exists())
        self.assertEqual(self._meta("demo")["extras"], ["funding", "stale"])

    def test_the_global_config_turns_them_on_and_no_extras_turns_them_off(self):
        home = Path(self.test_dir, "home")
        (home / ".repokit").mkdir(parents=True)
        (home / ".repokit" / "config.json").write_text(json.dumps(
            {"license": "mit", "extras": ["funding", "dependabot"], "github": {"username": "ada-example"}}), encoding="utf-8")
        with mock.patch.dict(os.environ, {"HOME": str(home), "USERPROFILE": str(home)}):
            self.assert_repokit_success(["create", "on", "--language", "generic", "--no-push"])
            self.assert_repokit_success(["create", "off", "--language", "generic", "--no-extras", "--no-push"])
        funding = (Path(self.test_dir, "on") / ".github/FUNDING.yml").read_text(encoding="utf-8")
        self.assertIn("github: ada-example", funding)
        self.assertTrue((Path(self.test_dir, "on") / ".github/dependabot.yml").exists())
        self.assertFalse((Path(self.test_dir, "off") / ".github/FUNDING.yml").exists())
        self.assertEqual(self._meta("off")["extras"], [])

    def test_an_unknown_extra_is_refused(self):
        code, out, err = self.run_repokit(["create", "demo", "--language", "generic", "--extras", "sponsors", "--no-push"])
        self.assertNotEqual(code, 0)
        self.assertIn("unknown extras sponsors", out + err)
