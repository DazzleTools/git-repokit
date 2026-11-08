"""L2 probe (refactor-advisor, 0.10.3): in a `minimal` project, does
`repokit setup-guardrails` run on main write revisions/ into the shared
.git/info/exclude, so a plain `git add .` on private skips it afterwards?

Prediction: yes -- check-ignore names info/exclude for revisions/x after the
switch back to private. Control: before setup-guardrails, revisions/x is not ignored.
"""
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ac_checks import HERE, NEW, create, env  # noqa: E402

RUN = HERE / "run-l2"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def sh(cwd, *args):
    r = subprocess.run(list(args), cwd=cwd, env=env(NEW), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
    return r.returncode, (r.stdout + r.stderr).strip()


if RUN.exists():
    shutil.rmtree(RUN, onerror=lambda f, p, e: (__import__("os").chmod(p, 0o700), f(p)))
code, out = create(RUN, NEW, "m", "--branch-strategy", "minimal", "--language", "python")
local = RUN / "m" / "local"
print("create exit", code)
(local / "revisions").mkdir(exist_ok=True)
(local / "revisions" / "x.md").write_text("old\n", encoding="utf-8")
print("control, on private:", sh(local, "git", "check-ignore", "-v", "revisions/x.md"))
print("checkout main:", sh(local, "git", "checkout", "-q", "main")[0])
rc, out = sh(local, sys.executable, "-m", "repokit", "setup-guardrails")
print("setup-guardrails on main: rc", rc, "|", out.splitlines()[-1] if out else "")
print("checkout private:", sh(local, "git", "checkout", "-q", "private")[0])
(local / "revisions").mkdir(exist_ok=True)
(local / "revisions" / "x.md").write_text("old\n", encoding="utf-8")
print("after, on private:", sh(local, "git", "check-ignore", "-v", "revisions/x.md"))
sh(local, "git", "add", ".")
print("plain add staged revisions/x.md:", "revisions/x.md" in sh(local, "git", "diff", "--cached", "--name-only")[1].split())
