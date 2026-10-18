"""
The private-content patterns in git-repokit's own pre-commit hook.

That hook is the guard when git-repokit-common is not vendored (--no-common,
or vendoring failed). Its glob-to-regex step did not escape `.`, so `*.log`
became `^.*.log` and refused any path with "log" after another character:
catalog.py, src/logger.py, repokit-common's own search_sesslog.py. Found by
the v0.7.0 smoke test on 2026-10-17, when a failed `git subtree add` left
repokit-common staged for the first commit and the hook refused it.
"""

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import pytest

from repokit import common_kit
from repokit.utils import glob_to_ere

from .test_utils import RepoKitTestCase, force_rmtree


class TestGlobToEre(unittest.TestCase):

    def matches(self, pattern, path):
        return re.search(glob_to_ere(pattern), path) is not None

    def test_a_dot_is_a_dot(self):
        self.assertTrue(self.matches("*.log", "debug.log"))
        self.assertTrue(self.matches("*.log", "logs/debug.log"))
        self.assertFalse(self.matches("*.log", "catalog.py"))
        self.assertFalse(self.matches("*.log", "src/logger.py"))
        self.assertFalse(self.matches("*.log", "scripts/repokit-common/search_sesslog.py"))

    def test_exact_names_match_whole_paths_only(self):
        self.assertEqual(glob_to_ere(".repokit.json"), r"^\.repokit\.json$")
        self.assertTrue(self.matches(".env.local", ".env.local"))
        self.assertFalse(self.matches(".env.local", "xenvylocal"))
        self.assertFalse(self.matches(".env.local", "docs/.env.local"))

    def test_directories_match_their_contents(self):
        self.assertEqual(glob_to_ere("private/"), "^private/")
        self.assertTrue(self.matches("private/", "private/notes.md"))
        self.assertFalse(self.matches("private/", "privateer.py"))
        self.assertFalse(self.matches("private/", "src/private/x"))

    def test_double_star_means_any_depth_including_the_root(self):
        self.assertEqual(glob_to_ere("**/__private__*"), r"^(.*/)?__private__.*")
        self.assertTrue(self.matches("**/__private__*", "__private__notes.md"))
        self.assertTrue(self.matches("**/__private__*", "a/b/__private__notes.md"))
        self.assertFalse(self.matches("**/private_*", "src/not_private_x"))
        self.assertTrue(self.matches("**/private_*", "src/private_x"))

    def test_leading_dot_patterns_do_not_swallow_other_names(self):
        self.assertTrue(self.matches(".env*", ".env.test"))
        self.assertFalse(self.matches(".env*", "venv/bin/python"))

    @unittest.skipUnless(common_kit.find_sh(), "no POSIX sh to run the hook's own test")
    def test_the_regex_is_what_grep_e_reads(self):
        # The regex goes into a script, as the hook carries it. Passed as an
        # argument from Python on Windows, the MSYS runtime strips the
        # backslashes (`^.*\.log` arrives as `^.*.log`) and the test would
        # see the bug it is checking for.
        regex = "|".join(glob_to_ere(p) for p in ["*.log", "*.tmp", ".repokit.json", "**/__private__*"])
        script = Path(tempfile.mkdtemp(prefix="repokit-ere-")) / "check.sh"
        script.write_text(f'#!/bin/sh\nread -r path\necho "$path" | grep -q -E "{regex}"\n', encoding="utf-8")
        self.addCleanup(force_rmtree, str(script.parent))
        def grep(path):
            return subprocess.run([common_kit.find_sh(), str(script)], input=path + "\n",
                                  text=True).returncode == 0
        self.assertTrue(grep("debug.log"))
        self.assertTrue(grep("a/__private__x"))
        self.assertTrue(grep(".repokit.json"))
        self.assertFalse(grep("catalog.py"))
        self.assertFalse(grep("scripts/repokit-common/search_sesslog.py"))
        self.assertFalse(grep("x.repokit.json"))


class TestVendorFailureLeavesNothingBehind(unittest.TestCase):
    """A `git subtree add` that dies midway must not leave half of repokit-common staged."""

    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="repokit-vendor-")
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=self.repo, check=True)
        Path(self.repo, "README.md").write_text("# t\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=self.repo, check=True)
        self.real_git = common_kit._git

    def tearDown(self):
        common_kit._git = self.real_git
        force_rmtree(self.repo)

    def test_a_failed_subtree_add_is_undone(self):
        prefix = Path(self.repo, common_kit.PREFIX)

        def failing_git(args, cwd):
            if args[:2] == ["subtree", "add"]:
                # what a midway failure leaves: files in the index and on disk
                prefix.mkdir(parents=True)
                (prefix / "search_sesslog.py").write_text("x\n", encoding="utf-8")
                subprocess.run(["git", "add", common_kit.PREFIX], cwd=cwd, check=True)
                return 128, "fatal: cannot create directory at '...': Filename too long"
            return self.real_git(args, cwd)

        common_kit._git = failing_git
        problem = common_kit.vendor(self.repo, "C:/nowhere/git-repokit-common", "main")

        self.assertIn("Filename too long", problem)
        self.assertFalse(prefix.exists())
        staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=self.repo,
                                capture_output=True, text=True).stdout
        self.assertEqual(staged.strip(), "")


@pytest.mark.integration
class TestOwnHookOnARealProject(RepoKitTestCase):
    """--no-common: git-repokit's own hook guards main, and lets catalog.py through."""

    def setUp(self):
        super().setUp()
        self.assert_repokit_success(["create", "demo", "--no-common", "--no-push"])
        self.repo = os.path.join(self.test_dir, "demo")

    def commit(self, name, content="x\n"):
        full = Path(self.repo) / name
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", "-f", name], cwd=self.repo, check=True, capture_output=True)
        return subprocess.run(["git", "commit", "-m", f"add {name}"], cwd=self.repo,
                              capture_output=True, text=True, encoding="utf-8", errors="replace")

    def test_the_hook_is_git_repokits_own_with_escaped_patterns(self):
        hook = Path(self.repo, ".git", "hooks", "pre-commit").read_text(encoding="utf-8", errors="replace")
        self.assertIn("Generated by RepoKit", hook)
        self.assertIn(r"\.log", hook)
        self.assertNotIn("^.*.log", hook)

    def test_a_name_containing_log_is_not_private(self):
        result = self.commit("src/catalog.py", "print('ok')\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_log_file_still_is(self):
        result = self.commit("debug.log")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("debug.log", result.stdout + result.stderr)

    @unittest.skipUnless(os.name == "nt", "Git for Windows' MAX_PATH limit")
    def test_a_windows_repository_allows_long_paths(self):
        # repokit-common's deepest vendored path is 133 characters; without this
        # a project ~130 characters deep failed to vendor it (Filename too long).
        value = subprocess.run(["git", "config", "core.longpaths"], cwd=self.repo,
                               capture_output=True, text=True).stdout.strip()
        self.assertEqual(value, "true")


if __name__ == "__main__":
    unittest.main()
