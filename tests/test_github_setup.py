"""v0.9.3, the GitHub half: labels, the two evergreen issues as #1 and #2
before the first push, pinning by title, discussions, topics, the pypi
environment, idempotent; refused on another gh account.

Safety: no test here reaches GitHub. The unit tests answer for gh with a
fake that keeps state; the CLI test uses a stub script (REPOKIT_GH) whose
`repo create` makes a local bare remote, as tests/test_github_create.py does.
Design: 2026-10-22__22-06-57__dev-workflow-process__0-9-x-parity-with-the-old-route.md (row 0.9.3).
"""
import json
import os
import textwrap
from pathlib import Path
from unittest import mock

import pytest

from repokit import github_setup
from repokit.github_setup import GhSetup, LABELS, ISSUES
from .test_utils import RepoKitTestCase


class FakeGh:
    """Enough of gh for the setup steps, with state, recording every call."""

    def __init__(self, labels=(), issues=()):
        self.labels = set(labels)
        self.issues = [dict(i) for i in issues]
        self.pinned = set()
        self.calls = []

    def __call__(self, cmd):
        args = cmd[1:]
        self.calls.append(args)
        if args[:2] == ["label", "list"]:
            return 0, json.dumps([{"name": n} for n in sorted(self.labels)])
        if args[:2] == ["label", "create"]:
            self.labels.add(args[2])
            return 0, ""
        if args[:2] == ["issue", "list"]:
            return 0, json.dumps([{"number": i["number"], "title": i["title"]} for i in self.issues])
        if args[:2] == ["issue", "create"]:
            n = len(self.issues) + 1
            self.issues.append({"number": n, "title": args[args.index("--title") + 1]})
            return 0, f"https://github.com/o/r/issues/{n}"
        if args[:2] == ["issue", "view"]:
            return 0, f"NODE{args[2]}"
        if args[:2] == ["api", "graphql"]:
            q = args[3]
            if q.startswith("query=mutation"):
                self.pinned.add(int(q.split('"NODE')[1].split('"')[0]))
                return 0, "{}"
            nodes = [{"issue": {"number": n}} for n in sorted(self.pinned)]
            return 0, json.dumps({"data": {"repository": {"pinnedIssues": {"nodes": nodes}}}})
        return 0, ""


def _setup(fake):
    return GhSetup(["gh"], "o/r", fake)


def test_labels_creates_the_missing_ones_and_a_second_run_nothing():
    fake = FakeGh(labels={"pinned", "bug"})
    assert _setup(fake).labels()[0].startswith("labels: created evergreen")
    assert fake.labels >= {n for n, _, _ in LABELS}
    before = len(fake.calls)
    assert _setup(fake).labels() == ["labels: all nine already there"]
    assert all(c[:2] != ["label", "create"] for c in fake.calls[before:])


def test_the_two_issues_are_1_and_2_and_their_drafts_are_kept(tmp_path):
    fake = FakeGh()
    report = _setup(fake).issues("demo", str(tmp_path))
    assert report == ["issues: #1 Roadmap", "issues: #2 Quick Notes -- Bugs, Features, Ideas"]
    create = [c for c in fake.calls if c[:2] == ["issue", "create"]]
    assert create[0][create[0].index("--label") + 1] == "pinned,roadmap,evergreen"
    assert "demo" in (tmp_path / "issue_roadmap.md").read_text(encoding="utf-8")
    assert (tmp_path / "issue_notes.md").exists()
    assert _setup(fake).issues("demo") == ["issues: Roadmap and Quick Notes already there"]


def test_issues_are_refused_when_the_repository_already_has_one():
    fake = FakeGh(issues=[{"number": 1, "title": "Bump actions/checkout"}])
    report = _setup(fake).issues("demo")
    assert "would not be #1 and #2" in report[0]
    assert all(c[:2] != ["issue", "create"] for c in fake.calls)


