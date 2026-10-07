"""
The legacy branch model still works when asked for (R2).

`repokit create --branch-strategy standard` is no longer how new projects are
made, but projects built that way still exist and some people will still ask
for it. This checks behaviour, not bytes: the branches, the layout, and the
pre-commit guard that keeps private files off public branches. Cosmetic
changes to the generated output are allowed; losing any of this is not.

Design: 2026-10-07__01-56-44__dev-workflow-process__repokit-revival.md (R2 and
its 02:12 addendum) in the project's private notes.
"""

import json
import os
import subprocess

from .test_utils import RepoKitTestCase

STANDARD_BRANCHES = {"main", "dev", "staging", "test", "live", "private"}


def git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )


class TestLegacyBranchModel(RepoKitTestCase):

    def setUp(self):
        super().setUp()
        self.assert_repokit_success([
            "create", "demo",
            "--branch-strategy", "standard",
            "--no-push",
        ])
        self.project = os.path.join(self.test_dir, "demo")
        self.local = os.path.join(self.project, "local")
        self.github = os.path.join(self.project, "github")

    def test_standard_strategy_creates_its_branches_and_the_private_branch(self):
        branches = set(git(self.local, "branch", "--format=%(refname:short)").stdout.split())
        self.assertTrue(STANDARD_BRANCHES <= branches, branches)

    def test_local_is_on_private_and_github_worktree_is_on_main(self):
        self.assertEqual(git(self.local, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip(), "private")
        self.assertEqual(git(self.github, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip(), "main")

    def test_repokit_json_records_the_legacy_choice(self):
        with open(os.path.join(self.local, ".repokit.json"), encoding="utf-8") as f:
            config = json.load(f)
        self.assertEqual(config["branch_strategy"], "standard")
        self.assertEqual(config["private_branch"], "private")

    def test_pre_commit_guard_refuses_private_files_on_main(self):
        before = git(self.github, "rev-parse", "HEAD").stdout.strip()

        for private_path in ("CLAUDE.md", os.path.join("private", "notes.md")):
            full = os.path.join(self.github, private_path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write("private\n")
            git(self.github, "add", "-f", private_path)
            result = git(self.github, "commit", "-m", f"leak {private_path}")
            self.assertNotEqual(result.returncode, 0, f"{private_path} was committed on main")
            git(self.github, "reset", "-q", "HEAD", "--", private_path)

        self.assertEqual(git(self.github, "rev-parse", "HEAD").stdout.strip(), before)

    def test_pre_commit_guard_allows_ordinary_files_on_main(self):
        # Control for the test above: the guard refuses private files, not everything.
        with open(os.path.join(self.github, "app.py"), "w", encoding="utf-8") as f:
            f.write("print('hello')\n")
        git(self.github, "add", "app.py")
        result = git(self.github, "commit", "-m", "add app")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
