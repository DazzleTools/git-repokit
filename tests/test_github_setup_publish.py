"""The GitHub setup beyond `create --github`: the token route
(`--publish-to github` on create, adopt and publish) runs the named steps in
the window between the repository's creation and its first push; `publish` on
a project already on GitHub takes the update path (nothing created, the push
and the setup still run); the #1/#2 check counts pull requests; a conflict
asks a person at a terminal (continue, skip, abort) and skips otherwise.

Safety: no test here reaches GitHub. gh is a fake (unit) or a stub script
(REPOKIT_GH, CLI); the CLI test's origin has a github.com fetch URL but a
local bare repository as its push URL, so even a broken guard cannot push to
the network.
Design: 2026-11-17__19-19-12__dev-workflow-process__github-setup-beyond-create.md
(and its 19:45 addendum: no new verb, conflicts ask).
"""
import json
import os
import subprocess
from pathlib import Path
from unittest import mock

import pytest

from repokit import github_setup
from repokit.github_create import github_repo_of, publish_hooks
from repokit.github_setup import GhSetup, SetupAborted
from .test_github_setup import FakeGh, STUB
from .test_utils import RepoKitTestCase


class FakeGhWithPulls(FakeGh):
    def __init__(self, pulls=(), **kw):
        super().__init__(**kw)
        self.pulls = [dict(p) for p in pulls]

    def __call__(self, cmd):
        if cmd[1:3] == ["pr", "list"]:
            self.calls.append(cmd[1:])
            return 0, json.dumps(self.pulls)
        return super().__call__(cmd)


def _setup(fake, ask=None):
    return GhSetup(["gh"], "o/r", fake, ask=ask)


# --- the #1/#2 check sees pull requests -----------------------------------------

def test_a_pull_request_at_1_stops_the_issues_by_default():
    fake = FakeGhWithPulls(pulls=[{"number": 1, "title": "Bump actions/checkout"}])
    report = _setup(fake).issues("demo")
    assert "#1 is already pull request 'Bump actions/checkout'" in report[0]
    assert report[0].endswith("not created")
    assert all(c[:2] != ["issue", "create"] for c in fake.calls)


def test_continue_at_the_conflict_takes_the_later_numbers():
    fake = FakeGhWithPulls(pulls=[{"number": 1, "title": "Bump x"}])
    asked = []
    report = _setup(fake, ask=lambda m: asked.append(m) or "continue").issues("demo")
    assert len(asked) == 1 and "would not be #1 and #2" in asked[0]
    assert [c[c.index("--title") + 1] for c in fake.calls if c[:2] == ["issue", "create"]] == \
        ["Roadmap", "Quick Notes -- Bugs, Features, Ideas"]
    assert report[-1].startswith("issues: #")


def test_abort_at_the_conflict_stops_the_rest():
    fake = FakeGhWithPulls(pulls=[{"number": 1, "title": "Bump x"}])
    with pytest.raises(SetupAborted):
        _setup(fake, ask=lambda m: "abort").issues("demo")
    assert all(c[:2] != ["issue", "create"] for c in fake.calls)


def test_continue_creates_only_the_missing_one():
    fake = FakeGhWithPulls(issues=[{"number": 1, "title": "Roadmap"}], pulls=[{"number": 2, "title": "Bump x"}])
    _setup(fake, ask=lambda m: "continue").issues("demo")
    titles = [c[c.index("--title") + 1] for c in fake.calls if c[:2] == ["issue", "create"]]
    assert titles == ["Quick Notes -- Bugs, Features, Ideas"]


def test_roadmap_at_1_alone_gets_quick_notes_at_2_without_a_question():
    fake = FakeGhWithPulls(issues=[{"number": 1, "title": "Roadmap"}])
    report = _setup(fake, ask=lambda m: pytest.fail("asked although #2 is free")).issues("demo")
    assert report == ["issues: #2 Quick Notes -- Bugs, Features, Ideas"]


def test_roadmap_elsewhere_is_named_in_the_conflict():
    fake = FakeGhWithPulls(issues=[{"number": 3, "title": "Roadmap"}])
    report = _setup(fake).issues("demo")
    assert "Roadmap would be #3" in report[0] and report[0].endswith("not created")


