"""0.10.2: every project is guarded by git-repokit-common, configured from
git-repokit's branch model.

Until 0.10.2 the private-branch strategies got git-repokit-common only with
--with-common, and a single-branch project got it without its private-content
settings (they were written only when there was a private branch). Measured
in the 2026-10-31 consultation, under tmp_path-style scratch folders:

- a single-branch project with `--private-dirs private,notes` committed
  notes/x.md to main, the public branch; the hook ran and passed it;
- a github-flow project committed a forced convos/x.md on feature/login and
  pushed it, under both hooks, because both treat feature/* as private.

Every test here works under tmp_path only, with git kept from looking above it
(Safety Rule 1b: a test asserting a commit is refused must not be able to make
that commit anywhere real).

Design: 2026-10-31__18-24-41__DISCUSS_Rnd3_FINAL_ASSESSMENT_(cli-layout-and-private-work).md
(addenda 18:29, 18:31, 19:02)
"""
import logging
import subprocess
import sys

import pytest

from repokit import cli, common_kit
from tests.conftest import repokit_common_available

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

DEFAULTS = list(common_kit.REPOKIT_COMMON_PRIVATE_BRANCHES)
NO_FEATURE = [b for b in DEFAULTS if b not in ("feature/*", "feat/*")]

needs_common = pytest.mark.skipif(not repokit_common_available(),
                                  reason="git-repokit-common not available locally (REPOKIT_COMMON_SOURCE=off)")


@pytest.fixture(autouse=True)
def git_stays_in_tmp_path(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, encoding="utf-8", errors="replace")


def create(where, monkeypatch, capfd, *args, language="python"):
    """`repokit create p ...` in-process from `where`; returns (exit code, output).
    language=None makes a bare project (no layers), the case the 0.10.2
    checklist's spot check caught with no settings written at all."""
    where.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(where)
    lang = ["--language", language] if language else []
    monkeypatch.setattr(sys, "argv", ["repokit", "create", "p", *lang, "--license", "mit",
                                      "--no-push", "--user-name", "T", "--user-email", "t@example.com", *args])
    code = cli.main()
    out, err = capfd.readouterr()
    return code, out + err


def repo_root(where, strategy):
    return where / "p" if strategy == "main-only" else where / "p" / "local"


def common_settings(root):
    """[tool.repokit-common] from pyproject.toml or .repokit-common.toml."""
    for name in ("pyproject.toml", ".repokit-common.toml"):
        path = root / name
        if path.exists():
            table = tomllib.loads(path.read_text(encoding="utf-8")).get("tool", {}).get("repokit-common")
            if table is not None:
                return table
    return {}


# -- the rule, in-process --------------------------------------------------

@pytest.mark.unit
@pytest.mark.parametrize("strategy,expected", [
    ("main-only", DEFAULTS),
    ("standard", DEFAULTS),
    ("simple", DEFAULTS),
    ("minimal", DEFAULTS),
    ("github-flow", NO_FEATURE),
    ("gitflow", NO_FEATURE),
])
def test_private_branches_follow_the_strategy(strategy, expected):
    assert common_kit.private_branches(strategy, "private") == expected


@pytest.mark.unit
def test_a_custom_private_branch_is_added():
    assert common_kit.private_branches("github-flow", "scratch") == NO_FEATURE + ["scratch"]


@pytest.mark.unit
def test_settings_always_name_the_private_branches():
    """Even with no private branch (main-only): a project that later gains
    one is already guarded."""
    settings = common_kit.private_branch_settings(None, ["notes/"], "main-only")
    assert settings == {"private-patterns": ["notes/"], "private-branches": DEFAULTS}


@pytest.mark.unit
def test_private_patterns_are_written_sorted_and_once():
    """The same project always writes the same file: CLAUDE.md, the sensitive
    files and --private-dirs can name a path twice (mutation sweep M6, M7)."""
    settings = common_kit.private_branch_settings("private", ["notes/", "CLAUDE.md", ".env", "notes/"])
    assert settings["private-patterns"] == [".env", "CLAUDE.md", "notes/"]


# -- real creates ------------------------------------------------------------

