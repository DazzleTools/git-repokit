"""
S4: `repokit create --github` through gh, and the REST-path fixes.

Safety: no test here can reach GitHub. gh is replaced by a stub script
(REPOKIT_GH) whose `repo create` adds a local bare repository as the remote,
so the push is real but local; the REST tests patch requests.post/patch.
"""

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from repokit.github_create import branches_to_push

from .test_utils import RepoKitTestCase

STUB = textwrap.dedent('''
    import json, os, subprocess, sys
    args = sys.argv[1:]
    with open(os.environ["GH_STUB_LOG"], "a", encoding="utf-8") as f:
        f.write(json.dumps(args) + "\\n")
    if args[:2] == ["auth", "status"]:
        sys.exit(0)
    if args[:2] == ["api", "user"]:
        print("stub-user")
        sys.exit(0)
    if args[:2] == ["repo", "create"]:
        name = args[2].split("/")[-1]
        bare = os.path.join(os.environ["GH_STUB_REMOTES"], name + ".git")
        subprocess.run(["git", "init", "-q", "--bare", bare], check=True)
        source = args[args.index("--source") + 1]
        subprocess.run(["git", "-C", source, "remote", "add", "origin", bare], check=True)
        sys.exit(0)
    sys.exit(3)
''')


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


class GhStubCase(RepoKitTestCase):

    def setUp(self):
        super().setUp()
        self.stub_dir = Path(self.test_dir, "_gh")
        (self.stub_dir / "remotes").mkdir(parents=True)
        self.stub = self.stub_dir / "gh_stub.py"
        self.stub.write_text(STUB, encoding="utf-8")
        self.log = self.stub_dir / "log.jsonl"
        self.env = mock.patch.dict(os.environ, {
            "REPOKIT_GH": str(self.stub),
            "GH_STUB_LOG": str(self.log),
            "GH_STUB_REMOTES": str(self.stub_dir / "remotes"),
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        super().tearDown()

    def calls(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def remote_branches(self, name):
        bare = self.stub_dir / "remotes" / f"{name}.git"
        return sorted(git(str(bare), "for-each-ref", "--format=%(refname:short)", "refs/heads").stdout.split())

    def create_call(self):
        return next(c for c in self.calls() if c[:2] == ["repo", "create"])


class TestCreateGithub(GhStubCase):

    def test_main_only_is_created_private_and_main_is_pushed(self):
        self.assert_repokit_success(["create", "demo", "--github", "--no-common"])
        call = self.create_call()
        self.assertEqual(call[2], "stub-user/demo")
        self.assertIn("--private", call)
        self.assertEqual(self.remote_branches("demo"), ["main"])

    def test_public_and_organization(self):
        self.assert_repokit_success(["create", "demo", "--github", "--public", "--org", "someorg", "--no-common"])
        call = self.create_call()
        self.assertEqual(call[2], "someorg/demo")
        self.assertIn("--public", call)
        # 0.9.3: the login is read even with --org, for the account check; the
        # repository is still created under the organisation, never the login
        self.assertIn(["api", "user", "-q", ".login"], self.calls())

    def test_private_branch_model_never_pushes_the_private_branch(self):
        self.assert_repokit_success(["create", "demo", "--branch-strategy", "simple", "--github"])
        self.assertEqual(self.remote_branches("demo"), ["dev", "main"])

    def test_no_push_creates_nothing(self):
        self.assert_repokit_success(["create", "demo", "--github", "--no-push", "--no-common"])
        self.assertEqual(self.calls(), [])

    def test_missing_gh_fails_clearly_and_keeps_the_local_repository(self):
        os.environ["REPOKIT_GH"] = str(self.stub_dir / "no-such-gh.exe")
        code, out, err = self.run_repokit(["create", "demo", "--github", "--no-common"])
        self.assertNotEqual(code, 0)
        self.assertIn("GitHub:", err)
        self.assertTrue(Path(self.test_dir, "demo", ".git").is_dir())


class TestBranchesToPush(unittest.TestCase):

    def test_only_existing_public_branches(self):
        self.assertEqual(branches_to_push({"branch_strategy": "standard"}, "private",
                                          ["main", "dev", "private"]), ["main", "dev"])
        self.assertEqual(branches_to_push({"branch_strategy": "main-only"}, None, ["main"]), ["main"])


class TestRestPathFixes(unittest.TestCase):

    def test_default_branch_is_set_on_the_real_owner(self):
        from repokit.remote_integration import RemoteIntegration
        import types

        repo_manager = types.SimpleNamespace(project_name="demo", config={})
        created = mock.Mock(status_code=201)
        created.json.return_value = {"html_url": "https://github.com/someone/demo",
                                     "owner": {"login": "someone"}}
        created.raise_for_status.return_value = None
        with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "dummy"}), \
             mock.patch("repokit.remote_integration.requests.post", return_value=created), \
             mock.patch("repokit.remote_integration.requests.patch",
                        return_value=mock.Mock(status_code=200)) as patch:
            ok, url = RemoteIntegration(repo_manager).create_github_repository("demo", "", True, None, None)
        self.assertTrue(ok, url)
        self.assertEqual(patch.call_args[0][0], "https://api.github.com/repos/someone/demo")

    def test_create_passes_token_to_the_publish_step(self):
        from repokit import cli
        seen = {}

        def fake_setup(self_, **kwargs):
            seen["token"] = os.environ.get("GITHUB_TOKEN")
            return True

        with tempfile.TemporaryDirectory() as d, \
             mock.patch.dict(os.environ, {"GITHUB_TOKEN": ""}), \
             mock.patch("sys.argv", ["repokit", "create", "demo", "--publish-to", "github",
                                     "--token", "tok-123", "--no-common"]), \
             mock.patch("repokit.cli.RepoManager.setup_repository", return_value=True), \
             mock.patch("repokit.remote_integration.RemoteIntegration.setup_remote_repository", fake_setup):
            cwd = os.getcwd()
            os.chdir(d)
            try:
                self.assertEqual(cli.main(), 0)
            finally:
                os.chdir(cwd)
        self.assertEqual(seen["token"], "tok-123")


if __name__ == "__main__":
    unittest.main()
