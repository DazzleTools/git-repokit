"""0.10.3 acceptance checks AC3, AC4, AC5 as real creates, outside the repository.

Predictions (the design's table):
  AC3  create x --branch-strategy simple: .repokit.json private_mode nested-branch;
       private/.git present; convos/ revisions/ tracked on private once used; public trees clean
  AC4  create x (main-only): identical to 0.10.2 apart from the dependency
       (compared: the file list and each file's bytes, minus the version/date lines)
  AC5  create x --private-mode branch (main-only): refused, naming the fixes; nothing written
"""
import filecmp
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "run"
NEW = "C:/code/git-repokit"
OLD = HERE / "repokit-0.10.2"
COMMON = "C:/code/git-repokit-common"


def env(src):
    e = dict(os.environ)
    e.update({"PYTHONPATH": str(src), "PYTHONDONTWRITEBYTECODE": "1", "GIT_CEILING_DIRECTORIES": str(HERE),
              "GIT_CONFIG_COUNT": "2", "GIT_CONFIG_KEY_0": "commit.gpgsign", "GIT_CONFIG_VALUE_0": "false",
              "GIT_CONFIG_KEY_1": "tag.gpgsign", "GIT_CONFIG_VALUE_1": "false",
              "REPOKIT_COMMON_SOURCE": COMMON, "GITHUB_TOKEN": "", "GH_TOKEN": "", "PYTHONIOENCODING": "utf-8",
              "HOME": str(HERE / "home"), "USERPROFILE": str(HERE / "home")})
    return e


def create(where, src, name, *args):
    where.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([sys.executable, "-m", "repokit", "create", name, "--license", "mit", "--no-push",
                        "--user-name", "T", "--user-email", "t@example.com", *args],
                       cwd=where, env=env(src), capture_output=True, text=True, encoding="utf-8",
                       errors="replace", stdin=subprocess.DEVNULL)
    return r.returncode, r.stdout + r.stderr


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", stdin=subprocess.DEVNULL, env=env(NEW)).stdout


def files(root):
    out = set()
    for d, dirs, fs in os.walk(root):
        dirs[:] = [x for x in dirs if x != ".git"]
        for f in fs:
            out.add(os.path.relpath(os.path.join(d, f), root).replace("\\", "/"))
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if RUN.exists():
        shutil.rmtree(RUN, onerror=lambda f, p, e: (os.chmod(p, 0o700), f(p)))
    (HERE / "home").mkdir(exist_ok=True)
    if not OLD.exists():
        OLD.mkdir()
        tar = subprocess.run(["git", "-C", NEW, "archive", "41f35df", "repokit"], capture_output=True).stdout
        subprocess.run(["tar", "-x", "-C", str(OLD)], input=tar)

    print("## AC3 simple -> nested-branch")
    code, out = create(RUN / "ac3", NEW, "x", "--branch-strategy", "simple", "--language", "python")
    local = RUN / "ac3" / "x" / "local"
    rec = json.loads((local / ".repokit.json").read_text(encoding="utf-8")) if code == 0 else {}
    print("  exit", code, "| mode", rec.get("private_mode"), "| exposure", rec.get("private_exposure"))
    print("  private/.git:", (local / "private" / ".git").exists())
    (local / "convos" / "a.md").write_text("talk\n", encoding="utf-8")
    (local / "revisions" / "old.py").write_text("x = 1\n", encoding="utf-8")
    git(local, "add", ".")
    print("  staged by plain add:", git(local, "diff", "--cached", "--name-only").split())
    git(local, "commit", "-q", "-m", "records")
    for ref in ("main", "dev"):
        hist = git(local, "log", "--no-renames", "--format=", "--name-only", ref).split()
        bad = [p for p in hist if p.split("/")[0] in ("convos", "revisions", "logs", "private")]
        print(f"  {ref} history private paths: {bad}")

    print("\n## AC4 main-only: 0.10.3 vs 0.10.2")
    c_new, o_new = create(RUN / "ac4new", NEW, "x", "--language", "python")
    c_old, o_old = create(RUN / "ac4old", OLD, "x", "--language", "python")
    a, b = RUN / "ac4new" / "x", RUN / "ac4old" / "x"
    fa, fb = files(a), files(b)
    print("  exit new/old:", c_new, c_old)
    print("  only in 0.10.3:", sorted(fa - fb))
    print("  only in 0.10.2:", sorted(fb - fa))
    differ = [f for f in sorted(fa & fb) if not filecmp.cmp(a / f, b / f, shallow=False)]
    print("  differing files:", differ)
    for f in differ:
        la = (a / f).read_text(encoding="utf-8", errors="replace").splitlines()
        lb = (b / f).read_text(encoding="utf-8", errors="replace").splitlines()
        diff = [(x, y) for x, y in zip(la, lb) if x != y][:4]
        print(f"    {f}: {len(la)} vs {len(lb)} lines; first differing pairs: {diff}")

    print("\n## AC5 main-only + --private-mode branch")
    code, out = create(RUN / "ac5", NEW, "x", "--private-mode", "branch")
    print("  exit", code, "| folder written:", (RUN / "ac5" / "x").exists())
    print("  message:", [l for l in out.splitlines() if "private-mode" in l][:2])


if __name__ == "__main__":
    main()
