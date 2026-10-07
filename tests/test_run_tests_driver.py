"""
tests/run_tests.py: choosing which tests run, with the suite's isolation kept.

djdarcy wanted the runner's --unit / --integration / --github choices back
after it stopped working (project-private note
2026-10-07__13-52-08__both_bring-back-test-categories.md).
"""

import datetime
import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from . import run_tests
from .conftest import LIVE_ENV

RUNNER = str(Path(run_tests.__file__))


class TestPlanRun(unittest.TestCase):

    def plan(self, *argv):
        return run_tests.plan_run(list(argv), now=datetime.datetime(2026, 10, 7, 14, 0, 0))

    def test_no_category_runs_everything_without_live(self):
        _, pytest_args, env, run_dir = self.plan()
        self.assertNotIn("-m", pytest_args)
        self.assertNotIn(LIVE_ENV, env)
        self.assertIsNone(run_dir)

    def test_each_category_selects_its_marker(self):
        for flag, marker in (("--unit", "unit"), ("--integration", "integration"),
                             ("--github", "live"), ("--deployment", "deployment")):
            _, pytest_args, _, _ = self.plan(flag)
            self.assertEqual(pytest_args[pytest_args.index("-m") + 1], marker, flag)

    def test_only_github_and_deployment_turn_on_live_tests(self):
        for flag in ("--unit", "--integration"):
            self.assertNotIn(LIVE_ENV, self.plan(flag)[2], flag)
        for flag in ("--github", "--deployment"):
            self.assertEqual(self.plan(flag)[2][LIVE_ENV], "1", flag)

    def test_categories_are_exclusive(self):
        with self.assertRaises(SystemExit), mock.patch("sys.stderr"):
            self.plan("--unit", "--github")

    def test_keep_run_uses_a_dated_directory_under_test_runs(self):
        _, _, env, run_dir = self.plan("--keep-run")
        self.assertEqual(run_dir, run_tests.TEST_RUNS / "test_run_2026_10_07__14_00_00")
        self.assertEqual(env["REPOKIT_TEST_RUN_DIR"], str(run_dir))

    def test_no_cleanup_and_passthrough(self):
        _, pytest_args, env, _ = self.plan("--no-cleanup", "--", "-k", "config")
        self.assertEqual(env["REPOKIT_TEST_CLEANUP"], "false")
        self.assertEqual(pytest_args[-2:], ["-k", "config"])


class TestCheck(unittest.TestCase):

    def test_check_reports_the_token_without_printing_it(self):
        with tempfile.TemporaryDirectory() as fake_root:
            Path(fake_root, ".env.test").write_text(
                "REPOKIT_TEST_GITHUB_TOKEN=ghp_not_a_real_token_1234567890\n", encoding="utf-8")
            out = io.StringIO()
            with mock.patch.object(run_tests, "REPO_ROOT", Path(fake_root)), redirect_stdout(out):
                self.assertEqual(run_tests.main(["--check"]), 0)
        self.assertIn("REPOKIT_TEST_GITHUB_TOKEN is set", out.getvalue())
        self.assertNotIn("ghp_not_a_real_token", out.getvalue())


class TestRunnerEndToEnd(unittest.TestCase):
    """Run the real script. It starts a second pytest, so keep the selection tiny."""

    def run_runner(self, *argv):
        return subprocess.run(
            [sys.executable, RUNNER, *argv], capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )

    def test_script_runs_from_its_documented_path(self):
        # It used to fail before running anything: ImportError on the test modules.
        result = self.run_runner("--unit", "--", "--collect-only")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("-m unit", result.stdout)
        self.assertIn("test_core_functionality.py", result.stdout)
        # integration-only files are not selected
        self.assertNotIn("test_legacy_smoke.py", result.stdout)

    def test_isolation_holds_under_the_runner(self):
        result = self.run_runner("--unit", "--", "-k", "TestSuiteIsolation")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