def test_only_one_of_the_two_issues_present_is_not_both():
    """Mutation G2 (0.9.3) survived without this."""
    fake = FakeGh(issues=[{"number": 1, "title": "Roadmap"}])
    assert "would not be #1 and #2" in _setup(fake).issues("demo")[0]
    assert all(c[:2] != ["issue", "create"] for c in fake.calls)


def test_no_topics_named_edits_nothing():
    """Mutation G7 (0.9.3) survived without this."""
    fake = FakeGh()
    assert _setup(fake).topics([]) == ["topics: none named (--topics a,b)"]
    assert fake.calls == []


def test_pin_by_title_and_a_second_run_pins_nothing():
    fake = FakeGh(issues=[{"number": 1, "title": "Roadmap"}, {"number": 2, "title": ISSUES[1][0]}])
    assert _setup(fake).pin() == ["pin: #1 pinned", "pin: #2 pinned"]
    assert fake.pinned == {1, 2}
    assert _setup(fake).pin() == ["pin: #1 already pinned", "pin: #2 already pinned"]


def test_the_pypi_environment_only_for_the_pypi_preset():
    fake = FakeGh()
    assert _setup(fake).pypi_environment("python/script") == []
    assert _setup(fake).pypi_environment("python/pypi")[0].startswith("pypi-environment: created")
    assert ["api", "repos/o/r/environments/pypi", "-X", "PUT"] in fake.calls


def test_topics_and_discussions():
    fake = FakeGh()
    assert _setup(fake).topics(["cli", "git"]) == ["topics: cli, git"]
    assert ["repo", "edit", "o/r", "--add-topic", "cli", "--add-topic", "git"] in fake.calls
    assert _setup(fake).discussions() == ["discussions: on"]


def test_setup_names_all_and_unknown():
    assert github_setup.setup_names(["all"]) == list(github_setup.STEPS)
    assert github_setup.setup_names(["pin", "labels"]) == ["labels", "pin"]
    with pytest.raises(ValueError, match="unknown github-setup steps nope"):
        github_setup.setup_names(["nope"])


# --- live, against a throwaway that already exists (never creates one) ---------

@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("REPOKIT_LIVE_THROWAWAY"),
                    reason="set REPOKIT_LIVE_THROWAWAY=owner/name of a throwaway made by "
                           "`repokit create ... --github --github-setup all`")
def test_live_a_second_run_on_the_throwaway_creates_nothing():
    """The live check of 2026-10-24 ran this against djdarcy/repokit-throwaway-20261024-1."""
    from repokit.github_create import gh_command, _run
    repo = os.environ["REPOKIT_LIVE_THROWAWAY"]
    s = GhSetup(gh_command(), repo, lambda c: _run(c, "."))
    assert s.labels() == ["labels: all nine already there"]
    assert s.issues(repo.split("/")[1]) == ["issues: Roadmap and Quick Notes already there"]
    assert s.pin() == ["pin: #1 already pinned", "pin: #2 already pinned"]


# --- through the CLI, with a stub gh ------------------------------------------