def test_pull_requests_unreadable_creates_nothing():
    class Broken(FakeGhWithPulls):
        def __call__(self, cmd):
            return (1, "HTTP 502") if cmd[1:3] == ["pr", "list"] else super().__call__(cmd)
    fake = Broken()
    assert _setup(fake).issues("demo") == [
        "issues: could not list the pull requests, so #1 and #2 cannot be checked; not created"]
    assert all(c[:2] != ["issue", "create"] for c in fake.calls)


def test_an_empty_repository_gets_1_and_2_without_a_question():
    fake = FakeGhWithPulls()
    report = _setup(fake, ask=lambda m: pytest.fail("asked on an empty repository")).issues("demo")
    assert report == ["issues: #1 Roadmap", "issues: #2 Quick Notes -- Bugs, Features, Ideas"]


# --- asking only a person ------------------------------------------------------------

@pytest.mark.parametrize("env", [{"CLAUDECODE": "1"}, {"CI": "true"}, {"REPOKIT_INTERACTIVE": "0"}])
def test_no_question_under_an_agent_ci_or_the_switch(env):
    # Only the one variable: the suite's conftest sets REPOKIT_INTERACTIVE=0 for every test
    clean = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CI", "REPOKIT_INTERACTIVE")}
    with mock.patch.dict(os.environ, {**clean, **env}, clear=True), mock.patch("sys.stdin") as stdin, \
            mock.patch("builtins.input", side_effect=AssertionError("asked")):
        stdin.isatty.return_value = True
        assert github_setup.interactive() is False
        assert github_setup.ask_conflict("x") == "skip"


def test_a_person_at_a_terminal_is_asked():
    clean = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CI", "REPOKIT_INTERACTIVE")}
    with mock.patch.dict(os.environ, clean, clear=True), mock.patch("sys.stdin") as stdin:
        stdin.isatty.return_value = True
        for typed, choice in (("c", "continue"), ("A", "abort"), ("", "skip"), ("x", "skip")):
            with mock.patch("builtins.input", return_value=typed):
                assert github_setup.ask_conflict("x") == choice


# --- the repository a URL names --------------------------------------------------------

@pytest.mark.parametrize("url,repo", [
    ("https://github.com/djdarcy/shotgun-marriage.git", "djdarcy/shotgun-marriage"),
    ("https://github.com/djdarcy/shotgun-marriage", "djdarcy/shotgun-marriage"),
    ("git@github.com:DazzleTools/git-repokit.git", "DazzleTools/git-repokit"),
    ("https://gitlab.com/a/b.git", None),
    ("", None),
    (None, None),
])
def test_github_repo_of(url, repo):
    assert github_repo_of(url) == repo


# --- the hooks for the token route ----------------------------------------------------

def test_gh_not_ready_skips_the_setup_and_the_publish_goes_on(tmp_path):
    report = []
    with mock.patch("repokit.github_create.gh_ready", return_value=(None, None, "gh is not installed")):
        before, after = publish_hooks(str(tmp_path), {}, ["labels", "issues"], report)
        assert before("https://github.com/o/r.git") is True
        after("https://github.com/o/r.git")
    assert len(report) == 1 and report[0].startswith("setup not run: gh is not installed")


def test_the_hooks_run_before_and_after_the_push_and_an_abort_stops_it(tmp_path):
    fake = FakeGhWithPulls(pulls=[{"number": 1, "title": "Bump x"}])
    with mock.patch("repokit.github_create.gh_ready", return_value=(["gh"], "o", None)), \
            mock.patch("repokit.github_create._run", side_effect=lambda cmd, cwd: fake(cmd)):
        report = []
        before, after = publish_hooks(str(tmp_path), {}, ["labels", "issues", "discussions"], report,
                                      ask=lambda m: "abort")
        assert before("https://github.com/o/r.git") is False
        assert "stopped before the push" in report[-1]

        report = []
        before, after = publish_hooks(str(tmp_path), {}, ["labels", "discussions"], report)
        assert before("https://github.com/o/r.git") is True
        assert any(l.startswith("labels:") for l in report)
        assert not any(l.startswith("discussions:") for l in report)
        after("https://github.com/o/r.git")
        assert any(l.startswith("discussions:") for l in report)