@pytest.mark.integration
@needs_common
@pytest.mark.parametrize("strategy,expected", [
    ("main-only", DEFAULTS),
    ("standard", DEFAULTS),
    ("github-flow", NO_FEATURE),
])
def test_every_project_gets_the_guard_settings(tmp_path, monkeypatch, capfd, strategy, expected):
    code, out = create(tmp_path, monkeypatch, capfd, "--branch-strategy", strategy,
                       "--directories", "notes", "--private-dirs", "private,notes,convos,revisions,logs")
    assert code == 0, out
    root = repo_root(tmp_path, strategy)
    assert (root / common_kit.PREFIX).is_dir(), "git-repokit-common not vendored"
    settings = common_settings(root)
    assert "notes/" in settings.get("private-patterns", []), settings
    assert settings.get("private-branches") == expected


@pytest.mark.integration
@needs_common
@pytest.mark.parametrize("language", ["python", None])
def test_single_branch_refuses_a_private_folder_on_main(tmp_path, monkeypatch, capfd, language):
    """The measured leak: notes/ named only by --private-dirs reached main --
    with a language, and in a bare project, which has no layers."""
    code, out = create(tmp_path, monkeypatch, capfd,
                       "--directories", "notes", "--private-dirs", "private,notes,convos,revisions,logs",
                       language=language)
    assert code == 0, out
    root = tmp_path / "p"
    (root / "notes" / "x.md").write_text("a private note\n", encoding="utf-8")
    assert git(root, "add", "-f", "notes/x.md").returncode == 0
    result = git(root, "commit", "-q", "-m", "a note")
    assert result.returncode != 0, "notes/x.md was committed to main"
    assert "notes/x.md" in result.stdout + result.stderr
    assert "notes/x.md" not in git(root, "ls-tree", "-r", "--name-only", "HEAD").stdout


@pytest.mark.integration
@needs_common
def test_github_flow_refuses_a_forced_private_file_on_a_feature_branch(tmp_path, monkeypatch, capfd):
    """The measured push gap: feature branches are public in github-flow."""
    code, out = create(tmp_path, monkeypatch, capfd, "--branch-strategy", "github-flow")
    assert code == 0, out
    public = tmp_path / "p" / "github"
    assert git(public, "switch", "-q", "-c", "feature/login").returncode == 0
    (public / "convos").mkdir(exist_ok=True)
    (public / "convos" / "x.md").write_text("a private conversation\n", encoding="utf-8")
    assert git(public, "add", "-f", "convos/x.md").returncode == 0
    result = git(public, "commit", "-q", "-m", "forced private file")
    assert result.returncode != 0, "convos/x.md was committed on feature/login"
    assert "convos/x.md" in result.stdout + result.stderr


@pytest.mark.integration
@needs_common
def test_the_private_branch_still_takes_a_forced_private_file(tmp_path, monkeypatch, capfd):
    """git add -f is the person's override where private content belongs."""
    code, out = create(tmp_path, monkeypatch, capfd, "--branch-strategy", "github-flow")
    assert code == 0, out
    local = tmp_path / "p" / "local"
    (local / "convos").mkdir(exist_ok=True)
    (local / "convos" / "x.md").write_text("a private conversation\n", encoding="utf-8")
    assert git(local, "add", "-f", "convos/x.md").returncode == 0
    result = git(local, "commit", "-q", "-m", "kept on private")
    assert result.returncode == 0, result.stdout + result.stderr


# -- opting out warns ----------------------------------------------------------

def _warnings(caplog):
    return [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]


@pytest.mark.integration
def test_no_common_warns(tmp_path, monkeypatch, capfd, caplog):
    code, out = create(tmp_path, monkeypatch, capfd, "--branch-strategy", "simple", "--no-common")
    assert code == 0, out
    assert not (tmp_path / "p" / "local" / common_kit.PREFIX).exists()
    found = [w for w in _warnings(caplog) if "--no-common" in w]
    assert found and "setup-guardrails --vendor" in found[0], _warnings(caplog)


@pytest.mark.integration
def test_vendoring_switched_off_warns(tmp_path, monkeypatch, capfd, caplog):
    monkeypatch.setenv(common_kit.SOURCE_ENV, "off")
    code, out = create(tmp_path, monkeypatch, capfd)
    assert code == 0, out
    found = [w for w in _warnings(caplog) if "vendoring switched off" in w]
    assert found and "setup-guardrails --vendor" in found[0], _warnings(caplog)


