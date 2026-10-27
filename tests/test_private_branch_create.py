"""0.9.12: the private-branch create builds clean public branches safely.

The private-branch strategies (standard, simple, gitflow, github-flow,
minimal) cut each public branch from the private branch. Until 0.9.12:

- `git reset --hard private` failed ("ambiguous argument 'private': both
  revision and filename", because a `private/` folder exists too), so every
  public branch held only the initial commit, and the create still exited 0;
- the step after the reset -- never reached while it failed -- deleted
  untracked files matching the sensitive patterns (.env, *.log, logs/...)
  from the private working folder;
- the .github step ran `git add`/`git commit` in <name>/github even when no
  worktree was there, and git walked up into whatever repository enclosed
  the project.

Every test here works under tmp_path only: the projects, the planted files and
the enclosing repository are all the test's own (Safety Rule 1b -- a test that
asserts files are not deleted must not be able to delete real ones). The
measure and the proof of concept behind these tests:
tests/one-offs/thinking/p4-measure-0.9.12-private-ref/ and
tests/one-offs/thinking/p4-poc-0.9.12-fix/.

Design: 2026-10-25__21-48-58__dev-workflow-process__0-9-12-private-branch-create-fixed-safely.md
"""
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from repokit import cli
from repokit.repo_manager import RepoManager

STRATEGIES = ["standard", "simple", "gitflow", "github-flow", "minimal"]
PRIVATE = re.compile(r"^(private/|CLAUDE\.md$|convos/|logs/|revisions/)")
PLANTED = {".env": "SECRET=keep-me\n", "app.log": "a log line\n", "logs/run.log": "run\n"}


@pytest.fixture(autouse=True)
def git_stays_in_tmp_path(tmp_path, monkeypatch):
    """Git may not look for a repository above tmp_path. pytest's tmp_path is
    under %TEMP%, which can sit inside a real repository (a home-directory
    repo), so a create whose code is wrong -- a mutant, a reverted fix --
    could otherwise commit into it. Repositories inside tmp_path (T3's parent)
    are still found."""
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, stdin=subprocess.DEVNULL)


def create(where, monkeypatch, capfd, *args):
    """`repokit create p ...` in-process from `where`; returns (exit code, output)."""
    where.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(where)
    monkeypatch.setattr(sys, "argv", ["repokit", "create", "p", "--language", "python", "--license", "mit",
                                      "--no-push", "--user-name", "T", "--user-email", "t@example.com", *args])
    code = cli.main()
    out, err = capfd.readouterr()
    return code, out + err


def errors(caplog):
    """The ERROR (and worse) log records the create wrote -- read from pytest's
    log capture, which receives every record whatever handlers repokit set."""
    return [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]


def branch_trees(local):
    refs = git(local, "for-each-ref", "--format=%(refname:short)", "refs/heads").stdout.split()
    return {b: set(git(local, "ls-tree", "-r", "--name-only", f"refs/heads/{b}").stdout.splitlines()) for b in refs}


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_every_public_branch_is_the_private_branch_less_its_private_files(strategy, tmp_path, monkeypatch, capfd,
                                                                         caplog):
    """T1: no ambiguity error, no ERROR line, and each public branch holds the
    private branch's files minus its private ones."""
    caplog.set_level(logging.INFO)
    code, log = create(tmp_path / "w", monkeypatch, capfd, "--branch-strategy", strategy)
    assert code == 0, log
    assert "ambiguous argument" not in caplog.text + log
    assert errors(caplog) == []
    trees = branch_trees(tmp_path / "w" / "p" / "local")
    private = trees.pop("private")
    assert trees, "no public branch was made"
    expected = {f for f in private if not PRIVATE.match(f)}
    for branch, files in trees.items():
        assert files == expected, f"{branch}: missing {sorted(expected - files)}, extra {sorted(files - expected)}"


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_nothing_under_private_reaches_a_public_branch(strategy, tmp_path, monkeypatch, capfd):
    """T6, djdarcy's rule (2026-10-26): "The only private we care about in the
    private-public branch strategy is the "private" branch as the source. The
    "private" subfolder as its own git repo NEVER populates outwards ever.\""""
    code, log = create(tmp_path / "w", monkeypatch, capfd, "--branch-strategy", strategy)
    assert code == 0, log
    trees = branch_trees(tmp_path / "w" / "p" / "local")
    trees.pop("private")
    leaked = {b: sorted(f for f in files if f == "private" or f.startswith("private/")) for b, files in trees.items()}
    assert not any(leaked.values()), leaked


