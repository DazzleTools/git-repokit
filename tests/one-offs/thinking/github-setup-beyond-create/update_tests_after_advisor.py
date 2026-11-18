"""Update the tests (and the red-green script) to the advisor-row fixes,
2026-11-17. Each replacement asserts its anchor occurs exactly once."""
from pathlib import Path


def edit(path, pairs, append=""):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, (path, s.count(old), old[:60])
        s = s.replace(old, new, 1)
    p.write_text(s + append, encoding="utf-8")


edit("tests/test_github_setup_publish.py", [
    ('''def test_continue_creates_only_the_missing_one():
    fake = FakeGhWithPulls(issues=[{"number": 1, "title": "Roadmap"}])
''', '''def test_continue_creates_only_the_missing_one():
    fake = FakeGhWithPulls(issues=[{"number": 1, "title": "Roadmap"}], pulls=[{"number": 2, "title": "Bump x"}])
'''),
    ('''def test_an_empty_repository_gets_1_and_2_without_a_question():''', '''def test_roadmap_at_1_alone_gets_quick_notes_at_2_without_a_question():
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


def test_an_empty_repository_gets_1_and_2_without_a_question():'''),
    ('''class _Mgr:
    project_name = "demo"
    config = {"branch_strategy": "main-only"}

    def run_git(self, *a, **k):
        return ""


def _integration():
    from repokit.remote_integration import RemoteIntegration
    ri = RemoteIntegration.__new__(RemoteIntegration)
    ri.repo_manager = _Mgr()''', '''class _Mgr:
    project_name = "demo"
    config = {"branch_strategy": "main-only"}

    def __init__(self, origin=""):
        self.origin = origin

    def run_git(self, args, *a, **k):
        return self.origin if args[:2] == ["remote", "get-url"] else ""


def _integration(origin=""):
    from repokit.remote_integration import RemoteIntegration
    ri = RemoteIntegration.__new__(RemoteIntegration)
    ri.repo_manager = _Mgr(origin)'''),
    ('''def test_the_update_path_creates_nothing_and_keeps_the_remote():
    ri = _integration()
''', '''def test_the_update_path_creates_nothing_and_keeps_the_remote():
    ri = _integration(origin="https://github.com/o/demo.git")
'''),
    ('''        assert ri.setup_remote_repository(existing_url="https://github.com/o/demo.git") is True
''', '''        assert ri.setup_remote_repository(update_existing=True) is True


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
'''),
], append='''

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
''')

# The old test whose expectation the partial-state fix changes (Roadmap #1
# alone used to be refused; Quick Notes now lands on #2, which is the goal).
edit("tests/test_github_setup.py", [
    ('''    """Mutation G2 (0.9.3) survived without this."""
    fake = FakeGh(issues=[{"number": 1, "title": "Roadmap"}])
    assert "would not be #1 and #2" in _setup(fake).issues("demo")[0]
    assert all(c[:2] != ["issue", "create"] for c in fake.calls)''', '''    """Mutation G2 (0.9.3) survived without this. Since 2026-11-17 the missing
    one is created when it still lands on its number (Roadmap #1 -> Quick
    Notes #2); "already there" needs both."""
    fake = FakeGh(issues=[{"number": 1, "title": "Roadmap"}])
    report = _setup(fake).issues("demo")
    assert report == ["issues: #2 Quick Notes -- Bugs, Features, Ideas"]
    assert [c[c.index("--title") + 1] for c in fake.calls if c[:2] == ["issue", "create"]] == \\
        ["Quick Notes -- Bugs, Features, Ideas"]'''),
])

edit("tests/one-offs/thinking/github-setup-beyond-create/redgreen.py", [
    ('''     "        if existing_url:\\n", "        if False:\\n",''',
     '''     'if update_existing and service.lower() == "github":', "if False:",'''),
    ('''     "if rc == 0 and github_repo_of(url):", "if False:",''',
     '''     "                update_existing=True,\\n", "",'''),
    ('''    ("M13 project''', '''    ("M14 the landing check ignored (partial state asks or misnumbers)", "repokit/github_setup.py",
     "if [landing[t] for t, _, _ in ISSUES] != [1, 2]:", "if everything:",
     [f"{T}::test_roadmap_at_1_alone_gets_quick_notes_at_2_without_a_question"]),
    ("M15 unreadable pull requests treated as none", "repokit/github_setup.py",
     "        if pulls is None:\\n            return", "        if pulls is None:\\n            pulls = []\\n        if False:\\n            return",
     [f"{T}::test_pull_requests_unreadable_creates_nothing"]),
    ("M16 unknown steps refused only after writing", "repokit/cli.py",
     '            setup_names(config.get("github_setup"))\\n', "            pass\\n",
     [f"{T}::TestCreateRecordsAndRefuses::test_unknown_step_refused_before_anything_is_written"]),
    ("M17 topics not recorded", "repokit/repo_manager.py",
     'repokit_config["topics"] = list(self.config["topics"])', "pass",
     [f"{T}::TestCreateRecordsAndRefuses::test_topics_are_recorded_for_a_later_publish"]),
    ("M18 the update path taken without being asked", "repokit/remote_integration.py",
     'if update_existing and service.lower() == "github":', 'if service.lower() == "github":',
     [f"{T}::test_without_update_existing_an_origin_on_github_still_creates"]),
    ("M13 project'''),
])
print("ok")