def test_no_steps_no_gh_call(tmp_path):
    with mock.patch("repokit.github_create.gh_ready", side_effect=AssertionError("gh consulted")):
        before, after = publish_hooks(str(tmp_path), {}, [], [])
        assert before("https://github.com/o/r.git") is True


# --- the token route's window and the update path ----------------------------------------

class _Mgr:
    project_name = "demo"
    config = {"branch_strategy": "main-only"}

    def __init__(self, origin=""):
        self.origin = origin

    def run_git(self, args, *a, **k):
        return self.origin if args[:2] == ["remote", "get-url"] else ""


def _integration(origin=""):
    from repokit.remote_integration import RemoteIntegration
    ri = RemoteIntegration.__new__(RemoteIntegration)
    ri.repo_manager = _Mgr(origin)
    import logging
    ri.logger = logging.getLogger("test")
    return ri


def test_an_abort_in_the_window_pushes_nothing():
    ri = _integration()
    with mock.patch.object(ri, "create_github_repository", return_value=(True, "https://github.com/o/demo.git")), \
            mock.patch.object(ri, "add_remote", return_value=True), \
            mock.patch.object(ri, "push_allowed_branches", side_effect=AssertionError("pushed")):
        assert ri.setup_remote_repository(after_create=lambda url: False) is False


def test_the_window_comes_before_the_push_and_after_push_after_it():
    ri, order = _integration(), []
    with mock.patch.object(ri, "create_github_repository", return_value=(True, "https://github.com/o/demo.git")), \
            mock.patch.object(ri, "add_remote", return_value=True), \
            mock.patch.object(ri, "push_allowed_branches", side_effect=lambda *a: order.append("push") or (["main"], [])):
        assert ri.setup_remote_repository(after_create=lambda url: order.append("window") or True,
                                          after_push=lambda url: order.append("after")) is True
    assert order == ["window", "push", "after"]


def test_the_update_path_creates_nothing_and_keeps_the_remote():
    ri = _integration(origin="https://github.com/o/demo.git")
    with mock.patch.object(ri, "create_github_repository", side_effect=AssertionError("created")), \
            mock.patch.object(ri, "add_remote", side_effect=AssertionError("remote rewritten")), \
            mock.patch.object(ri, "push_allowed_branches", return_value=(["main"], [])):
        assert ri.setup_remote_repository(update_existing=True) is True


def test_without_update_existing_an_origin_on_github_still_creates():
    """adopt and create pass no update_existing: they keep creating."""
    ri = _integration(origin="https://github.com/o/demo.git")
    with mock.patch.object(ri, "create_github_repository", return_value=(False, "stop here")) as create:
        assert ri.setup_remote_repository() is False
    create.assert_called_once()


def test_update_existing_with_a_non_github_origin_creates():
    ri = _integration(origin="https://gitlab.com/o/demo.git")
    with mock.patch.object(ri, "create_github_repository", return_value=(False, "stop here")) as create:
        assert ri.setup_remote_repository(update_existing=True) is False
    create.assert_called_once()


# --- the command line ------------------------------------------------------------------------

def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false",
                    *args], cwd=cwd, check=True, capture_output=True)


