"""
Group count.py's output by top-level project folder under the root.

Usage: python summarize.py output-YYYY-MM-DD.txt
"""

import collections
import ntpath
import sys

# Path fragments that mark a checkout as a copy, test run, or backup rather than
# a project someone works in.
NOISE = ("test", "tmp", "temp", "backup", "old", "copy", "archive", "demo", "scratch")


def main(path):
    groups = collections.defaultdict(list)
    for line in open(path, encoding="utf-8"):
        if "  private_branch=" not in line:
            continue
        checkout = line.split("  private_branch=")[0]
        parts = checkout.split("\\")
        top = parts[2] if len(parts) > 2 else checkout
        groups[top].append((checkout, line.rstrip()))

    for top, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        working = [c for c, _ in items
                   if not any(n in c.lower().replace(top.lower(), "") for n in NOISE)]
        print(f"{len(items):4d}  {top}  (outside test/backup/copy paths: {len(working)})")
        for c in working[:4]:
            print(f"        {c}")


if __name__ == "__main__":
    main(sys.argv[1])