# -- part 2: the other guards read --private-dirs ---------------------------

PRIVATE_NOTES = ("--directories", "notes", "--private-dirs", "private,notes,convos,revisions,logs")


def gitignore_lines(root):
    return {line.strip() for line in (root / ".gitignore").read_text(encoding="utf-8").splitlines()}


def commit_on_private(local, *paths):
    """Commit planted private files on the private branch (forced: ignored there)."""
    for rel in paths:
        target = local / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("private\n", encoding="utf-8")
    assert git(local, "add", "-f", *paths).returncode == 0
    result = git(local, "commit", "-q", "-m", "private work")
    assert result.returncode == 0, result.stdout + result.stderr


def dev_worktree(tmp_path):
    local, dev = tmp_path / "p" / "local", tmp_path / "p" / "dev"
    if not dev.exists():
        assert git(local, "worktree", "add", "-q", str(dev), "dev").returncode == 0
    return dev


@pytest.mark.integration
@pytest.mark.parametrize("strategy", ["main-only", "simple"])
def test_gitignore_keeps_the_private_dirs_after_the_templates(tmp_path, monkeypatch, capfd, strategy):
    """The language templates rewrite .gitignore; --private-dirs' lines used to
    go with it, so `git add .` staged notes/."""
    code, out = create(tmp_path, monkeypatch, capfd, "--branch-strategy", strategy, *PRIVATE_NOTES)
    assert code == 0, out
    root = repo_root(tmp_path, strategy)
    assert "/notes/" in gitignore_lines(root)
    (root / "notes" / "x.md").write_text("a private note\n", encoding="utf-8")
    assert git(root, "check-ignore", "-q", "notes/x.md").returncode == 0


TABLE = '[tool.repokit-common]\nprivate-patterns = ["{}"]\n'


@pytest.mark.unit
def test_read_settings_prefers_pyproject(tmp_path):
    """The order repokit-common reads them in: pyproject.toml, then
    .repokit-common.toml (safe-merge and the hook must agree)."""
    (tmp_path / "pyproject.toml").write_text(TABLE.format("a/"), encoding="utf-8")
    (tmp_path / ".repokit-common.toml").write_text(TABLE.format("b/"), encoding="utf-8")
    assert common_kit.read_settings(str(tmp_path))["private-patterns"] == ["a/"]


