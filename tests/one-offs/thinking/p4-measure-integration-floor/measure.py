"""Where an integration test's ~5 s goes (0.9.5's opening measure).

    python tests/one-offs/thinking/p4-measure-integration-floor/measure.py

Times, three runs each, in a temp HOME with the unsigned git environment:
the interpreter alone, `python -m repokit --version` (imports), a create
with --no-common, a create with repokit-common vendored from the sibling
checkout, and the two `git init`s a create makes. Prints a table.
"""
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ENV = dict(os.environ, GIT_CONFIG_COUNT="2", GIT_CONFIG_KEY_0="commit.gpgsign", GIT_CONFIG_VALUE_0="false",
           GIT_CONFIG_KEY_1="tag.gpgsign", GIT_CONFIG_VALUE_1="false", PYTHONPATH=str(REPO),
           REPOKIT_LICENSE="mit", REPOKIT_COMMON_SOURCE=str(REPO.parent / "git-repokit-common"))


def timed(cmd, cwd):
    t = time.perf_counter()
    subprocess.run(cmd, cwd=cwd, env=ENV, stdin=subprocess.DEVNULL, capture_output=True)
    return time.perf_counter() - t


def main():
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp, "home"); home.mkdir()
        (home / ".gitconfig").write_text("[user]\n\tname = M\n\temail = m@example.invalid\n", encoding="utf-8")
        ENV.update(HOME=str(home), USERPROFILE=str(home))
        cases = [
            ("python -c pass", lambda d, i: [sys.executable, "-c", "pass"]),
            ("python -m repokit --version", lambda d, i: [sys.executable, "-m", "repokit", "--version"]),
            ("create generic --no-common", lambda d, i: [sys.executable, "-m", "repokit", "create", f"g{i}", "--language", "generic", "--no-common", "--no-push"]),
            ("create python --no-common", lambda d, i: [sys.executable, "-m", "repokit", "create", f"p{i}", "--language", "python", "--no-common", "--no-push"]),
            ("create python (vendored)", lambda d, i: [sys.executable, "-m", "repokit", "create", f"v{i}", "--language", "python", "--no-push"]),
            ("git init (x2)", None),
        ]
        for n, (label, make) in enumerate(cases):
            times = []
            for i in range(3):
                d = Path(tmp, f"case{n}-{i}"); d.mkdir()
                if make is None:
                    t = timed(["git", "init", "-q", "a"], d) + timed(["git", "init", "-q", "b"], d)
                else:
                    t = timed(make(d, i), d)
                times.append(t)
            rows.append((label, statistics.median(times)))
    print("| step | median of 3 (s) |\n|---|---|")
    for label, t in rows:
        print(f"| {label} | {t:.2f} |")


if __name__ == "__main__":
    main()