def test_files_in_the_private_working_folder_survive_the_public_branches(tmp_path, monkeypatch, capfd):
    """T2: untracked .env, app.log and logs/run.log in local/ when the public
    branches are cut are still on disk afterwards, and in no public branch.
    The plant happens inside the create, just before the first public branch
    is cut, by wrapping the method that cuts it -- the files exist only under
    tmp_path."""
    original = RepoManager._create_clean_public_branch
    planted = []

    def plant_then_cut(self, branch_name, source_branch):
        if not planted:
            for rel, text in PLANTED.items():
                path = Path(self.repo_root, rel)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
                planted.append(path)
        return original(self, branch_name, source_branch)

    monkeypatch.setattr(RepoManager, "_create_clean_public_branch", plant_then_cut)
    code, log = create(tmp_path / "w", monkeypatch, capfd, "--branch-strategy", "standard")
    local = tmp_path / "w" / "p" / "local"
    assert planted and all(str(p).startswith(str(tmp_path)) for p in planted)
    assert [rel for rel in PLANTED if not (local / rel).is_file()] == [], log
    for rel, text in PLANTED.items():
        assert (local / rel).read_text(encoding="utf-8") == text
    trees = branch_trees(local)
    trees.pop("private")
    assert not {b: sorted(set(PLANTED) & files) for b, files in trees.items() if set(PLANTED) & files}


@pytest.mark.parametrize("strategy,extra,no_github", [
    ("minimal", (), True),
    ("simple", ("--branch-dir-main", "public"), True),
])
def test_a_create_inside_another_repository_leaves_it_alone(strategy, extra, no_github, tmp_path, monkeypatch, capfd):
    """T3: a create inside an enclosing repository (the test's own, under
    tmp_path) adds no commit to it and stages nothing in it, and makes no
    <name>/github folder where main is not checked out there."""
    parent = tmp_path / "parent"
    parent.mkdir()
    git(parent, "init", "-q", "-b", "main")
    (parent / "keep.txt").write_text("the parent's own file\n")
    git(parent, "add", "keep.txt")
    git(parent, "-c", "user.name=T", "-c", "user.email=t@example.com", "commit", "-qm", "parent")
    head = git(parent, "rev-parse", "HEAD").stdout.strip()
    code, log = create(parent / "work", monkeypatch, capfd, "--branch-strategy", strategy, *extra)
    assert code == 0, log
    assert git(parent, "rev-parse", "HEAD").stdout.strip() == head, git(parent, "log", "--oneline", "-3").stdout
    assert git(parent, "diff", "--cached", "--name-only").stdout.strip() == ""
    if no_github:
        assert not (parent / "work" / "p" / "github").exists()


def test_a_public_branch_that_cannot_be_built_fails_the_create(tmp_path, monkeypatch, capfd, caplog):
    """T4: when cutting `dev` fails, the create says so and exits non-zero."""
    caplog.set_level(logging.INFO)
    original = RepoManager._create_clean_public_branch

    def fail_on_dev(self, branch_name, source_branch):
        if branch_name == "dev":
            raise RuntimeError("forced failure cutting dev")
        return original(self, branch_name, source_branch)

    monkeypatch.setattr(RepoManager, "_create_clean_public_branch", fail_on_dev)
    code, log = create(tmp_path / "w", monkeypatch, capfd, "--branch-strategy", "standard")
    assert code != 0, log
    assert any("dev" in e for e in errors(caplog)), errors(caplog)
    # The remaining branches were still cut and local/ is back on the private
    # branch before the create fails, so the person's checkout is not left on
    # a public branch.
    local = tmp_path / "w" / "p" / "local"
    assert git(local, "branch", "--show-current").stdout.strip() == "private"


