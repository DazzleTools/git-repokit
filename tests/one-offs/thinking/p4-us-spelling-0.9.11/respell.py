"""0.9.11: respell git-repokit in US English: licence -> license, colour -> color.

djdarcy, 2026-10-25: "Why'd you spell everything as licence rather than
license?" The British forms crept in from 0.7.1 on; the house's other
projects, and every flag, key and file name, say license.

What changes: every git-tracked or new (not ignored) text file outside the
records -- docs, CHANGELOG, code, tests, comments, messages. Kept as they
are: the vault (private/), the one-off and mutation records (tests/one-offs/,
tests/mutation/: records of their moment), the license texts (their bytes are
fingerprinted in LICENSES.md), and the two checklist file names that contain
the word (renaming them would break every reference). All-caps LICENCE is a
real license file name and is kept.

    python respell.py          # dry run: counts per file
    python respell.py --write  # apply
"""
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
# scripts/repokit-common/ is git-repokit-common, vendored: it changes only
# through its own update script, never by hand here
SKIP_PREFIXES = ("private/", "tests/one-offs/", "tests/mutation/", ".pytest_cache/",
                 "scripts/repokit-common/")
SKIP_FILES = {"LICENSE"}
KEEP = ["template-parity-licence-and-extras", "real-owner-licence-and-commands"]
LICENCE = re.compile(r"(?<![A-Z])([Ll])icenc(e|es|ed|ing)(?![a-z])")
COLOUR = re.compile(r"([Cc])olour(s|ed|ing)?(?![a-z])")


def files():
    out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=REPO,
                         capture_output=True, text=True, check=True).stdout.splitlines()
    for rel in out:
        if rel.startswith(SKIP_PREFIXES) or rel in SKIP_FILES:
            continue
        if rel.startswith("repokit/licenses/") and rel.endswith(".txt"):
            continue  # the license texts, fingerprinted byte for byte
        path = REPO / rel
        if path.is_file():
            yield rel, path


def respell(text):
    for i, name in enumerate(KEEP):
        text = text.replace(name, f"\x00KEEP{i}\x00")
    text, n1 = LICENCE.subn(lambda m: f"{m.group(1)}icens{m.group(2)}", text)
    text, n2 = COLOUR.subn(lambda m: f"{m.group(1)}olor{m.group(2) or ''}", text)
    for i, name in enumerate(KEEP):
        text = text.replace(f"\x00KEEP{i}\x00", name)
    return text, n1, n2


def main(write):
    total = [0, 0]
    for rel, path in files():
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        new, n1, n2 = respell(text)
        if n1 or n2:
            total[0] += n1
            total[1] += n2
            print(f"{n1:4} licence {n2:4} colour  {rel}")
            if write:
                path.write_bytes(new.encode("utf-8"))  # line endings as they were
    print(f"total: {total[0]} licence, {total[1]} colour" + ("" if write else "  (dry run)"))


if __name__ == "__main__":
    main("--write" in sys.argv)
