"""
Branch strategies: one definition, the strategy's private branch wins unless
--private-branch is given, and the main-only strategy.

Design: the revival plan, steps 6-8 (project-private notes,
2026-10-07__02-09-36__claude-plan__repokit-revival-phases-0-1.md).
"""

import os
import shutil
import subprocess
import tempfile
import types
import unittest
from unittest import mock

from repokit import defaults
from repokit.cli import args_to_config, parse_arguments
from repokit.config import ConfigManager
from repokit.remote_integration import RemoteIntegration

from .test_utils import RepoKitTestCase


def git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )


def parse(*argv):
    with mock.patch("sys.argv", ["repokit", *argv]):
        return parse_arguments()


class NeutralCwd(unittest.TestCase):
    """ConfigManager reads ./.repokit.json as a project override, and this
    repository has its own; run from an empty folder so defaults are tested."""

    def setUp(self):
        self._cwd = os.getcwd()
        self._tmp = tempfile.mkdtemp(prefix="repokit-cfg-")
        os.chdir(self._tmp)

    def tearDown(self):
        os.chdir(self._cwd)
        shutil.rmtree(self._tmp, ignore_errors=True)


def resolved_config(cli_config):
    manager = ConfigManager()
    manager.set_cli_config(cli_config)
    return manager.get_config()


class TestOneSourceOfStrategies(NeutralCwd):

    def test_config_defaults_come_from_the_table(self):
        self.assertEqual(ConfigManager().config["branch_strategies"], defaults.BRANCH_STRATEGIES)

    def test_cli_accepts_every_strategy_in_the_table(self):
        for name in defaults.BRANCH_STRATEGIES:
            self.assertEqual(parse("create", "demo", "--branch-strategy", name).branch_strategy, name)

    def test_cli_rejects_a_strategy_not_in_the_table(self):
        with self.assertRaises(SystemExit), mock.patch("sys.stderr"):
            parse("create", "demo", "--branch-strategy", "no-such-strategy")

    def test_main_only_is_listed_first(self):
        self.assertEqual(next(iter(defaults.BRANCH_STRATEGIES)), "main-only")

    def test_analyzer_lists_derive_from_the_table(self):
        self.assertEqual(
            set(defaults.DEFAULT_BRANCH_STRATEGIES["standard"]),
            {"private", "main", "dev", "staging", "test", "live"},
        )
        self.assertEqual(defaults.DEFAULT_BRANCH_STRATEGIES["main-only"], ["main"])
        self.assertEqual(defaults.DEFAULT_BRANCH_STRATEGIES["minimal"], ["private", "main"])

    def test_push_branches(self):
        self.assertEqual(defaults.strategy_push_branches("standard"),
                         ["main", "dev", "staging", "test", "live"])
        self.assertEqual(defaults.strategy_push_branches("gitflow"), ["main", "develop"])
        self.assertEqual(defaults.strategy_push_branches("main-only"), ["main"])
        self.assertEqual(defaults.strategy_push_branches("no-such-strategy"), [])


class TestPrivateBranchPrecedence(NeutralCwd):

    def parse(self, *argv):
        return args_to_config(parse("create", "demo", *argv))

    def test_cli_does_not_send_a_private_branch_unless_given(self):
        self.assertNotIn("private_branch", self.parse("--branch-strategy", "minimal"))

    def test_strategy_private_branch_wins_by_default(self):
        strategies = dict(defaults.BRANCH_STRATEGIES)
        strategies["custom"] = {"branches": ["main"], "worktrees": [], "private_branch": "scratch"}
        with mock.patch.dict(defaults.BRANCH_STRATEGIES, strategies):
            config = resolved_config({"branch_strategy": "custom"})
        self.assertEqual(config["private_branch"], "scratch")

    def test_main_only_has_no_private_branch(self):
        config = resolved_config(self.parse("--branch-strategy", "main-only"))
        self.assertIsNone(config["private_branch"])

    def test_explicit_flag_still_wins(self):
        config = resolved_config(self.parse("--branch-strategy", "standard", "--private-branch", "mine"))
        self.assertEqual(config["private_branch"], "mine")


