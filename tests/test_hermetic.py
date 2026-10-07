"""
The suite's own isolation (tests/conftest.py) holds.

If any of these fail, other tests may be signing commits with the
developer's key, writing to the real home directory, or talking to GitHub.
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from .conftest import LIVE_ENV, live_github_enabled


class TestSuiteIsolation(unittest.TestCase):

    def test_home_is_a_temporary_directory(self):
        home = Path.home()
        self.assertIn("repokit-test-home-", home.name)
        self.assertEqual(Path(os.path.expanduser("~")), home)

    def test_credentials_path_is_under_the_temporary_home(self):
        from repokit.auth_integration import AuthenticationHandler

        handler = AuthenticationHandler()
        self.assertIn("repokit-test-home-", str(handler.default_creds_path))

    def test_git_does_not_sign_in_a_test_made_repo(self):
        with tempfile.TemporaryDirectory() as repo:
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            for key in ("commit.gpgsign", "tag.gpgsign"):
                value = subprocess.run(
                    ["git", "config", key], cwd=repo,
                    capture_output=True, text=True,
                ).stdout.strip()
                self.assertEqual(value, "false", key)

    def test_github_tokens_are_blank_unless_live_tests_were_asked_for(self):
        if live_github_enabled():
            self.skipTest(f"{LIVE_ENV}=1: live GitHub tests requested")
        for name in ("REPOKIT_TEST_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
            self.assertEqual(os.environ.get(name), "", name)

    def test_repokit_runs_from_an_unrelated_directory(self):
        with tempfile.TemporaryDirectory() as elsewhere:
            result = subprocess.run(
                [sys.executable, "-m", "repokit", "--version"],
                cwd=elsewhere, capture_output=True, text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
