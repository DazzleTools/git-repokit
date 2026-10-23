"""0.9.0 identity: every file a v0.8.3 create wrote, the 0.9.0 tree writes
byte-identically when asked for no licence and no extras, request by request.
Copied from p3-identity/compare.py (2026-10-20) on 2026-10-23; TAG, REQUESTS
and the .repokit.json keys changed, nothing else.

    python tests/one-offs/thinking/p4-identity/compare.py [--keep]

For each request below, `repokit create` runs twice: from a detached git
worktree of the tag v0.8.3 and from this working tree (which adds
`--license none --no-extras`, flags v0.8.3 did not have), both with
--no-common --no-push into a temp dir. Then the two projects are compared
file by file, ignoring .git/ and, inside .repokit.json, the keys expected to
differ: "version", "created_at", "layers", and the new "license" and
"extras". Anything else that differs is printed and the exit code is 1.

Read-only on the repository: a detached worktree adds no branch and is
removed at the end (--keep leaves it for inspection). Never touches main.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
TAG = "31f2d18"   # v0.8.3's commit; the tag itself is djdarcy's and was not yet made on 2026-10-23
NEW_ONLY = ["--license", "none", "--no-extras"]
REQUESTS = [
    # name, old flags, new flags
    ("py-default", ["--language", "python"], ["--language", "python", *NEW_ONLY]),
    ("py-script", ["--language", "python", "--with", "script"], ["--language", "python", "--with", "script", *NEW_ONLY]),
    ("cpp-default", ["--language", "c-cpp"], ["--language", "c-cpp", *NEW_ONLY]),
    ("js-default", ["--language", "js-ts"], ["--language", "js-ts", *NEW_ONLY]),
    ("js-plugin", ["--language", "js-ts", "--with", "claude-plugin"], ["--language", "js-ts", "--with", "claude-plugin", *NEW_ONLY]),
    ("generic", ["--language", "generic"], ["--language", "generic", *NEW_ONLY]),
]
IGNORE_JSON_KEYS = ('"version"', '"created_at"', '"layers"', '"license"', '"extras"')


def run(cmd, cwd, env=None):
    # stdin closed: `repokit create` asks for a git identity when HOME has none,
    # and an open pipe would make that prompt wait forever (observed 2026-10-20).
    r = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=env, stdin=subprocess.DEVNULL, timeout=300)
    if r.returncode != 0:
        print(f"$ {' '.join(cmd)}\n(exit {r.returncode})\n{r.stdout[-1500:]}{r.stderr[-1500:]}")
    return r.returncode


def create(tree: Path, name: str, flags: list[str], out: Path) -> int:
    env = dict(os.environ, PYTHONPATH=str(tree), HOME=str(out), USERPROFILE=str(out))
    env.pop("REPOKIT_COMMON_SOURCE", None)
    # a git identity in the temp HOME, so both trees' creates take the same path
    (out / ".gitconfig").write_text("[user]\n\tname = Identity Check\n\temail = identity@example.com\n", encoding="utf-8")
    return run([sys.executable, "-m", "repokit", "create", name, *flags, "--no-common", "--no-push"], out, env)


GUID = re.compile(rb"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}")
GUID_FILES = (".sln", ".vcxproj", ".vcxproj.filters")


def normalised_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    for k in ("version", "created_at", "layers", "license", "extras"):
        data.pop(k, None)
    return data


def same_bytes(pa: Path, pb: Path) -> bool:
    da, db = pa.read_bytes(), pb.read_bytes()
    if pa.suffix in GUID_FILES or pa.name.endswith(GUID_FILES):
        # the GUIDs are fresh uuid4 values on every create, in both trees
        da, db = GUID.sub(b"<GUID>", da), GUID.sub(b"<GUID>", db)
    return da == db


def compare(a: Path, b: Path) -> list[str]:
    diffs = []
    files_a = {p.relative_to(a).as_posix() for p in a.rglob("*") if p.is_file() and ".git" not in p.parts}
    files_b = {p.relative_to(b).as_posix() for p in b.rglob("*") if p.is_file() and ".git" not in p.parts}
    for rel in sorted(files_a ^ files_b):
        diffs.append(f"only in {'old' if rel in files_a else 'new'}: {rel}")
    for rel in sorted(files_a & files_b):
        pa, pb = a / rel, b / rel
        if rel == ".repokit.json":
            if normalised_json(pa) != normalised_json(pb):
                diffs.append(f"differs: {rel} (beyond version/created_at/layers)")
        elif not same_bytes(pa, pb):
            da, db = pa.read_bytes(), pb.read_bytes()
            why = " (line endings only)" if da.replace(b"\r\n", b"\n") == db.replace(b"\r\n", b"\n") else ""
            diffs.append(f"differs: {rel}{why}")
    return diffs


def main(argv: list[str]) -> int:
    keep = "--keep" in argv
    work = Path(tempfile.mkdtemp(prefix="p3-identity-"))
    old_tree = work / "old-tree"
    rc = run(["git", "worktree", "add", "--detach", str(old_tree), TAG], REPO)
    if rc:
        return rc
    bad = 0
    try:
        for name, old_flags, new_flags in REQUESTS:
            o, n = work / "old" / name, work / "new" / name
            o.mkdir(parents=True), n.mkdir(parents=True)
            if create(old_tree, name, old_flags, o) or create(REPO, name, new_flags, n):
                print(f"[{name}] a create failed"); bad += 1; continue
            diffs = compare(o / name, n / name)
            print(f"[{name}] {'identical' if not diffs else str(len(diffs)) + ' differences'}")
            for d in diffs:
                print(f"    {d}")
            bad += bool(diffs)
    finally:
        if not keep:
            run(["git", "worktree", "remove", "--force", str(old_tree)], REPO)
            shutil.rmtree(work, ignore_errors=True)
        else:
            print(f"kept: {work}")
    print("RESULT:", "identical for every request" if not bad else f"{bad} request(s) differ")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
