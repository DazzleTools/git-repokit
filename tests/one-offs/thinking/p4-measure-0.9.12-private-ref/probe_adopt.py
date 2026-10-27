"""0.9.12 measure, part 2: does `repokit adopt` lose any of a project's files?

adopt runs on someone's existing project and takes the private-branch layout,
so the question is whether any of the project's own files -- committed,
untracked, or ignored -- disappear or change, with the shipped code and with
the `--` fix. A DUMMY project only, and a full copy of it is taken before
adopt runs (djdarcy: "It sholud be tested against a dummy repo", "Or be making
sure you actually backup things first"); the comparison is against that copy.

The dummy holds what a real project might, including files the sensitive
patterns match: .env, *.log, logs/, a .bak, editor settings, a notes file.
Variants: with and without a `private/` folder (the ambiguity needs one).

    python probe_adopt.py <scratch folder probe.py printed>   # uses its pkg/
"""
import filecmp
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe import env_for, git, private_paths  # noqa: E402

FILES = {
    "main.py": "print('hello')\n",
    "README.md": "# demo\n",
    "requirements.txt": "requests\n",
    "src/util.py": "X = 1\n",
    ".env": "SECRET=do-not-lose\n",              # untracked, matches .env*
    "app.log": "a log line\n",                    # untracked, matches *.log
    "logs/run.log": "run\n",                      # untracked, matches logs/*
    "config.bak": "old config\n",                 # untracked, matches *.bak
    ".vscode/settings.json": "{}\n",             # untracked editor settings
    "notes/todo.md": "my notes\n",               # untracked, no pattern
}
COMMITTED = ["main.py", "README.md", "requirements.txt", "src/util.py"]


def make_dummy(root, env, with_private):
    root.mkdir(parents=True)
    git(["init", "-q", "-b", "main"], root, env)
    for rel, text in FILES.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    if with_private:
        (root / "private").mkdir()
        (root / "private" / "design.md").write_text("private design\n", encoding="utf-8")
    git(["add", "--"] + COMMITTED, root, env)
    git(["commit", "-qm", "the project as it was"], root, env)
    return root


def walk(root):
    return sorted(str(p.relative_to(root)).replace("\\", "/") for p in root.rglob("*")
                  if p.is_file() and ".git" not in p.relative_to(root).parts)


def run(tmp, label, pkg_root, with_private):
    tag = f"{label}-{'with' if with_private else 'no'}-private"
    home = tmp / f"home-{tag}"
    home.mkdir()
    env = env_for(home)
    if pkg_root:
        env["PYTHONPATH"] = str(pkg_root)
    proj = make_dummy(tmp / tag / "proj", env, with_private)
    backup = tmp / tag / "proj.backup"
    shutil.copytree(proj, backup)                  # the backup, before anything runs
    cmd = [sys.executable, "-m", "repokit.cli", "adopt", ".", "--no-push",
           "--user-name", "T", "--user-email", "t@example.com"]
    # adopt asks "Continue with adoption? Changes should be committed first"
    # when untracked files exist; a real person with a stray .env answers yes,
    # so the probe does too (this is a dummy, and its backup is already taken)
    r = subprocess.run(cmd, cwd=proj, env=env, capture_output=True, text=True, input="y\n")
    log = r.stdout + r.stderr
    (Path(__file__).resolve().parent / "out" / f"adopt-{tag}.log").write_text(log, encoding="utf-8")
    before = walk(backup)
    after = set(walk(proj))
    lost = [f for f in before if f not in after]
    changed = [f for f in before if f in after and not filecmp.cmp(backup / f, proj / f, shallow=False)]
    _, branches = git(["for-each-ref", "--format=%(refname:short)", "refs/heads"], proj, env)
    trees = {}
    for b in branches.split():
        _, names = git(["ls-tree", "-r", "--name-only", f"refs/heads/{b}"], proj, env)
        names = names.splitlines()
        trees[b] = {"files": len(names), "private": private_paths(names),
                    "secrets": [n for n in names if n in (".env", "app.log", "logs/run.log", "config.bak")]}
    return tag, {"exit": r.returncode, "ambiguous": log.count("ambiguous argument"),
                 "errors": sum(1 for l in log.splitlines() if " - ERROR - " in l),
                 "lost": lost, "changed": changed, "branches": trees,
                 "siblings": sorted(x.name for x in (tmp / tag).iterdir())}


def main():
    pkg = Path(sys.argv[1]) / "pkg"
    assert (pkg / "repokit").is_dir(), "run probe.py first"
    tmp = Path(tempfile.mkdtemp(prefix="rk0912-adopt-"))
    report = {"scratch": str(tmp), "runs": {}}
    for label, root in (("shipped", None), ("patched", pkg)):
        for wp in (False, True):
            tag, res = run(tmp, label, root, wp)
            report["runs"][tag] = res
    out = Path(__file__).resolve().parent / "out" / "report-adopt.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("scratch", tmp)
    for tag, v in report["runs"].items():
        print(f"\n{tag}: exit={v['exit']} ambiguous={v['ambiguous']} ERROR={v['errors']} siblings={v['siblings']}")
        print(f"   LOST from the project folder: {v['lost']}")
        print(f"   CHANGED: {v['changed']}")
        for b, d in v["branches"].items():
            print(f"   {b:10} files={d['files']:3} private={d['private']} secrets-in-tree={d['secrets']}")


if __name__ == "__main__":
    main()
