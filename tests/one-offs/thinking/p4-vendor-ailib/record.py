"""Append git-repokit's section to repokit/_vendor/ailib/_VENDORED.md: where
this copy came from (ccs's fork of record, by commit) and every file's sha256
as received (LF-normalised), so a later diff against ccs's copy is exactly
what repokit changed -- the design input for dazzle-ailib (djdarcy, 2026-10-22).

    python tests/one-offs/thinking/p4-vendor-ailib/record.py <ccs-commit>

Run once, right after the `cp -p` copy; refuses if the section exists.
"""
import hashlib
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
AILIB = REPO / "repokit" / "_vendor" / "ailib"
HEADER = "## git-repokit's copy"


def main(commit: str) -> int:
    record = AILIB / "_VENDORED.md"
    text = record.read_text(encoding="utf-8")
    if HEADER in text:
        print("section already there"); return 1
    rows = []
    for p in sorted(q for q in AILIB.rglob("*.py") if "__pycache__" not in q.parts):
        sha = hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        rows.append(f"| `{p.relative_to(AILIB).as_posix()}` | {sha} |")
    section = "\n".join([
        "", "---", "", HEADER, "",
        "git-repokit vendors this library too (0.9.4, for the vault bootstrap's AI door). Its copy was taken on "
        f"2026-10-24 with `cp -p` from ccs's copy of record (`dazzle-claude-config-tool__ccs-ai-pass-1`, commit `{commit}`), "
        "not from wtf-windows: ccs's is the copy being developed, and a diff between the two copies is exactly what "
        "git-repokit needed that ccs did not -- the evidence for the shape of a shared dazzle-ailib.",
        "",
        "The same two rules bind this copy, enforced by git-repokit's `tests/test_vendored_ailib.py`: purity (no import "
        "of repokit, no relative import out of `_vendor/ailib`, none of repokit's or ccs's tokens, the standard library "
        "only) and honesty (a file that differs from the fingerprint below is named in *Changes in git-repokit's copy*).",
        "",
        "| file | sha256 as received from ccs (LF-normalised) |",
        "|---|---|",
        *rows,
        "",
        "### Changes in git-repokit's copy",
        "",
        "- (none yet)",
        "",
    ])
    record.write_text(text.rstrip("\n") + "\n" + section, encoding="utf-8")
    print(f"recorded {len(rows)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
