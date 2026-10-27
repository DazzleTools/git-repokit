"""0.9.12 measure: the ambiguous `private` ref, and what reaches the public branches.

Question (the decision it feeds): which git calls break when a branch and a
folder share the name `private`, and -- once the reset succeeds -- does any
private file reach main/dev/staging/test/live? Decides the fix's shape and
whether the never-run cleaning step after the reset is safe to switch on.

Method:
  A. Known-answer: a tiny repo with branch `private` and folder `private/`;
     run each candidate git command, record exit code and the error.
  B. Real creates of every private-branch strategy, twice: the checkout's code
     (as shipped in 0.9.11) and a scratch COPY of the package with `--` added
     after the two `reset --hard <branch>` calls. The checkout is never edited.
     HOME/USERPROFILE isolated, commits unsigned, stdin closed.
  C. For each branch, list the tree's private paths. Positive control: the
     private branch must show private paths, or the classifier is broken.

    python probe.py            # writes out/ beside this file
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = HERE / "out"
STRATEGIES = ["standard", "simple", "gitflow", "github-flow", "minimal"]
PRIVATE_PATTERNS = [r"^private/", r"^CLAUDE\.md$", r"^convos/", r"^logs/", r"^revisions/", r"(^|/)\.env$"]


def env_for(home):
    e = dict(os.environ)
    e.update({"HOME": str(home), "USERPROFILE": str(home), "GIT_CONFIG_COUNT": "2",
              "GIT_CONFIG_KEY_0": "commit.gpgsign", "GIT_CONFIG_VALUE_0": "false",
              "GIT_CONFIG_KEY_1": "tag.gpgsign", "GIT_CONFIG_VALUE_1": "false",
              "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.com",
              "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.com",
              "PYTHONDONTWRITEBYTECODE": "1", "REPOKIT_LICENSE": "mit"})
    e.pop("PYTHONPATH", None)
    return e


def git(args, cwd, env):
    r = subprocess.run(["git"] + args, cwd=cwd, env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return r.returncode, (r.stdout + r.stderr).strip()


def private_paths(names):
    return [n for n in names if any(re.search(p, n) for p in PRIVATE_PATTERNS)]


def part_a(tmp):
    """Which commands fail when branch `private` and folder `private/` coexist."""
    env = env_for(tmp / "home")
    (tmp / "home").mkdir()
    r = tmp / "ka"
    r.mkdir()
    git(["init", "-q", "-b", "main"], r, env)
    (r / "a.txt").write_text("a\n")
    git(["add", "-A"], r, env)
    git(["commit", "-qm", "a"], r, env)
    git(["branch", "private"], r, env)
    (r / "private").mkdir()
    (r / "private" / "n.md").write_text("n\n")  # untracked folder of the same name
    cmds = [["rev-parse", "private"], ["rev-parse", "private", "--"], ["rev-parse", "refs/heads/private"],
            ["log", "-1", "--format=%h", "private"], ["log", "-1", "--format=%h", "private", "--"],
            ["ls-tree", "private"], ["merge-base", "main", "private"],
            ["checkout", "-q", "private"], ["checkout", "-q", "main"],
            ["reset", "--hard", "private"], ["reset", "--hard", "private", "--"],
            ["reset", "--hard", "refs/heads/private"]]
    rows = []
    for c in cmds:
        code, out = git(c, r, env)
        rows.append({"cmd": "git " + " ".join(c), "exit": code,
                     "ambiguous": "ambiguous argument" in out, "out": out.splitlines()[-1] if out else ""})
    return rows


def patched_package(tmp):
    """A copy of repokit/ with `--` after the two `reset --hard <branch>` calls."""
    dst = tmp / "pkg"
    # Skip only bytecode and the top-level editor folder: the layer templates
    # hold .vscode/launch.json files of their own (an earlier run of this probe
    # skipped every .vscode folder and lost them -- a method error, caught by
    # the private branch's file count differing between the two runs)
    def ignore(dirpath, names):
        top = Path(dirpath).resolve() == (REPO / "repokit").resolve()
        return [n for n in names if n == "__pycache__" or (top and n == ".vscode")]
    shutil.copytree(REPO / "repokit", dst / "repokit", ignore=ignore)
    p = dst / "repokit" / "repo_manager.py"
    t = p.read_text(encoding="utf-8")
    a = t.count('["reset", "--hard", source_branch]')
    b = t.count('["reset", "--hard", private_branch]')
    t = t.replace('["reset", "--hard", source_branch]', '["reset", "--hard", source_branch, "--"]')
    t = t.replace('["reset", "--hard", private_branch]', '["reset", "--hard", private_branch, "--"]')
    p.write_text(t, encoding="utf-8")
    return dst, {"source_branch": a, "private_branch": b}


def create(tmp, label, strategy, pkg_root):
    home = tmp / f"home-{label}-{strategy}"
    work = tmp / f"w-{label}-{strategy}"
    home.mkdir()
    work.mkdir()
    env = env_for(home)
    if pkg_root:
        env["PYTHONPATH"] = str(pkg_root)
    cmd = [sys.executable, "-m", "repokit.cli", "create", "p", "--branch-strategy", strategy,
           "--language", "python", "--license", "mit", "--no-push",
           "--user-name", "T", "--user-email", "t@example.com"]
    r = subprocess.run(cmd, cwd=work, env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    log = r.stdout + r.stderr
    (OUT / f"{label}-{strategy}.log").write_text(log, encoding="utf-8")
    proj = work / "p"
    local = proj / "local" if (proj / "local").is_dir() else proj
    code, branches = git(["for-each-ref", "--format=%(refname:short)", "refs/heads"], local, env)
    result = {"exit": r.returncode, "ambiguous_lines": log.count("ambiguous argument"),
              "error_lines": sum(1 for l in log.splitlines() if " - ERROR - " in l),
              "folders": sorted(x.name for x in proj.iterdir() if x.is_dir()), "branches": {}}
    for b in branches.split():
        _, names = git(["ls-tree", "-r", "--name-only", f"refs/heads/{b}"], local, env)
        names = names.splitlines()
        result["branches"][b] = {"files": len(names), "private": private_paths(names)}
    _, wt = git(["worktree", "list", "--porcelain"], local, env)
    result["worktrees"] = [l.split(" ", 1)[1] for l in wt.splitlines() if l.startswith("worktree ")]
    gh = proj / "github"
    result["github_folder"] = None if not gh.is_dir() else sorted(x.name for x in gh.iterdir())
    return result


def main():
    OUT.mkdir(exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="rk0912-"))
    report = {"scratch": str(tmp), "part_a": part_a(tmp)}
    pkg, counts = patched_package(tmp)
    report["patch_counts"] = counts
    report["creates"] = {}
    for label, root in (("shipped", None), ("patched", pkg)):
        for s in STRATEGIES:
            report["creates"][f"{label}/{s}"] = create(tmp, label, s, root)
    (OUT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=1)[:200000])


if __name__ == "__main__":
    main()
