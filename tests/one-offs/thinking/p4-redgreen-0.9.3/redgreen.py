"""Red-green audit for v0.9.3: revert each behaviour (never the API), run the
tests written for it, restore the file byte for byte, and report.

    python tests/one-offs/thinking/p4-redgreen-0.9.3/redgreen.py

Each reversion is an exact string replacement on a copy held in memory and on
disk beside the script; the file is restored and compared after every run.
"""
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
REVERSIONS = [
    ("A: labels and issues after the push", "repokit/github_create.py",
     '    if "labels" in steps:\n        report += setup.labels()\n    if "issues" in steps:',
     '    if False:\n        report += setup.labels()\n    if False:',
     "tests/test_github_setup.py", "before_the_first_push"),
    ("B: no account check", "repokit/github_create.py",
     "    if configured and login and configured.lower() != login.lower():",
     "    if False:",
     "tests/test_github_setup.py", "another_gh_account"),
    ("C: issues created on a repository that has some", "repokit/github_setup.py",
     "        if existing:\n            # They would not be #1 and #2",
     "        if False:\n            # They would not be #1 and #2",
     "tests/test_github_setup.py", "refused_when"),
    ("D: no pythonpath in the pypi preset", "repokit/templates/layers/archetypes/python/pypi/pyproject.toml",
     'pythonpath = ["."]\n', "\n",
     "tests/test_github_setup.py", "before_the_first_push"),
]


def main() -> int:
    bad = 0
    for label, rel, old, new, tests, k in REVERSIONS:
        path = REPO / rel
        original = path.read_bytes()
        backup = Path(__file__).with_name(path.name + ".orig")
        shutil.copyfile(path, backup)
        text = original.decode("utf-8")
        assert text.count(old) == 1, f"{label}: anchor not unique"
        path.write_bytes(text.replace(old, new).encode("utf-8"))
        try:
            r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", tests, "-k", k],
                               cwd=REPO, capture_output=True, text=True, timeout=600)
        finally:
            path.write_bytes(original)
        restored = path.read_bytes() == original
        backup.unlink()
        last = (r.stdout.strip().splitlines() or ["?"])[-1]
        red = r.returncode != 0
        print(f"{label:52} {'RED' if red else 'green (!)'} -- {last} -- restored={restored}")
        bad += (not red) or (not restored)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
