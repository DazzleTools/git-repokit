"""0.9.12 measure, part 3: does a create reach into a repository ABOVE it?

`_setup_github_integration` runs `git status` / `git add .github` / `git
commit` with cwd = <name>/github. When that folder is not a worktree (the
`minimal` strategy; or `--branch-dir-main` naming another folder), git walks up
to the nearest enclosing repository. The question: does a create made inside
an ordinary repository stage or commit anything in that parent?

A DUMMY parent repository only, made here, with one commit; its HEAD and index
are recorded before the create and compared after. Shipped code only (the
`--` fix does not touch this path).

    python probe_parent_repo.py
"""
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe import env_for, git  # noqa: E402

tmp = Path(tempfile.mkdtemp(prefix="rk0912-parent-"))
home = tmp / "home"
home.mkdir()
env = env_for(home)
parent = tmp / "parent"
parent.mkdir()
git(["init", "-q", "-b", "main"], parent, env)
(parent / "keep.txt").write_text("parent's own file\n")
git(["add", "keep.txt"], parent, env)
git(["commit", "-qm", "parent repo"], parent, env)
_, head0 = git(["rev-parse", "HEAD"], parent, env)

results = {}
for strategy, extra in (("minimal", []), ("simple", ["--branch-dir-main", "public"])):
    work = parent / f"work-{strategy}"
    work.mkdir()
    cmd = [sys.executable, "-m", "repokit.cli", "-vv", "create", "p", "--branch-strategy", strategy,
           "--license", "mit", "--no-push", "--user-name", "T", "--user-email", "t@example.com"] + extra
    r = subprocess.run(cmd, cwd=work, env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    log = r.stdout + r.stderr
    (Path(__file__).resolve().parent / "out" / f"parent-{strategy}.log").write_text(log, encoding="utf-8")
    gh_lines = [l for l in log.splitlines() if "github" in l.lower() and ("Running: git" in l or "GitHub" in l)]
    _, staged = git(["diff", "--cached", "--name-only"], parent, env)
    _, head = git(["rev-parse", "HEAD"], parent, env)
    _, log1 = git(["log", "--format=%h %s", "-3"], parent, env)
    results[strategy] = {"exit": r.returncode, "parent_staged": staged.splitlines(),
                         "parent_head_moved": head != head0, "parent_log": log1.splitlines(),
                         "github_git_lines": gh_lines[:12]}

print("scratch", tmp)
for s, v in results.items():
    print(f"\n{s}: exit={v['exit']} parent HEAD moved={v['parent_head_moved']}")
    print(f"   parent staged ({len(v['parent_staged'])}): {v['parent_staged'][:8]}")
    print(f"   parent log: {v['parent_log']}")
    for l in v["github_git_lines"]:
        print("   |", l[:200])
