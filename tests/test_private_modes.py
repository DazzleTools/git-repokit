"""0.10.3: three private modes, and the record folders a private-branch project promotes.

- ``nested`` (main-only's default): ./private is its own repository; nothing private at the root.
- ``nested-branch`` (the private-branch strategies' default for a create): ./private stays its own
  repository, and convos/, revisions/ and logs/ are tracked on the private branch.
- ``branch`` (opt-in, warned): private/ is tracked on the private branch as well.

The promoted folders are committed on the private branch after the public branches are cut, so no
public branch's history ever holds them. The proofs are the 2026-11-06 proof of concept (G4) as
tests: a plain `git add .` commits them on private; safe-merge leaves them out; a direct merge's
commit is refused; a public branch's history has none of them; pushing the private branch is
refused (git-repokit-common 0.4.4).

Every test works under tmp_path only, with git kept from looking above it (Safety Rule 1b: a test
asserting a commit or push is refused must not be able to make it anywhere real). The only remote is
a bare repository under tmp_path.

Design: 2026-11-06__23-30-00__dev-workflow-process__0-10-3-private-modes-and-promotion.md (and its
addendum "measurement contradicted the contract")
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from repokit import cli, defaults
from repokit.repo_manager import RepoManager, private_mode_for
from tests.conftest import repokit_common_available

needs_common = pytest.mark.skipif(not repokit_common_available(),
                                  reason="git-repokit-common not available locally (REPOKIT_COMMON_SOURCE=off)")

PROMOTED = ["convos", "revisions", "logs"]


@pytest.fixture(autouse=True)
def git_stays_in_tmp_path(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))


def git(cwd, *args, env=None):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, encoding="utf-8", errors="replace", env=env)


def create(where, monkeypatch, capfd, *args, language="python"):
    """`repokit create p ...` in-process from `where`; returns (exit code, output)."""
    where.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(where)
    lang = ["--language", language] if language else []
    monkeypatch.setattr(sys, "argv", ["repokit", "create", "p", *lang, "--license", "mit",
                                      "--no-push", "--user-name", "T", "--user-email", "t@example.com", *args])
    code = cli.main()
    out, err = capfd.readouterr()
    return code, out + err


def record(root):
    return json.loads((root / ".repokit.json").read_text(encoding="utf-8"))


def tree(root, ref):
    return git(root, "ls-tree", "-r", "--name-only", ref).stdout.split("\n")


def history_paths(root, ref):
    """Every path any commit reachable from ref added or changed."""
    out = git(root, "log", "--no-renames", "--format=", "--name-only", ref).stdout
    return {p for p in out.splitlines() if p}


def under(paths, folder):
    return [p for p in paths if p == folder or p.startswith(folder + "/")]


# -- the rank, the dependencies (in-process) -------------------------------

@pytest.mark.unit
def test_the_exposure_continuum_has_the_agreed_ranks():
    """Who can read a thing, from untracked to public, with controlled at zero."""
    c = defaults.EXPOSURE_CONTINUUM
    assert dict(c.ranks) == {"untracked": -2, "local": -1, "controlled": 0, "shared": 1, "public": 2}
    assert c.rank("local") < c.rank("shared")


@pytest.mark.unit
def test_the_exposure_record_names_the_vault_and_each_promoted_folder():
    """From the folders actually promoted, never from the mode name alone; every
    level stays below "shared", checked through the continuum."""
    assert defaults.mode_exposure([]) == {"private/": "local"}
    record_ = defaults.mode_exposure(["convos", "revisions", "logs", "private"])
    assert record_ == {"private/": "local", "convos/": "local", "revisions/": "local", "logs/": "local"}
    assert defaults.mode_exposure(["convos"]) == {"private/": "local", "convos/": "local"}
    assert all(defaults.EXPOSURE_CONTINUUM.is_colder(level, "shared") for level in record_.values())


# -- choosing the mode (in-process) ----------------------------------------

@pytest.mark.unit
@pytest.mark.parametrize("config,expected", [
    ({}, "nested-branch"),  # a missing key is the legacy "private" branch (mutation M4)
    ({"private_branch": None}, "nested"),
    ({"private_branch": "private"}, "nested-branch"),
    ({"private_branch": "private", "is_adoption": True}, "branch"),
    ({"private_branch": "private", "private_mode": "nested"}, "nested"),
    ({"private_branch": "private", "private_mode": "branch"}, "branch"),
    ({"private_branch": None, "private_mode": "nested"}, "nested"),
])
def test_the_default_mode_follows_the_strategy_and_the_command(config, expected):
    """A create with a private branch gets nested-branch; adopt keeps branch; asked-for wins."""
    mode, problem = private_mode_for(config)
    assert (mode, problem) == (expected, None)


@pytest.mark.unit
@pytest.mark.parametrize("mode", ["nested-branch", "branch"])
def test_a_branch_mode_without_a_private_branch_is_refused_with_the_fixes(mode):
    found, problem = private_mode_for({"private_branch": None, "private_mode": mode})
    assert found is None
    assert "--branch-strategy" in problem and "--private-mode nested" in problem


@pytest.mark.unit
def test_the_repo_manager_refuses_it_too():
    with pytest.raises(ValueError, match="--private-mode nested"):
        RepoManager({"name": "p", "private_branch": None, "private_mode": "branch"})


@pytest.mark.unit
def test_private_dirs_are_matched_by_folder_name_however_they_are_written():
    """--private-dirs convos/ or /revisions names the same folder (mutation M7)."""
    manager = RepoManager({"name": "p", "private_branch": "private",
                           "private_dirs": ["convos/", "/revisions", "logs", "notes"]})
    assert manager.promoted == ["convos", "revisions", "logs"]


@pytest.mark.unit
def test_every_form_of_a_promoted_line_is_dropped_and_none_comes_back(tmp_path):
    """The template's /logs/, a bare logs, a line with trailing spaces, and a
    private_dirs entry written logs/ (mutations M8, M9, M10)."""
    from types import SimpleNamespace
    (tmp_path / ".gitignore").write_text("/convos/   \nlogs\nrevisions/\n/private/\n", encoding="utf-8")
    fake = SimpleNamespace(repo_root=str(tmp_path), promoted=["convos", "revisions", "logs"],
                           config={"private_dirs": ["private", "convos", "revisions/", "logs/"]})
    RepoManager._write_private_ignores(fake)
    lines = [line.strip() for line in (tmp_path / ".gitignore").read_text(encoding="utf-8").splitlines()]
    for name in PROMOTED:
        assert not {f"/{name}/", f"{name}/", f"/{name}", name} & set(lines), (name, lines)
    assert "/private/" in lines


@pytest.mark.integration
def test_create_refuses_a_branch_mode_on_main_only_and_writes_nothing(tmp_path, monkeypatch, capfd, caplog):
    code, out = create(tmp_path, monkeypatch, capfd, "--private-mode", "branch")
    out += caplog.text  # the refusal is logged
    assert code != 0, out
    assert "--private-mode nested" in out and "--branch-strategy" in out
    assert not (tmp_path / "p").exists()


# -- main-only is unchanged ------------------------------------------------

@pytest.mark.integration
def test_main_only_keeps_the_nested_vault_and_no_record_folders_at_the_root(tmp_path, monkeypatch, capfd):
    code, out = create(tmp_path, monkeypatch, capfd)
    assert code == 0, out
    root = tmp_path / "p"
    assert record(root)["private_mode"] == "nested"
    assert (root / "private" / ".git").exists()
    for name in PROMOTED:
        assert not (root / name).exists(), name
        assert (root / "private" / name).is_dir(), name  # they live in the vault here
    ignore = (root / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "/convos/" in ignore and "/logs/" in ignore


# -- nested-branch: the vault stays a repository, the record folders are promoted

@pytest.fixture
def simple(tmp_path, monkeypatch, capfd):
    """A simple-strategy create (private + main + dev): the default nested-branch."""
    code, out = create(tmp_path, monkeypatch, capfd, "--branch-strategy", "simple")
    assert code == 0, out
    return tmp_path, tmp_path / "p" / "local", out


@pytest.mark.integration
def test_nested_branch_is_recorded_and_keeps_private_its_own_repository(simple):
    where, local, out = simple
    rec = record(local)
    assert rec["private_mode"] == "nested-branch"
    assert rec["private_exposure"]["convos/"] == "local"
    assert (local / "private" / ".git").exists()
    for ref in ("private", "main", "dev"):
        assert not under(tree(local, ref), "private"), ref
    # one home per folder: the promoted ones are at the root, not also in the vault
    for name in PROMOTED:
        assert not (local / "private" / name).exists(), name
    assert (local / "private" / "notes").is_dir()


@pytest.mark.integration
@pytest.mark.parametrize("strategy", ["standard", "gitflow", "github-flow", "minimal"])
def test_every_private_branch_strategy_gets_the_vault_and_the_promoted_folders(strategy, tmp_path, monkeypatch, capfd):
    """#16's first criterion: nested-branch works with every private-branch
    strategy (simple has its own tests above): the public branches are built,
    the vault is its own repository, and the folders are on private only."""
    code, out = create(tmp_path, monkeypatch, capfd, "--branch-strategy", strategy)
    assert code == 0, out
    local = tmp_path / "p" / "local"
    assert record(local)["private_mode"] == "nested-branch"
    assert (local / "private" / ".git").exists()
    assert "convos/.gitkeep" in tree(local, "private")
    public = [b for b in defaults.BRANCH_STRATEGIES[strategy]["branches"]]
    for ref in public:
        assert git(local, "rev-parse", "--verify", "-q", f"refs/heads/{ref}").returncode == 0, ref
        for name in PROMOTED + ["private"]:
            assert not under(history_paths(local, ref), name), (strategy, ref, name)


@pytest.mark.integration
def test_the_record_folders_are_tracked_on_private_and_on_no_public_branch(simple):
    where, local, out = simple
    on_private = tree(local, "private")
    assert "convos/.gitkeep" in on_private
    assert "revisions/.gitkeep" in on_private
    assert "logs/.gitignore" in on_private
    for ref in ("main", "dev"):
        for name in PROMOTED:
            assert not under(history_paths(local, ref), name), (ref, name)


@pytest.mark.integration
def test_a_plain_add_on_private_commits_conversations_and_revisions_but_not_run_logs(simple):
    """G4: no -f needed. revisions/ also proves the local excludes no longer hide it."""
    where, local, out = simple
    (local / "convos" / "talk.md").write_text("a conversation\n", encoding="utf-8")
    (local / "revisions" / "old.py").write_text("print(1)\n", encoding="utf-8")
    (local / "logs" / "run.log").write_text("noise\n", encoding="utf-8")
    git(local, "add", ".")
    staged = git(local, "diff", "--cached", "--name-only").stdout.split()
    assert "convos/talk.md" in staged
    assert "revisions/old.py" in staged
    assert "logs/run.log" not in staged
    # logs/ ignores its own run output, whatever the root .gitignore says (the
    # templates also ignore *.log; a custom template or an edited root may not)
    assert "*.log" in (local / "logs" / ".gitignore").read_text(encoding="utf-8").splitlines()


@pytest.mark.integration
def test_the_private_branch_gitignore_drops_the_promoted_lines(simple):
    where, local, out = simple
    ignore = {line.strip() for line in (local / ".gitignore").read_text(encoding="utf-8").splitlines()}
    for name in PROMOTED:
        assert f"/{name}/" not in ignore and f"{name}/" not in ignore, name
    assert "/private/" in ignore


@pytest.mark.integration
@needs_common
def test_the_hooks_still_name_the_promoted_folders_private(simple):
    from tests.test_common_guard import common_settings
    where, local, out = simple
    patterns = common_settings(local)["private-patterns"]
    for name in PROMOTED:
        assert f"{name}/" in patterns, name


@pytest.mark.integration
@needs_common
def test_safe_merge_leaves_the_promoted_files_out_and_a_direct_merge_is_refused(simple, monkeypatch, capfd):
    """G4, through the real hooks: safe-merge into dev excludes convos/; a hand merge's commit is
    refused by pre-commit on the public branch."""
    where, local, out = simple
    (local / "convos" / "talk.md").write_text("a conversation\n", encoding="utf-8")
    (local / "src.txt").write_text("feature\n", encoding="utf-8")
    git(local, "add", ".")
    r = git(local, "commit", "-q", "-m", "work")
    assert r.returncode == 0, r.stdout + r.stderr
    dev = where / "p" / "dev"
    if not dev.exists():
        git(local, "worktree", "add", "-q", str(dev), "dev")
    monkeypatch.chdir(dev)
    monkeypatch.setattr(sys, "argv", ["repokit", "safe-merge", "private"])
    cli.main()
    capfd.readouterr()
    staged = git(dev, "diff", "--cached", "--name-only").stdout.split()
    assert "src.txt" in staged
    assert not under(staged, "convos")
    git(dev, "merge", "--abort")
    git(dev, "reset", "-q", "--hard", "HEAD")
    git(dev, "merge", "-q", "--no-ff", "--no-commit", "private")
    r = git(dev, "commit", "-q", "-m", "direct merge")
    assert r.returncode != 0, r.stdout + r.stderr
    assert "convos/talk.md" in r.stdout + r.stderr
    git(dev, "merge", "--abort")


def _vendored_pre_push_refuses_private_content(local):
    hook = local / "scripts" / "repokit-common" / "hooks" / "pre-push"
    return hook.exists() and "PUSH BLOCKED - Private Content Protection" in hook.read_text(encoding="utf-8")


@pytest.mark.integration
@needs_common
def test_pushing_the_private_branch_is_refused_and_public_branches_push(simple):
    """G4's open gap, closed by git-repokit-common 0.4.4: the private branch carries promoted
    folders, so pushing it is refused; main and dev push, and a clone holds none of them."""
    where, local, out = simple
    if not _vendored_pre_push_refuses_private_content(local):
        pytest.skip("the vendored git-repokit-common predates 0.4.4's pre-push refusal")
    remote = where / "remote.git"
    git(where, "init", "-q", "--bare", str(remote))
    git(local, "remote", "add", "origin", str(remote))
    r = git(local, "push", "origin", "main", "dev")
    assert r.returncode == 0, r.stdout + r.stderr
    r = git(local, "push", "origin", "private")
    assert r.returncode != 0, r.stdout + r.stderr
    assert "PUSH BLOCKED - Private Content Protection" in r.stdout + r.stderr
    assert git(remote, "rev-parse", "--verify", "-q", "refs/heads/private").returncode != 0
    clone = where / "clone"
    git(where, "clone", "-q", str(remote), str(clone))
    for name in PROMOTED + ["private"]:
        assert not under(history_paths(clone, "--all"), name), name


@pytest.mark.integration
def test_a_global_ignore_on_the_promoted_folders_does_not_fail_the_create(tmp_path, monkeypatch, capfd, caplog):
    """An ignore rule outside the project (core.excludesFile, given through the
    environment for this test only) refuses the folders: the create still
    succeeds, and says what to do."""
    excludes = tmp_path / "global-excludes"
    excludes.write_text("convos/\nrevisions/\nlogs/\n", encoding="utf-8")
    n = int(os.environ.get("GIT_CONFIG_COUNT", "0"))
    monkeypatch.setenv("GIT_CONFIG_COUNT", str(n + 1))
    monkeypatch.setenv(f"GIT_CONFIG_KEY_{n}", "core.excludesFile")
    monkeypatch.setenv(f"GIT_CONFIG_VALUE_{n}", str(excludes))
    code, out = create(tmp_path / "w", monkeypatch, capfd, "--branch-strategy", "simple")
    assert code == 0, out + caplog.text
    assert "add them by hand" in caplog.text
    assert (tmp_path / "w" / "p" / "local" / "convos").is_dir()


@pytest.mark.integration
def test_guardrails_on_a_public_branch_never_hide_the_promoted_folders(tmp_path, monkeypatch, capfd):
    """minimal switches branches in one checkout, and .git/info/exclude is one
    file for all of them: `repokit setup-guardrails` run on main used to write
    revisions/ there, so back on private a plain add skipped it (found by the
    refactor-advisor, probed before the fix)."""
    from repokit.branch_utils import BranchContext
    code, out = create(tmp_path, monkeypatch, capfd, "--branch-strategy", "minimal")
    assert code == 0, out
    local = tmp_path / "p" / "local"
    assert git(local, "checkout", "-q", "main").returncode == 0
    BranchContext(str(local)).setup_branch_excludes()
    capfd.readouterr()
    assert git(local, "checkout", "-q", "private").returncode == 0
    (local / "revisions").mkdir(exist_ok=True)
    (local / "revisions" / "x.md").write_text("old\n", encoding="utf-8")
    assert git(local, "check-ignore", "-q", "revisions/x.md").returncode == 1  # not ignored
    exclude = (local / ".git" / "info" / "exclude").read_text(encoding="utf-8").splitlines()
    assert "private/claude/" in exclude  # the other public-branch excludes are still written


# -- branch (opt-in): private/ itself on the private branch -----------------

@pytest.mark.integration
def test_branch_mode_is_warned_recorded_and_tracks_private_on_the_private_branch_only(tmp_path, monkeypatch, capfd, caplog):
    code, out = create(tmp_path, monkeypatch, capfd, "--branch-strategy", "simple", "--private-mode", "branch")
    out += caplog.text  # the warning is logged
    assert code == 0, out
    local = tmp_path / "p" / "local"
    assert "--private-mode branch" in out and "nested-branch" in out  # the warning names the default
    assert record(local)["private_mode"] == "branch"
    assert not (local / "private" / ".git").exists()
    assert under(tree(local, "private"), "private")
    # a plain add on the private branch takes a new private/ file (no -f)
    (local / "private" / "notes").mkdir(parents=True, exist_ok=True)
    (local / "private" / "notes" / "new.md").write_text("a note\n", encoding="utf-8")
    git(local, "add", ".")
    assert "private/notes/new.md" in git(local, "diff", "--cached", "--name-only").stdout.split()
    git(local, "reset", "-q")
    for ref in ("main", "dev"):
        assert not under(history_paths(local, ref), "private"), ref
        assert not under(history_paths(local, ref), "convos"), ref