@pytest.mark.unit
def test_read_settings_falls_back_past_a_pyproject_without_the_table(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "p"\n', encoding="utf-8")
    (tmp_path / ".repokit-common.toml").write_text(TABLE.format("b/"), encoding="utf-8")
    assert common_kit.read_settings(str(tmp_path))["private-patterns"] == ["b/"]


@pytest.mark.unit
def test_read_settings_skips_a_file_it_cannot_parse(tmp_path):
    (tmp_path / "pyproject.toml").write_text("this is [not toml", encoding="utf-8")
    (tmp_path / ".repokit-common.toml").write_text(TABLE.format("b/"), encoding="utf-8")
    assert common_kit.read_settings(str(tmp_path))["private-patterns"] == ["b/"]


@pytest.mark.unit
def test_read_settings_without_either_file_is_empty(tmp_path):
    assert common_kit.read_settings(str(tmp_path)) == {}


@pytest.mark.unit
def test_read_settings_skips_a_value_that_is_not_a_table(tmp_path):
    """Mutation sweep M3: `repokit-common = "x"` is not the settings table."""
    (tmp_path / "pyproject.toml").write_text('[tool]\nrepokit-common = "x"\n', encoding="utf-8")
    (tmp_path / ".repokit-common.toml").write_text(TABLE.format("b/"), encoding="utf-8")
    assert common_kit.read_settings(str(tmp_path))["private-patterns"] == ["b/"]


def write_ignores(tmp_path, existing, private_dirs):
    """Run _write_private_ignores on a planted .gitignore; return its lines."""
    from types import SimpleNamespace
    from repokit.repo_manager import RepoManager
    (tmp_path / ".gitignore").write_text(existing, encoding="utf-8")
    # promoted=[]: a nested-mode project (0.10.3 added the attribute)
    RepoManager._write_private_ignores(SimpleNamespace(repo_root=str(tmp_path), promoted=[],
                                                       config={"private_dirs": private_dirs}))
    return [line.strip() for line in (tmp_path / ".gitignore").read_text(encoding="utf-8").splitlines()]


@pytest.mark.unit
def test_gitignore_line_already_there_counts_with_trailing_spaces(tmp_path):
    """Mutation sweep M5."""
    lines = write_ignores(tmp_path, "/logs/   \n", ["logs"])
    assert lines.count("/logs/") == 1


@pytest.mark.unit
def test_gitignore_folder_name_with_slashes_is_normalised(tmp_path):
    """Mutation sweep M6: --private-dirs notes/ is the folder notes."""
    lines = write_ignores(tmp_path, "", ["notes/", "/drafts"])
    assert "/notes/" in lines and "/drafts/" in lines
    assert not any("//" in line for line in lines)


@pytest.mark.unit
def test_gitignore_unanchored_line_already_covers_the_folder(tmp_path):
    """Mutation sweep M8: 'notes/' already ignores the root notes/."""
    lines = write_ignores(tmp_path, "notes/\n", ["notes"])
    assert "/notes/" not in lines


def resolved_private_dirs(tmp_path, monkeypatch, **cli):
    """ConfigManager's private_dirs for these CLI options, read from an empty
    folder (ConfigManager reads .repokit.json from the current directory)."""
    from repokit.config import ConfigManager
    monkeypatch.chdir(tmp_path)
    manager = ConfigManager()
    manager.set_cli_config(cli)
    return manager.config["private_dirs"]


@pytest.mark.unit
def test_private_set_adds_to_private_dirs_once(tmp_path, monkeypatch):
    """Mutation sweep M11, M13: the set's folders join --private-dirs, each once."""
    dirs = resolved_private_dirs(tmp_path, monkeypatch, private_dirs=["notes", "private"],
                                 private_set="enhanced")
    assert dirs[:2] == ["notes", "private"]
    assert {"credentials", "secrets", "local"} <= set(dirs)
    assert len(dirs) == len(set(dirs))


@pytest.mark.unit
def test_the_standard_private_set_changes_nothing(tmp_path, monkeypatch):
    """Mutation sweep M10: --private-dirs stays what the person named."""
    assert resolved_private_dirs(tmp_path, monkeypatch, private_dirs=["notes"],
                                 private_set="standard") == ["notes"]


@pytest.mark.unit
def test_gitignore_line_is_matched_whole_not_as_a_substring(tmp_path):
    """'/docs/' used to count as present inside a line like 'private/docs/'
    (the public branches' .gitignore carries it; a layer's could too)."""
    from types import SimpleNamespace
    from repokit.repo_manager import RepoManager
    (tmp_path / ".gitignore").write_text("private/docs/\n/logs/\n", encoding="utf-8")
    fake = SimpleNamespace(repo_root=str(tmp_path), promoted=[], config={"private_dirs": ["docs", "logs"]})
    RepoManager._write_private_ignores(fake)
    lines = gitignore_lines(tmp_path)
    assert "/docs/" in lines
    assert sum(1 for line in (tmp_path / ".gitignore").read_text(encoding="utf-8").splitlines()
               if line.strip() == "/logs/") == 1, "a line already there is not written twice"


@pytest.mark.integration
@needs_common
def test_enhanced_private_set_reaches_the_hook(tmp_path, monkeypatch, capfd):
    """--private-set without a profile or groups was read nowhere. The
    template already ignores local/, secrets/ and credentials/; what the set
    never reached was the hook's list of folders kept off public branches."""
    code, out = create(tmp_path, monkeypatch, capfd, "--private-set", "enhanced")
    assert code == 0, out
    patterns = common_settings(tmp_path / "p").get("private-patterns", [])
    assert {"local/", "secrets/", "credentials/"} <= set(patterns), patterns


@pytest.mark.integration
@needs_common
def test_safe_merge_leaves_out_the_private_dirs(tmp_path, monkeypatch, capfd):
    """Measured: safe-merge staged notes/x.md (and convos/x.md) into dev."""
    code, out = create(tmp_path, monkeypatch, capfd, "--branch-strategy", "simple", *PRIVATE_NOTES)
    assert code == 0, out
    commit_on_private(tmp_path / "p" / "local", "notes/x.md", "convos/x.md")
    dev = dev_worktree(tmp_path)
    merged = subprocess.run([sys.executable, "-m", "repokit", "safe-merge", "private"], cwd=dev,
                            capture_output=True, text=True, stdin=subprocess.DEVNULL,
                            encoding="utf-8", errors="replace")
    assert merged.returncode == 0, merged.stdout + merged.stderr
    staged = git(dev, "diff", "--cached", "--name-only").stdout.split()
    assert "notes/x.md" not in staged and "convos/x.md" not in staged, staged


@pytest.mark.integration
def test_no_common_hook_refuses_the_private_dirs_on_a_public_branch(tmp_path, monkeypatch, capfd):
    """Measured: safe-merge left notes/x.md staged (it knows only its built-in
    folders when no settings file exists) and git-repokit's own hook passed it
    into dev. The hook is the guard that has to name it."""
    code, out = create(tmp_path, monkeypatch, capfd, "--branch-strategy", "simple", "--no-common", *PRIVATE_NOTES)
    assert code == 0, out
    commit_on_private(tmp_path / "p" / "local", "notes/x.md")
    dev = dev_worktree(tmp_path)
    merged = subprocess.run([sys.executable, "-m", "repokit", "safe-merge", "private"], cwd=dev,
                            capture_output=True, text=True, stdin=subprocess.DEVNULL,
                            encoding="utf-8", errors="replace")
    assert merged.returncode == 0, merged.stdout + merged.stderr
    assert "notes/x.md" in git(dev, "diff", "--cached", "--name-only").stdout, "the precondition: it is staged"
    result = git(dev, "commit", "-q", "-m", "merge private")
    assert result.returncode != 0, "notes/x.md was committed on dev"
    assert "notes/x.md" in result.stdout + result.stderr
    assert "notes/x.md" not in git(dev, "ls-tree", "-r", "--name-only", "HEAD").stdout
    # the refusal says how to commit it anyway, on purpose (djdarcy, 2026-11-01)
    said = result.stdout + result.stderr  # git passes a hook's output on stderr
    assert ".repokit-allowlist" in said and "--no-verify" in said, said


@pytest.mark.integration
def test_no_common_hook_honors_the_allowlist(tmp_path, monkeypatch, capfd):
    """A path listed in .repokit-allowlist is deliberately public: the fallback
    hook lets it through, as git-repokit-common's hook does."""
    code, out = create(tmp_path, monkeypatch, capfd, "--no-common", *PRIVATE_NOTES)
    assert code == 0, out
    root = tmp_path / "p"
    (root / "notes" / "x.md").write_text("now public\n", encoding="utf-8")
    assert git(root, "add", "-f", "notes/x.md").returncode == 0
    refused = git(root, "commit", "-q", "-m", "not yet allowed")
    assert refused.returncode != 0, "the precondition: notes/x.md is refused without the allowlist"
    (root / ".repokit-allowlist").write_text("# deliberately public\n\nnotes/x.md\n", encoding="utf-8")
    allowed = git(root, "commit", "-q", "-m", "allowed")
    assert allowed.returncode == 0, allowed.stdout + allowed.stderr
    assert "notes/x.md" in git(root, "ls-tree", "-r", "--name-only", "HEAD").stdout


@pytest.mark.integration
def test_no_common_hook_refuses_a_forced_private_file_on_a_github_flow_feature_branch(tmp_path, monkeypatch, capfd):
    """Measured: git-repokit's own hook treated feature/* as private too."""
    code, out = create(tmp_path, monkeypatch, capfd, "--branch-strategy", "github-flow", "--no-common")
    assert code == 0, out
    public = tmp_path / "p" / "github"
    assert git(public, "switch", "-q", "-c", "feature/login").returncode == 0
    (public / "convos").mkdir(exist_ok=True)
    (public / "convos" / "x.md").write_text("a private conversation\n", encoding="utf-8")
    assert git(public, "add", "-f", "convos/x.md").returncode == 0
    result = git(public, "commit", "-q", "-m", "forced private file")
    assert result.returncode != 0, "convos/x.md was committed on feature/login"
