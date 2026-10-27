"""Where does .vscode/launch.json go in a patched standard create?

Runs one verbose create (the patched scratch package from probe.py) in a fresh
throwaway folder and records: the log lines about .vscode, the clean-branch
steps and commits, and the private branch's history with the files each commit
touched. Throwaway repositories only; the checkout is never touched.

    python trace_vscode.py <scratch folder probe.py printed>
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe import env_for, git  # noqa: E402

scratch = Path(sys.argv[1])
pkg = scratch / "pkg"
assert (pkg / "repokit" / "repo_manager.py").is_file(), "run probe.py first"
tmp = Path(tempfile.mkdtemp(prefix="rk0912-trace-"))
home = tmp / "home"
home.mkdir()
env = env_for(home)
env["PYTHONPATH"] = str(pkg)
cmd = [sys.executable, "-m", "repokit.cli", "-vv", "create", "p", "--branch-strategy", "standard",
       "--language", "python", "--license", "mit", "--no-push", "--user-name", "T", "--user-email", "t@example.com"]
r = subprocess.run(cmd, cwd=tmp, env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL)
log = (r.stdout + r.stderr).splitlines()
out = Path(__file__).resolve().parent / "out"
(out / "trace-patched-standard.log").write_text("\n".join(log), encoding="utf-8")
keys = ("vscode", "launch.json", "clean public", "Removing", "Committed", "Initial commit", "worktree", "checkout",
        "Removed", "sensitive")
print(f"exit {r.returncode}; {len(log)} log lines; scratch {tmp}")
for i, line in enumerate(log):
    if any(k.lower() in line.lower() for k in keys):
        print(f"{i:4}: {line[:220]}")
local = tmp / "p" / "local"
print("\nprivate branch history (files per commit):")
_, h = git(["log", "--name-status", "--format=--- %h %s", "refs/heads/private", "--"], local, env)
print(h)
print("\non disk in local/.vscode:", sorted(os.listdir(local / ".vscode")) if (local / ".vscode").is_dir() else "absent")
_, st = git(["status", "--short", "--ignored"], local, env)
print("status --ignored:\n" + st)
