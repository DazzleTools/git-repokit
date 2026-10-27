"""0.9.12 red-green audit: revert each unit's BEHAVIOUR (never its API), run
only its tests, restore, and confirm the file is byte-identical afterwards.

Each revert is a text replacement in repokit/repo_manager.py that asserts its
anchor matched exactly once; the original is copied aside first and copied
back in a finally block, then its sha256 is compared. The tests involved work
only under tmp_path (Safety Rule 1b).

    python redgreen.py
"""
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
TARGET = REPO / "repokit" / "repo_manager.py"
TESTS = "tests/test_private_branch_create.py"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def head_function(name):
    """The body of `name` as committed at HEAD (the pre-0.9.12 behaviour)."""
    src = subprocess.run(["git", "show", "HEAD:repokit/repo_manager.py"], cwd=REPO,
                         capture_output=True, text=True, encoding="utf-8").stdout
    m = re.search(rf"(    def {name}\(.*?)(?=\n    def |\Z)", src, re.S)
    assert m, name
    return m.group(1)


def current_function(text, name):
    m = re.search(rf"(    def {name}\(.*?)(?=\n    def |\Z)", text, re.S)
    assert m, name
    return m.group(1)


def replace_once(text, old, new):
    n = text.count(old)
    assert n == 1, f"anchor matched {n} times: {old[:70]!r}"
    return text.replace(old, new)


def revert_u2(t):
    return replace_once(t, 'source_ref = f"refs/heads/{source_branch}"', "source_ref = source_branch")


def revert_u3(t):
    return t.replace(current_function(t, "_cleanup_sensitive_files"), head_function("_cleanup_sensitive_files"))


def revert_u4(t):
    t = replace_once(t, "        # No <name>/github is made ahead of time (0.9.12): `git worktree add`\n",
                     "        if self.github_root:\n            os.makedirs(self.github_root, exist_ok=True)\n"
                     "        # No <name>/github is made ahead of time (0.9.12): `git worktree add`\n")
    return replace_once(t, '        out = self.run_git(["worktree", "list", "--porcelain"], cwd=self.repo_root, check=False) or ""\n',
                        '        return os.path.join(self.project_root, "github")  # REDGREEN-REVERT\n'
                        '        out = self.run_git(["worktree", "list", "--porcelain"], cwd=self.repo_root, check=False) or ""\n')


def revert_u5(t):
    return replace_once(t, '            raise RuntimeError(f"public branches not built: {\', \'.join(failed)}")',
                        '            pass  # REDGREEN-REVERT')


def revert_u6(t):
    return replace_once(t, '        result = subprocess.run(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{name}"],',
                        '        listing = subprocess.run(["git", "branch", "--list"], cwd=repo, capture_output=True, text=True).stdout\n'
                        '        return any(name in b.strip() for b in listing.splitlines())  # REDGREEN-REVERT\n'
                        '        result = subprocess.run(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{name}"],')


ARMS = [
    ("U2 refs/heads", revert_u2, "less_its_private or nothing_under"),
    ("U3 index-only cleanup", revert_u3, "survive"),
    ("U4 real worktree only", revert_u4, "another_repository"),
    ("U5 failures fail", revert_u5, "cannot_be_built"),
    ("U6 exact names", revert_u6, "whole_names"),
]


def run(selector):
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", TESTS, "-k", selector,
                        "--tb=line", "-rA"], cwd=REPO, capture_output=True, text=True)
    lines = [l for l in r.stdout.splitlines() if l.startswith(("PASSED", "FAILED", "ERROR")) or "Error" in l[:200]]
    return lines


def main():
    original = TARGET.read_text(encoding="utf-8")
    before = sha(TARGET)
    aside = Path(tempfile.mkdtemp(prefix="rk0912-rg-")) / "repo_manager.py"
    shutil.copy2(TARGET, aside)
    report = []
    try:
        for name, revert, selector in ARMS:
            TARGET.write_text(revert(original), encoding="utf-8")
            red = run(selector)
            shutil.copy2(aside, TARGET)
            assert sha(TARGET) == before, "restore failed"
            green = run(selector)
            report.append((name, red, green))
    finally:
        shutil.copy2(aside, TARGET)
    assert sha(TARGET) == before and "REDGREEN-REVERT" not in TARGET.read_text(encoding="utf-8")
    for name, red, green in report:
        print(f"\n== {name}\n  reverted:")
        for l in red:
            print("    " + l[:190])
        print("  restored:")
        for l in green:
            print("    " + l[:190])
    print(f"\nrestored byte-identical: {sha(TARGET) == before}")


if __name__ == "__main__":
    main()