class TestPublishExcludes(unittest.TestCase):
    """What publish pushes. Repository creation and the push are stubbed, so
    these tests cannot reach GitHub whatever the code under test does."""

    def pushed(self, strategy, private_branch):
        repo_manager = types.SimpleNamespace(
            project_name="demo",
            config={"branch_strategy": strategy, "private_branch": private_branch},
        )
        remote = RemoteIntegration(repo_manager)
        calls = []
        with mock.patch.object(remote, "create_github_repository", return_value=(True, "https://example.invalid/demo.git")), \
             mock.patch.object(remote, "create_gitlab_repository", side_effect=AssertionError("network")), \
             mock.patch.object(remote, "add_remote", return_value=True), \
             mock.patch.object(remote, "push_allowed_branches",
                               side_effect=lambda allowed, exclude, name: calls.append((allowed, exclude)) or (allowed, [])):
            self.assertTrue(remote.setup_remote_repository(service="github"))
        return calls[0]

    def test_legacy_excludes_the_private_branch(self):
        allowed, exclude = self.pushed("standard", "private")
        self.assertEqual(allowed, ["main", "dev", "staging", "test", "live"])
        self.assertEqual(exclude, ["private"])

    def test_a_private_branch_that_is_also_public_is_still_pushed(self):
        # e.g. `--branch-strategy minimal --private-branch main`
        allowed, exclude = self.pushed("minimal", "main")
        self.assertEqual(allowed, ["main"])
        self.assertNotIn("main", exclude)

    def test_main_only_pushes_main_and_excludes_nothing(self):
        allowed, exclude = self.pushed("main-only", None)
        self.assertEqual(allowed, ["main"])
        self.assertEqual(exclude, [])


class TestCreateWithStrategies(RepoKitTestCase):

    def test_minimal_still_makes_main_and_a_private_branch(self):
        # What minimal has always produced (see defaults.BRANCH_STRATEGIES).
        self.assert_repokit_success(["create", "demo", "--branch-strategy", "minimal", "--no-push"])
        branches = git(os.path.join(self.test_dir, "demo", "local"), "branch", "--format=%(refname:short)").stdout.split()
        self.assertEqual(sorted(branches), ["main", "private"])

    def test_a_custom_private_branch_is_private_to_the_guard(self):
        # --private-branch scratch: the generated pre-commit hook must treat
        # 'scratch' as private, or create's own commits on it are refused.
        self.assert_repokit_success([
            "create", "named", "--branch-strategy", "simple",
            "--private-branch", "scratch", "--ai", "claude", "--no-push",
        ])
        local = os.path.join(self.test_dir, "named", "local")
        self.assertEqual(git(local, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip(), "scratch")
        self.assertIn("CLAUDE.md", git(local, "ls-files").stdout.split())

    def test_main_only_makes_one_branch_in_a_flat_layout(self):
        self.assert_repokit_success(["create", "demo", "--branch-strategy", "main-only", "--no-push"])
        repo = os.path.join(self.test_dir, "demo")

        self.assertTrue(os.path.isdir(os.path.join(repo, ".git")))
        self.assertFalse(os.path.exists(os.path.join(repo, "local")))
        self.assertFalse(os.path.exists(os.path.join(repo, "github")))

        branches = git(repo, "branch", "--format=%(refname:short)").stdout.split()
        self.assertEqual(branches, ["main"])
        self.assertEqual(git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip(), "main")

    def test_main_only_commits_nothing_private(self):
        self.assert_repokit_success(["create", "demo", "--branch-strategy", "main-only", "--ai", "claude", "--no-push"])
        repo = os.path.join(self.test_dir, "demo")

        tracked = git(repo, "ls-files").stdout.split()
        self.assertTrue(tracked, "nothing was committed")
        self.assertFalse([f for f in tracked if f.startswith("private/")], tracked)
        self.assertNotIn("CLAUDE.md", tracked)
        # the AI files were still written for local use
        self.assertTrue(os.path.exists(os.path.join(repo, "CLAUDE.md")))


if __name__ == "__main__":
    unittest.main()