def test_a_public_branch_that_fails_verification_fails_the_create(tmp_path, monkeypatch, capfd, caplog):
    """T4b: a public branch that is built but fails the private-content check
    fails the create as well -- not only one whose cut raises."""
    caplog.set_level(logging.INFO)
    original = RepoManager._verify_clean_branch
    monkeypatch.setattr(RepoManager, "_verify_clean_branch",
                        lambda self, branch: False if branch == "dev" else original(self, branch))
    code, log = create(tmp_path / "w", monkeypatch, capfd, "--branch-strategy", "standard")
    assert code != 0, log
    assert any("dev" in e and "verification" in e for e in errors(caplog)), errors(caplog)


@pytest.mark.parametrize("tracked", [
    {"config/.env": "TOKEN=private\n"},
    {"old.bak": "an old copy\n"},
], ids=["nested-env", "root-bak"])
def test_tracked_sensitive_files_stay_private_and_on_disk(tracked, tmp_path, monkeypatch, capfd):
    """T7: sensitive files the private branch tracks reach no public branch,
    and are still on disk and on the private branch afterwards. root-bak is
    also U10's anchor: the commit that takes old.bak out of a public branch
    used to be refused by the created project's pre-commit hook, which
    counted the deletion as an added private file. They are
    committed inside the create, just before the first public branch is cut,
    all under tmp_path."""
    original = RepoManager._create_clean_public_branch
    done = []

    def commit_then_cut(self, branch_name, source_branch):
        if not done:
            for rel, text in tracked.items():
                path = Path(self.repo_root, rel)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            git(self.repo_root, "add", "-f", *tracked)
            git(self.repo_root, "-c", "user.name=T", "-c", "user.email=t@example.com",
                "commit", "-qm", "tracked sensitive files")
            done.append(True)
        return original(self, branch_name, source_branch)

    monkeypatch.setattr(RepoManager, "_create_clean_public_branch", commit_then_cut)
    code, log = create(tmp_path / "w", monkeypatch, capfd, "--branch-strategy", "standard")
    assert code == 0, log
    local = tmp_path / "w" / "p" / "local"
    trees = branch_trees(local)
    assert set(tracked) <= trees.pop("private")
    assert not {b: sorted(set(tracked) & files) for b, files in trees.items() if set(tracked) & files}
    for rel, text in tracked.items():
        assert (local / rel).read_text(encoding="utf-8") == text


def test_branch_exists_compares_whole_names(tmp_path):
    """T5: `dev` is not found among branches named `develop` and `* main`, nor
    when only a tag is named `dev`."""
    repo = tmp_path / "r"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "-c", "user.name=T", "-c", "user.email=t@example.com", "commit", "-q", "--allow-empty", "-m", "a")
    git(repo, "branch", "develop")
    git(repo, "tag", "dev")
    assert RepoManager._branch_exists_in(str(repo), "dev") is False
    assert RepoManager._branch_exists_in(str(repo), "develop") is True
    assert RepoManager._branch_exists_in(str(repo), "main") is True


def test_the_guard_does_not_count_a_deleted_file_as_staged(tmp_path):
    """U10: the guardrail hook's list of staged files holds what a commit adds
    or changes, never a deletion -- removing a private file from a public
    branch must not be refused as if it added one."""
    from repokit.branch_utils import BranchContext
    repo = tmp_path / "r"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / "old.bak").write_text("x\n")
    (repo / "kept.txt").write_text("a\n")
    git(repo, "add", "old.bak", "kept.txt")
    git(repo, "-c", "user.name=T", "-c", "user.email=t@example.com", "commit", "-qm", "seed")
    git(repo, "rm", "-q", "--cached", "old.bak")
    (repo / "kept.txt").write_text("b\n")
    git(repo, "add", "kept.txt")
    assert BranchContext(str(repo)).get_staged_files() == ["kept.txt"]