STUB = textwrap.dedent('''
    import json, os, subprocess, sys
    args = sys.argv[1:]
    state_path = os.environ["GH_STUB_STATE"]
    state = json.load(open(state_path)) if os.path.exists(state_path) else {"labels": [], "issues": [], "remote": None}
    log = open(os.environ["GH_STUB_LOG"], "a", encoding="utf-8")
    def pushed():
        if not state["remote"]:
            return False
        r = subprocess.run(["git", "-C", state["remote"], "for-each-ref", "refs/heads"], capture_output=True, text=True)
        return bool(r.stdout.strip())
    log.write(json.dumps({"args": args, "pushed": pushed()}) + "\\n")
    out, rc = "", 0
    if args[:2] == ["auth", "status"]:
        pass
    elif args[:2] == ["api", "user"]:
        out = os.environ.get("GH_STUB_LOGIN", "stub-user")
    elif args[:2] == ["repo", "create"]:
        bare = os.path.join(os.environ["GH_STUB_REMOTES"], args[2].split("/")[-1] + ".git")
        subprocess.run(["git", "init", "-q", "--bare", bare], check=True)
        subprocess.run(["git", "-C", args[args.index("--source") + 1], "remote", "add", "origin", bare], check=True)
        state["remote"] = bare
    elif args[:2] == ["label", "list"]:
        out = json.dumps([{"name": n} for n in state["labels"]])
    elif args[:2] == ["label", "create"]:
        state["labels"].append(args[2])
    elif args[:2] == ["issue", "list"]:
        out = json.dumps(state["issues"])
    elif args[:2] == ["issue", "create"]:
        n = len(state["issues"]) + 1
        state["issues"].append({"number": n, "title": args[args.index("--title") + 1]})
        out = "https://github.com/stub-user/x/issues/%d" % n
    elif args[:2] == ["issue", "view"]:
        out = "NODE" + args[2]
    elif args[:2] == ["api", "graphql"]:
        out = json.dumps({"data": {"repository": {"pinnedIssues": {"nodes": []}}}})
    elif args[:2] in (["repo", "edit"],) or args[:1] == ["api"]:
        pass
    else:
        rc = 3
    json.dump(state, open(state_path, "w"))
    print(out)
    sys.exit(rc)
''')


@pytest.mark.integration
class TestGithubSetupThroughCreate(RepoKitTestCase):

    def setUp(self):
        super().setUp()
        d = Path(self.test_dir, "_gh")
        (d / "remotes").mkdir(parents=True)
        (d / "gh_stub.py").write_text(STUB, encoding="utf-8")
        self.log = d / "log.jsonl"
        self.env = mock.patch.dict(os.environ, {"REPOKIT_GH": str(d / "gh_stub.py"), "GH_STUB_LOG": str(self.log),
                                                "GH_STUB_REMOTES": str(d / "remotes"), "GH_STUB_STATE": str(d / "state.json")})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        super().tearDown()

    def _calls(self):
        return [json.loads(l) for l in self.log.read_text(encoding="utf-8").splitlines()]

    def test_labels_and_issues_land_before_the_first_push_and_the_rest_after(self):
        code, out, err = self.run_repokit(["create", "demo", "--language", "python", "--github",
                                           "--github-setup", "all", "--topics", "cli,git"])
        self.assertEqual(code, 0, out[-2000:] + err[-2000:])
        calls = self._calls()
        creates = [c for c in calls if c["args"][:2] == ["issue", "create"]]
        self.assertEqual(len(creates), 2)
        self.assertTrue(all(not c["pushed"] for c in creates), "an issue was created after the push")
        self.assertTrue(all(not c["pushed"] for c in calls if c["args"][:2] == ["label", "create"]))
        edits = [c for c in calls if c["args"][:2] == ["repo", "edit"]]
        self.assertTrue(edits and all(c["pushed"] for c in edits))
        self.assertIn("GitHub: issues: #1 Roadmap", out)
        self.assertIn("GitHub: pypi-environment: created", out)
        self.assertIn("GitHub: CI: watch the first run", out)

    def test_another_gh_account_is_refused_before_anything_is_created(self):
        home = Path(self.test_dir, "home")
        (home / ".repokit").mkdir(parents=True)
        (home / ".repokit" / "config.json").write_text(json.dumps({"license": "mit", "github": {"username": "someone-else"}}),
                                                       encoding="utf-8")
        with mock.patch.dict(os.environ, {"HOME": str(home), "USERPROFILE": str(home)}):
            code, out, err = self.run_repokit(["create", "demo", "--language", "generic", "--github", "--github-setup", "labels"])
        self.assertNotEqual(code, 0)
        self.assertIn("gh is logged into 'stub-user' but the config's github.username is 'someone-else'", out + err)
        self.assertFalse(any(c["args"][:2] == ["repo", "create"] for c in self._calls()))
