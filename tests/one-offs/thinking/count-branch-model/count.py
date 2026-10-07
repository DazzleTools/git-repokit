"""
Count the checkouts that still use git-repokit's 2025 branch model.

Read-only. Walks a root (default C:\\code) for git checkouts and, for each,
lists local and remote branch names; a checkout "uses the branch model" when
it carries a `private` branch, or two or more of dev/staging/test/live.
Also notes which checkouts hold a `.repokit.json` (written by `repokit create`)
and a nested `private/` repository (the two-repo model).

Runs only `git for-each-ref`, never anything that writes. Output: one line per
checkout of interest, then totals. Critical Safety Rule 6 asks for this count
before any compatibility decision about the legacy model.

Usage: python count.py [ROOT] [--max-depth N]
"""

import os
import subprocess
import sys

SKIP_DIRS = {"node_modules", ".venv", "venv", "__pycache__", ".tox", "dist", "build",
             "site-packages", "old_test_runs", "test_runs"}
LEGACY_SET = {"dev", "staging", "test", "live"}


def find_checkouts(root, max_depth):
    root = os.path.abspath(root)
    base_depth = root.rstrip(os.sep).count(os.sep)
    for current, dirs, files in os.walk(root):
        depth = current.rstrip(os.sep).count(os.sep) - base_depth
        if ".git" in dirs or ".git" in files:
            yield current
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and d != ".git" and depth < max_depth]


def branch_names(checkout):
    out = subprocess.run(
        ["git", "-C", checkout, "for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout.split()
    names = set()
    for ref in out:
        if ref.startswith("refs/heads/"):
            names.add(ref[len("refs/heads/"):])
        elif ref.startswith("refs/remotes/"):
            parts = ref.split("/", 3)
            if len(parts) == 4 and parts[3] != "HEAD":
                names.add(parts[3])
    return names


def git_out(checkout, *args):
    return subprocess.run(
        ["git", "-C", checkout, *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout.strip()


def private_activity(checkout):
    """(checked-out branch, last commit date on the private branch or '')."""
    head = git_out(checkout, "rev-parse", "--abbrev-ref", "HEAD")
    last = git_out(checkout, "log", "-1", "--format=%cs", "private", "--")
    return head, last


def is_nested_private(checkout):
    # a checkout that is itself somebody's private/ vault
    return os.path.basename(checkout) == "private"


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    root = args[0] if args else r"C:\code"
    max_depth = 4
    if "--max-depth" in argv:
        max_depth = int(argv[argv.index("--max-depth") + 1])

    rows = []
    for checkout in find_checkouts(root, max_depth):
        if is_nested_private(checkout):
            continue
        names = branch_names(checkout)
        legacy = sorted(names & LEGACY_SET)
        has_private_branch = "private" in names
        uses_model = has_private_branch or len(legacy) >= 2
        head, private_last = private_activity(checkout) if has_private_branch else ("", "")
        rows.append({
            "head": head,
            "private_last": private_last,
            "checkout": checkout,
            "uses_branch_model": uses_model,
            "private_branch": has_private_branch,
            "legacy_branches": legacy,
            "repokit_json": os.path.isfile(os.path.join(checkout, ".repokit.json")),
            "nested_private_repo": os.path.exists(os.path.join(checkout, "private", ".git")),
        })

    users = [r for r in rows if r["uses_branch_model"]]
    for r in users:
        print(f"{r['checkout']}  private_branch={r['private_branch']}  "
              f"legacy={','.join(r['legacy_branches']) or '-'}  "
              f".repokit.json={r['repokit_json']}  nested_private={r['nested_private_repo']}  "
              f"head={r['head'] or '-'}  private_last={r['private_last'] or '-'}")
    print()
    print(f"checkouts scanned: {len(rows)} (root {root}, depth {max_depth}; nested private/ vaults skipped)")
    print(f"using the branch model: {len(users)}")
    print(f"  with a private branch: {sum(r['private_branch'] for r in users)}")
    print(f"  with a .repokit.json: {sum(r['repokit_json'] for r in rows)} (all checkouts)")
    print(f"nested private/ repo (two-repo model): {sum(r['nested_private_repo'] for r in rows)}")
    print(f"both a private branch and a nested private/ repo: "
          f"{sum(r['private_branch'] and r['nested_private_repo'] for r in rows)}")
    print(f"checked out on the private branch now: {sum(r['head'] == 'private' for r in users)}")
    for since in ("2026-01-01", "2026-07-01"):
        print(f"private branch committed to since {since}: "
              f"{sum(bool(r['private_last']) and r['private_last'] >= since for r in users)}")


if __name__ == "__main__":
    main(sys.argv[1:])