@pytest.mark.integration
class TestPublishUpdatePath(RepoKitTestCase):
    """`repokit publish` on a project already on GitHub, gh answered by a stub."""

    def setUp(self):
        super().setUp()
        d = Path(self.test_dir, "_gh")
        (d / "remotes").mkdir(parents=True)
        (d / "gh_stub.py").write_text(STUB, encoding="utf-8")
        self.log = d / "log.jsonl"
        bare = d / "remotes" / "demo.git"
        subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
        (d / "state.json").write_text(json.dumps({"labels": [], "issues": [], "remote": str(bare)}), encoding="utf-8")
        home = Path(self.test_dir, "home")
        (home / ".repokit").mkdir(parents=True)
        # A default in the config, so --no-github-setup has something to switch off
        (home / ".repokit" / "config.json").write_text(json.dumps({"github": {"username": "stub-user"},
                                                                   "github_setup": ["labels"]}),
                                                       encoding="utf-8")
        self.repo = Path(self.test_dir, "demo")
        self.repo.mkdir()
        (self.repo / ".repokit.json").write_text(json.dumps({"project_name": "demo", "branch_strategy": "main-only",
                                                             "extras": ["funding"]}), encoding="utf-8")
        _git(self.repo, "init", "-q", "-b", "main")
        _git(self.repo, "add", ".repokit.json")
        _git(self.repo, "commit", "-q", "-m", "init")
        _git(self.repo, "remote", "add", "origin", "https://github.com/stub-user/demo.git")
        _git(self.repo, "remote", "set-url", "--push", "origin", str(bare))   # never the network
        self.env = mock.patch.dict(os.environ, {
            "REPOKIT_GH": str(d / "gh_stub.py"), "GH_STUB_LOG": str(self.log),
            "GH_STUB_REMOTES": str(d / "remotes"), "GH_STUB_STATE": str(d / "state.json"),
            "HOME": str(home), "USERPROFILE": str(home), "GIT_CEILING_DIRECTORIES": self.test_dir,
            "REPOKIT_INTERACTIVE": "0"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        super().tearDown()

    def _calls(self):
        return [json.loads(l) for l in self.log.read_text(encoding="utf-8").splitlines()] if self.log.exists() else []

    def test_publish_on_an_existing_repository_pushes_and_sets_up_in_order(self):
        code, out, err = self.run_repokit(["publish", str(self.repo), "--publish-to", "github",
                                           "--github-setup", "labels,issues,pin,discussions"])
        self.assertEqual(code, 0, out[-2000:] + err[-2000:])
        self.assertIn("GitHub: issues: #1 Roadmap", out)
        self.assertIn("GitHub: discussions: on", out)
        self.assertIn("Sponsorships", out)          # the project's own extras reached the reminders
        calls = self._calls()
        creates = [c for c in calls if c["args"][:2] == ["issue", "create"]]
        self.assertEqual(len(creates), 2)
        self.assertTrue(all(not c["pushed"] for c in creates), "an issue was created after the push")
        self.assertTrue(all(c["pushed"] for c in calls if c["args"][:2] == ["repo", "edit"]))
        self.assertFalse(any(c["args"][:2] == ["repo", "create"] for c in calls))

    def test_a_second_publish_creates_nothing_new(self):
        args = ["publish", str(self.repo), "--publish-to", "github", "--github-setup", "labels,issues"]
        self.assertEqual(self.run_repokit(args)[0], 0)
        code, out, err = self.run_repokit(args)
        self.assertEqual(code, 0, out[-2000:] + err[-2000:])
        self.assertIn("GitHub: labels: all already there", out)
        self.assertIn("GitHub: issues: Roadmap and Quick Notes already there", out)

    def test_no_github_setup_runs_nothing(self):
        code, out, err = self.run_repokit(["publish", str(self.repo), "--publish-to", "github", "--no-github-setup"])
        self.assertEqual(code, 0, out[-2000:] + err[-2000:])
        self.assertNotIn("GitHub:", out)
        self.assertEqual(self._calls(), [])

    def test_gitlab_with_github_setup_is_refused_before_anything(self):
        code, out, err = self.run_repokit(["publish", str(self.repo), "--publish-to", "gitlab",
                                           "--github-setup", "labels"])
        self.assertNotEqual(code, 0)
        self.assertIn("--github-setup works with --publish-to github only", out + err)
        self.assertEqual(self._calls(), [])


@pytest.mark.integration
class TestCreateRecordsAndRefuses(RepoKitTestCase):

    def test_unknown_step_refused_before_anything_is_written(self):
        code, out, err = self.run_repokit(["create", "demo", "--language", "generic", "--license", "mit",
                                           "--github-setup", "labels,bogus"])
        self.assertNotEqual(code, 0)
        self.assertIn("unknown github-setup steps bogus", out + err)
        self.assertFalse(os.path.exists(os.path.join(self.test_dir, "demo")))

    def test_topics_are_recorded_for_a_later_publish(self):
        code, out, err = self.run_repokit(["create", "demo", "--language", "generic", "--license", "mit",
                                           "--topics", "cli, git,cli"])
        self.assertEqual(code, 0, out[-2000:] + err[-2000:])
        record = json.loads(Path(self.test_dir, "demo", ".repokit.json").read_text(encoding="utf-8"))
        self.assertEqual(record.get("topics"), ["cli", "git"])
