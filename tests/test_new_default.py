"""
S3: the new default (main-only + nested private repository + git-repokit-common),
the private-branch model with git-repokit-common's hooks, worktree links, and
setup-guardrails installing git-repokit-common's hooks.

Design: plan addendum 2026-10-08 17:40 and the hook inventory (design addendum
2026-10-08 15:04) in the project's private notes. git-repokit-common is
vendored from a local checkout (tests/conftest.py); without one these tests skip.
"""

import os
import subprocess
import sys
import unittest
from pathlib import Path

from .conftest import repokit_common_available
from .test_utils import RepoKitTestCase

STUB_MARKER = "repokit-common hook stub"
needs_common = unittest.skipUnless(repokit_common_available(),
                                   "no local git-repokit-common checkout to vendor from")


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def hook_text(repo):
    path = Path(git(repo, "rev-parse", "--git-path", "hooks").stdout.strip())
    if not path.is_absolute():
        path = Path(repo) / path
    pre_commit = path / "pre-commit"
    return pre_commit.read_text(encoding="utf-8", errors="replace") if pre_commit.exists() else ""


def commit_file(repo, name, content="x\n"):
    full = Path(repo) / name
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    git(repo, "add", "-f", name)
    return git(repo, "commit", "-m", f"add {name}")


@needs_common
class TestBareCreate(RepoKitTestCase):
    """R3: a bare `repokit create demo`."""

    def setUp(self):
        super().setUp()
        self.assert_repokit_success(["create", "demo", "--no-push"])
        self.repo = os.path.join(self.test_dir, "demo")

    def test_one_branch_main(self):
        self.assertEqual(git(self.repo, "branch", "--format=%(refname:short)").stdout.split(), ["main"])

    def test_private_is_its_own_repository_with_a_first_commit(self):
        vault = os.path.join(self.repo, "private")
        self.assertTrue(os.path.isdir(os.path.join(vault, ".git")))
        self.assertEqual(len(git(vault, "log", "--oneline").stdout.splitlines()), 1)
        self.assertEqual(git(vault, "config", "commit.gpgsign").stdout.strip(), "false")

    def test_parent_ignores_the_vault_and_local_claude_file(self):
        lines = Path(self.repo, ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("/private/", lines)
        self.assertIn("CLAUDE.local.md", lines)
        self.assertFalse([f for f in git(self.repo, "ls-files").stdout.split() if f.startswith("private/")])

    def test_repokit_common_is_vendored_and_its_hooks_installed(self):
        self.assertTrue(Path(self.repo, "scripts", "repokit-common", "install-hooks.sh").is_file())
        self.assertIn(STUB_MARKER, hook_text(self.repo))

    def test_tree_is_clean(self):
        status = git(self.repo, "status", "--porcelain").stdout.split("\n")
        self.assertEqual([s for s in status if s and ".repokit.json" not in s], [])


@needs_common
class TestPrivateBranchModelWithCommon(RepoKitTestCase):
    """The private-branch model guarded by git-repokit-common's pre-commit."""

    def test_claude_md_refused_on_main_allowed_on_private(self):
        self.assert_repokit_success(["create", "demo", "--branch-strategy", "simple", "--with-common", "--no-push"])
        local = os.path.join(self.test_dir, "demo", "local")
        github = os.path.join(self.test_dir, "demo", "github")
        self.assertIn(STUB_MARKER, hook_text(local))

        refused = commit_file(github, "CLAUDE.md")
        self.assertNotEqual(refused.returncode, 0, refused.stdout + refused.stderr)

        allowed = commit_file(local, "CLAUDE.md")
        self.assertEqual(allowed.returncode, 0, allowed.stdout + allowed.stderr)

    def test_a_custom_private_branch_is_written_to_the_settings(self):
        self.assert_repokit_success(["create", "demo", "--branch-strategy", "simple",
                                     "--private-branch", "scratch", "--with-common", "--no-push"])
        local = os.path.join(self.test_dir, "demo", "local")
        settings = Path(local, ".repokit-common.toml").read_text(encoding="utf-8")
        self.assertIn("private-branches", settings)
        self.assertIn('"scratch"', settings)
        allowed = commit_file(local, "private/notes.md")
        self.assertEqual(allowed.returncode, 0, allowed.stdout + allowed.stderr)


class TestDefaultsAndFallback(RepoKitTestCase):

    def test_standard_alone_still_makes_no_vault_and_no_subtree(self):
        self.assert_repokit_success(["create", "demo", "--branch-strategy", "standard", "--no-push"])
        local = os.path.join(self.test_dir, "demo", "local")
        self.assertFalse(os.path.exists(os.path.join(local, "private", ".git")))
        self.assertFalse(os.path.exists(os.path.join(local, "scripts", "repokit-common")))

    def test_no_common_keeps_git_repokits_own_guard(self):
        self.assert_repokit_success(["create", "demo", "--no-common", "--no-push"])
        repo = os.path.join(self.test_dir, "demo")
        self.assertFalse(os.path.exists(os.path.join(repo, "scripts", "repokit-common")))
        text = hook_text(repo)
        self.assertTrue(text, "no pre-commit hook at all")
        self.assertNotIn(STUB_MARKER, text)


class TestWorktreeLinks(RepoKitTestCase):

    def test_every_worktree_reaches_the_real_vault(self):
        self.assert_repokit_success(["create", "demo", "--branch-strategy", "simple",
                                     "--private-mode", "nested", "--no-common", "--no-push"])
        vault = os.path.join(self.test_dir, "demo", "local", "private")
        link = os.path.join(self.test_dir, "demo", "github", "private")
        self.assertTrue(os.path.isdir(os.path.join(vault, ".git")))
        self.assertTrue(os.path.exists(link), "no private/ link in the github worktree")
        self.assertTrue(os.path.samefile(vault, link))
        # the link is not something the worktree would commit
        self.assertNotIn("private", git(os.path.dirname(link), "status", "--porcelain").stdout)


@needs_common
class TestSetupGuardrails(RepoKitTestCase):

    def setUp(self):
        super().setUp()
        self.repo = os.path.join(self.test_dir, "proj")
        os.makedirs(self.repo)
        git(self.repo, "init", "-q")
        Path(self.repo, "README.md").write_text("# proj\n", encoding="utf-8")
        git(self.repo, "add", "README.md")
        git(self.repo, "commit", "-q", "-m", "init")

    def test_without_a_copy_it_explains_and_changes_nothing(self):
        code, out, err = self.run_repokit(["setup-guardrails"], cwd=self.repo)
        self.assertNotEqual(code, 0)
        self.assertIn("git subtree add", out)
        self.assertEqual(len(git(self.repo, "log", "--oneline").stdout.splitlines()), 1)

    def test_output_on_a_non_utf8_console_does_not_crash(self):
        # The status lines print emoji; with output piped and no UTF-8
        # override (the suite sets one), the command used to crash after
        # installing everything.
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
        result = subprocess.run(
            [sys.executable, "-m", "repokit", "setup-guardrails", "--vendor"],
            cwd=self.repo, capture_output=True, env=env,
        )
        out = (result.stdout + result.stderr).decode("utf-8", errors="replace")
        self.assertNotIn("UnicodeEncodeError", out)
        self.assertEqual(result.returncode, 0, out)

    def test_previous_hooks_are_moved_aside_not_lost(self):
        hooks = Path(self.repo, ".git", "hooks")
        hooks.mkdir(exist_ok=True)
        (hooks / "pre-commit").write_text("#!/bin/sh\n# an older guard\nexit 0\n", encoding="utf-8")
        (hooks / "post-checkout").write_text("#!/bin/sh\n# RepoKit post-checkout hook\nexit 0\n", encoding="utf-8")
        self.assert_repokit_success(["setup-guardrails", "--vendor"], cwd=self.repo)
        self.assertIn(STUB_MARKER, hook_text(self.repo))
        self.assertIn("an older guard", (hooks / "pre-commit.before-repokit-common").read_text(encoding="utf-8"))
        self.assertTrue((hooks / "post-checkout.disabled").is_file())
        self.assertFalse((hooks / "post-checkout").exists())

    def test_vendor_installs_repokit_common_hooks(self):
        self.assert_repokit_success(["setup-guardrails", "--vendor"], cwd=self.repo)
        self.assertTrue(Path(self.repo, "scripts", "repokit-common", "install-hooks.sh").is_file())
        self.assertIn(STUB_MARKER, hook_text(self.repo))
        self.assertFalse(Path(self.repo, ".git", "hooks", "post-checkout").exists())


class TestExcludesKeepUserLines(unittest.TestCase):

    def test_branch_excludes_keep_lines_that_are_not_repokits(self):
        import tempfile
        from repokit.branch_utils import _write_excludes
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "exclude")
            Path(path).write_text("# mine\nCLAUDE.local.md\n", encoding="utf-8")
            _write_excludes(path, ["# RepoKit: block", "CLAUDE.md"])
            _write_excludes(path, ["# RepoKit: block", "CLAUDE.md"])  # twice: no duplicates
            lines = Path(path).read_text(encoding="utf-8").splitlines()
        self.assertIn("CLAUDE.local.md", lines)
        self.assertEqual(lines.count("CLAUDE.md"), 1)
        self.assertEqual(lines.count("# RepoKit: block"), 1)


if __name__ == "__main__":
    unittest.main()
