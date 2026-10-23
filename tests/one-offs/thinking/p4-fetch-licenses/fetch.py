"""Fetch the licence catalogue from github/choosealicense.com at ONE pinned
commit, strip each file's YAML front matter, replace the placeholders with
git-repokit's tokens, and write repokit/licenses/<id>.txt plus LICENSES.md
(the record: source commit, title, sha256 as received, sha256 as shipped).

Re-runnable; a bulk transform, so a script (CLAUDE.md: one-offs for sed-class
work). Run from the repository root:
    python tests/one-offs/thinking/p4-fetch-licenses/fetch.py
Network: raw.githubusercontent.com only. 2026-10-23.
"""
import hashlib
import re
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "repokit" / "licenses"
COMMIT = "f66c5dd01866041688edd87f658b6d5ac3304f1b"   # gh-pages head, 2026-10-23 00:0x
RAW = f"https://raw.githubusercontent.com/github/choosealicense.com/{COMMIT}/_licenses/"
IDS = ["0bsd", "agpl-3.0", "apache-2.0", "bsd-2-clause", "bsd-3-clause", "bsl-1.0", "cc-by-4.0",
       "cc-by-sa-4.0", "cc0-1.0", "epl-2.0", "gpl-2.0", "gpl-3.0", "isc", "lgpl-2.1", "lgpl-3.0",
       "mit", "mpl-2.0", "unlicense"]
# placeholder -> token; the Apache appendix uses the long forms
TOKENS = [("[year]", "__RK_YEAR__"), ("[yyyy]", "__RK_YEAR__"),
          ("[fullname]", "__RK_HOLDER__"), ("[name of copyright owner]", "__RK_HOLDER__")]

ALL_RIGHTS = """Copyright (c) __RK_YEAR__ __RK_HOLDER__. All rights reserved.

This software and its source code are the property of the copyright holder.
No permission is granted to use, copy, modify, merge, publish, distribute,
sublicense, or sell copies of the software, in whole or in part, without the
prior written consent of the copyright holder.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
"""


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for lid in IDS:
        raw = urllib.request.urlopen(RAW + lid + ".txt", timeout=30).read()
        text = raw.decode("utf-8")
        m = re.match(r"---\n(.*?)\n---\n", text, re.S)
        if not m:
            print("no front matter:", lid); return 1
        front, body = m.group(1), text[m.end():]
        title = re.search(r"^title:\s*(.+)$", front, re.M).group(1).strip()
        spdx = re.search(r"^spdx-id:\s*(.+)$", front, re.M).group(1).strip()
        body = body.lstrip("\n")
        for old, new in TOKENS:
            body = body.replace(old, new)
        shipped = body.encode("utf-8")
        (OUT / f"{lid}.txt").write_bytes(shipped)
        rows.append((lid, spdx, title, sha(raw), sha(shipped), "__RK_" in body))
    arr = ALL_RIGHTS.encode("utf-8")
    (OUT / "all-rights-reserved.txt").write_bytes(arr)
    rows.append(("all-rights-reserved", "LicenseRef-AllRightsReserved", "All rights reserved (authored here)", "-", sha(arr), True))

    lines = ["# The licence catalogue: where each text came from, and its fingerprint", "",
             f"Source: `github/choosealicense.com`, `_licenses/<id>.txt`, commit `{COMMIT}` (branch gh-pages, fetched 2026-10-23 by `tests/one-offs/thinking/p4-fetch-licenses/fetch.py`). Each file's YAML front matter was stripped and the placeholders `[year]`, `[yyyy]`, `[fullname]`, `[name of copyright owner]` became `__RK_YEAR__` and `__RK_HOLDER__`; nothing else changed. `all-rights-reserved.txt` is authored here, not fetched. The \"or-later\" variants (`gpl-3.0-or-later`, `lgpl-3.0-or-later`, `agpl-3.0-or-later`) are not files: `repokit.licenses` renders them from the base text with a notice line, because the licence text is identical and only the project's notice says \"or later\".",
             "", "`tests/test_licenses.py` checks every shipped file against its shipped sha256; a changed file without a new row here fails.", "",
             "| id | SPDX | title | sha256 as received | sha256 as shipped | tokens |", "|---|---|---|---|---|---|"]
    for lid, spdx, title, rsha, ssha, tok in rows:
        lines.append(f"| {lid} | {spdx} | {title} | {rsha} | {ssha} | {'holder, year' if tok else 'none'} |")
    (OUT / "LICENSES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} files + LICENSES.md to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
