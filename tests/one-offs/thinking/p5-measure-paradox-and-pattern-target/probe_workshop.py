"""Two checks against the installed CK3 Workshop mods (read-only; nothing is written).

A (D0, nesting): what sits at the top level of real Workshop uploads besides the
  game's own folders? Repository files there (.git, README, tests/, scripts/,
  .github/, private/) show that an upload ships whatever the folder holds.
B (D4, the pattern target): the proposed pattern ^version="([^"]*)"$ (multiline)
  on every descriptor.mod: how many lines match (0, 1, 2+), whether it ever
  touches supported_version, and whether an in-memory rewrite to 9.9.9 keeps
  every other byte, the BOM state and the line endings.

    python probe_workshop.py
"""
import re
import sys
from collections import Counter
from pathlib import Path

WS = Path("E:/SteamLibrary/steamapps/workshop/content/1158310")
GAME_DIRS = {"common", "events", "gfx", "gui", "localization", "localisation", "history", "map_data",
             "music", "sound", "fonts", "content_source", "data_binding", "dlc", "tests", "tools"}
GAME_FILES = {"descriptor.mod", "thumbnail.png"}
REPO_LIKE = {".git", ".github", "readme.md", "readme.txt", "readme", "license", "license.md", "license.txt",
             "scripts", "private", ".gitignore", ".gitattributes", ".vscode", "changelog.md", "pyproject.toml"}
PATTERN = re.compile(rb'^version="([^"]*)"\r?$', re.M)


def main():
    if not WS.is_dir():
        print(f"UNREACHABLE {WS}")
        return 2
    mods = sorted(p for p in WS.iterdir() if p.is_dir())
    extra = Counter()
    repo_like_mods = {}
    match_counts = Counter()
    rewrite_ok = 0
    rewrite_bad = []
    touched_supported = 0
    for m in mods:
        names = {c.name.lower() for c in m.iterdir()}
        odd = sorted(n for n in names if n not in GAME_DIRS and n not in GAME_FILES)
        extra.update(odd)
        rl = sorted(n for n in names if n in REPO_LIKE)
        if rl:
            repo_like_mods[m.name] = rl
        d = m / "descriptor.mod"
        if not d.is_file():
            match_counts["no descriptor"] += 1
            continue
        data = d.read_bytes()
        bom = data.startswith(b"\xef\xbb\xbf")
        body = data[3:] if bom else data
        found = PATTERN.findall(body)
        match_counts[min(len(found), 2)] += 1
        if not found:
            continue
        m1 = PATTERN.search(body)
        new_body = body[: m1.start(1)] + b"9.9.9" + body[m1.end(1):]
        new = (b"\xef\xbb\xbf" if bom else b"") + new_body
        # every byte outside the version value is unchanged; supported_version untouched
        before_after_ok = (new[: len(data) - len(body) + m1.start(1)] == data[: len(data) - len(body) + m1.start(1)]
                           and new_body[m1.start(1) + 5:] == body[m1.end(1):])
        sv_before = re.findall(rb'supported_version="([^"]*)"', body)
        sv_after = re.findall(rb'supported_version="([^"]*)"', new_body)
        if sv_before != sv_after:
            touched_supported += 1
        crlf_same = body.count(b"\r\n") == new_body.count(b"\r\n")
        if before_after_ok and crlf_same and new.startswith(b"\xef\xbb\xbf") == bom:
            rewrite_ok += 1
        else:
            rewrite_bad.append(m.name)

    print(f"A. mods={len(mods)}")
    print(f"   top-level entries outside the game's folders: {dict(extra.most_common(15))}")
    print(f"   mods with repository-like entries: {len(repo_like_mods)}")
    for k, v in list(repo_like_mods.items())[:10]:
        print(f"     {k}: {v}")
    print(f"B. descriptor.mod matches: {dict(match_counts)}   (0, 1, 2 = two or more)")
    print(f"   rewrites byte-exact (BOM state, CRLF count, every other byte): {rewrite_ok}; not: {rewrite_bad}")
    print(f"   supported_version changed by the rewrite: {touched_supported}")
    total = sum(match_counts.values())
    print(f"   reconcile: {total} = {len(mods)} mods")


if __name__ == "__main__":
    sys.exit(main())