def _local_repo(mgr, first_branch):
    """A repository at the manager's repo_root (under tmp_path) with one commit."""
    local = Path(mgr.repo_root)
    local.mkdir(parents=True)
    git(local, "init", "-q", "-b", first_branch)
    git(local, "config", "user.name", "T")
    git(local, "config", "user.email", "t@example.com")
    (local / "a.txt").write_text("a\n")
    git(local, "add", "a.txt")
    git(local, "commit", "-qm", "a")
    return local


def same_path(a, b):
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def test_worktree_of_finds_only_another_worktree_of_exactly_that_branch(tmp_path):
    """T8: the default branch checked out in local/ itself has no worktree to
    write into; a worktree of `main2` is not one of `main`; a worktree of
    `dev` elsewhere is found."""
    p = tmp_path / "p"
    mgr = RepoManager({"name": str(p), "private_branch": None, "worktrees": ["main"]})
    local = _local_repo(mgr, "main")
    git(local, "branch", "main2")
    git(local, "worktree", "add", "-q", str(p / "w2"), "main2")
    git(local, "branch", "dev")
    git(local, "worktree", "add", "-q", str(p / "devdir"), "dev")
    assert mgr._worktree_of("main") is None
    assert same_path(mgr._worktree_of("dev"), p / "devdir")


def _manager_with_github_on_private(p, **config):
    """A private-branch layout under tmp_path whose private branch carries
    .github; the branch `base` is the commit before it."""
    mgr = RepoManager({"name": str(p), "private_branch": "private", "github": True, **config})
    local = _local_repo(mgr, "private")
    git(local, "branch", "base")
    (local / ".github" / "workflows").mkdir(parents=True)
    (local / ".github" / "workflows" / "ci.yml").write_text("name: ci\n")
    git(local, "add", ".github")
    git(local, "commit", "-qm", "github")
    return mgr, local


def test_github_step_writes_into_the_default_branch_worktree_by_its_configured_name(tmp_path):
    """T9: with the default branch named `trunk` and checked out in a worktree,
    the .github files are committed there."""
    p = tmp_path / "p"
    mgr, local = _manager_with_github_on_private(p, default_branch="trunk")
    git(local, "branch", "trunk", "base")
    git(local, "worktree", "add", "-q", str(p / "pub"), "trunk")
    mgr._setup_github_integration()
    assert (p / "pub" / ".github" / "workflows" / "ci.yml").is_file()
    assert git(local, "log", "-1", "--format=%s", "trunk").stdout.strip() == "Add GitHub configuration files"


def test_github_step_leaves_a_folder_that_is_not_a_worktree_alone(tmp_path):
    """T10: with no worktree for the default branch, a plain <name>/github
    folder gets nothing, and the repository enclosing the project (the test's
    own, under tmp_path) gets no commit."""
    parent = tmp_path / "parent"
    parent.mkdir()
    git(parent, "init", "-q", "-b", "main")
    (parent / "keep.txt").write_text("the parent's own file\n")
    git(parent, "add", "keep.txt")
    git(parent, "-c", "user.name=T", "-c", "user.email=t@example.com", "commit", "-qm", "parent")
    head = git(parent, "rev-parse", "HEAD").stdout.strip()
    p = parent / "p"
    mgr, local = _manager_with_github_on_private(p)
    (p / "github").mkdir()
    mgr._setup_github_integration()
    assert not (p / "github" / ".github").exists()
    assert git(parent, "rev-parse", "HEAD").stdout.strip() == head
