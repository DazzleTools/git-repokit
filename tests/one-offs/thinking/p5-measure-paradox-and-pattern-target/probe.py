"""Measure, for the paradox-language / pattern-target design (2026-10-30):

Q1  Which git-repokit-common consumers carry their version in a NON-JSON text
    file beside the version source, and is that copy in step or drifted?
    (Would a generic "pattern" extra-target replace hand edits anywhere?)
Q2  Which consumers declare `languages`, what would the hooks conclude, and
    which are NOT Python projects yet would be treated as Python (the default)?

Read-only: reads files, runs only `git rev-parse --git-common-dir` and
`--show-toplevel`. Uses git-repokit-common's own repokit_config (main) for the
settings lookup and language rules, so the answers follow the tooling.

    python probe.py > results-raw.txt
"""
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path("C:/code")
SKIP_DIRS = {"node_modules", ".git", "site-packages", ".venv", "venv", "__pycache__", "dist", "build"}
spec = importlib.util.spec_from_file_location("rkc", "C:/code/git-repokit-common/repokit_config.py")
rkc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rkc)

VER = r"(\d+\.\d+\.\d+(?:[-.+][0-9A-Za-z.\-]+)?)"
CANDIDATES = [  # (glob at the root or one level down, regex with the version group)
    ("Cargo.toml", re.compile(r'^\s*version\s*=\s*"' + VER + '"', re.M)),
    ("CMakeLists.txt", re.compile(r"project\s*\([^)]*VERSION\s+" + VER, re.S | re.I)),
    ("project.godot", re.compile(r'^config/version\s*=\s*"' + VER + '"', re.M)),
    ("*.csproj", re.compile(r"<(?:Version|AssemblyVersion|FileVersion)>" + VER + "<")),
    ("descriptor.mod", re.compile(r'^version\s*=\s*"' + VER + '"', re.M)),
    ("setup.cfg", re.compile(r"^\s*version\s*=\s*" + VER, re.M)),
    ("setup.py", re.compile(r"""version\s*=\s*['"]""" + VER + """['"]""")),
    ("*.iss", re.compile(r'(?:AppVersion|MyAppVersion)\s*"?\s*=?\s*"?' + VER)),
    ("*.nsi", re.compile(r"(?:VERSION|PRODUCT_VERSION)\s+\"?" + VER)),
]


def git(cwd, *args):
    r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True,
                       env=rkc.sanitized_git_env())
    return r.stdout.strip() if r.returncode == 0 else ""


def walk_consumers():
    """Every folder holding a repokit-common tool copy, up to depth 6."""
    hits = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        depth = Path(dirpath).relative_to(ROOT).parts
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and len(depth) < 6]
        if "repokit_config.py" in filenames or "sync-versions.py" in filenames:
            hits.append(Path(dirpath))
    return hits


def version_of(path):
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return None
    m = re.search(r"__version__\s*=\s*['\"]" + VER, text)
    if m:
        return m.group(1)
    parts = {k: re.search(rf"^{k}\s*=\s*(\d+)", text, re.M) for k in ("MAJOR", "MINOR", "PATCH")}
    if all(parts.values()):
        return ".".join(parts[k].group(1) for k in ("MAJOR", "MINOR", "PATCH"))
    defs = {k: re.search(rf"#define\s+\w*VERSION_{k}\s+(\d+)", text) for k in ("MAJOR", "MINOR", "PATCH")}
    if all(defs.values()):
        return ".".join(defs[k].group(1) for k in ("MAJOR", "MINOR", "PATCH"))
    m = re.search(r"^\s*" + VER + r"\s*$", text, re.M)
    return m.group(1) if m else None


def base(v):
    m = re.match(r"\d+\.\d+\.\d+", v or "")
    return m.group(0) if m else None


def main():
    copies = walk_consumers()
    seen = {}
    for copy in copies:
        if copy.name == "git-repokit-common" and copy.parent == ROOT:
            pass  # repokit-common itself is a consumer of its own tooling; keep it
        top = git(copy, "rev-parse", "--show-toplevel")
        # --path-format=absolute: without it git answers relative to the folder
        # it was run in (a subfolder here), which collapsed different repos
        # onto one wrong key on the first run.
        common = git(copy, "rev-parse", "--path-format=absolute", "--git-common-dir")
        if not top or not common:
            print(f"NOT-A-REPO\t{copy}")
            continue
        key = os.path.normcase(os.path.abspath(common))
        seen.setdefault(key, []).append((Path(top), copy))

    rows = []
    for key, entries in sorted(seen.items()):
        top, copy = sorted(entries, key=lambda e: len(str(e[0])))[0]
        try:
            cfg = rkc.find_config(copy)
            table = rkc.read_table(cfg) if cfg else {}
            proj = rkc.project_root(copy, cfg) if cfg else top
        except Exception as e:  # a malformed config is a finding, not a crash
            rows.append((top, f"CONFIG-ERROR {e}", "", "", "", ""))
            continue
        proj = Path(proj)
        declared = table.get("languages")
        try:
            langs = rkc.languages(table, proj)
        except Exception as e:
            langs = f"ERROR {e}"
        detected = rkc.detect_languages(proj)
        src = table.get("version-source", "")
        src_path = proj / src if src and "$" not in src else None
        if src_path is None:
            for guess in ("version.py", "VERSION", "_version.py"):
                if (proj / guess).is_file():
                    src_path = proj / guess
                    break
            if src_path is None:
                found = [p for p in proj.glob("*/_version.py") if "repokit-common" not in str(p)]
                src_path = found[0] if found else None
        ver = version_of(src_path) if src_path and src_path.is_file() else None
        extras = table.get("extra-targets") or []
        others = []
        for pattern, rx in CANDIDATES:
            for f in list(proj.glob(pattern)) + list(proj.glob("*/" + pattern)):
                if any(p in SKIP_DIRS or p == "repokit-common" for p in f.parts):
                    continue
                try:
                    m = rx.search(f.read_text(encoding="utf-8-sig", errors="replace"))
                except OSError:
                    continue
                if m:
                    state = "in-step" if base(m.group(1)) == base(ver) else "DRIFTED"
                    others.append(f"{f.relative_to(proj).as_posix()}={m.group(1)}({state})")
        python_like = ("python" in detected) or (proj / "pyproject.toml").is_file() and "[project]" in (proj / "pyproject.toml").read_text(errors="replace")
        treated_py = isinstance(langs, list) and "python" in langs and declared is None and not detected
        rows.append((proj, f"declared={declared}", f"hooks={langs}", f"detected={detected}",
                     f"version={ver} ({src_path.relative_to(proj).as_posix() if src_path else 'none'})",
                     f"json-extra={len(extras)}", "others=" + ("; ".join(others) or "-"),
                     "TREATED-AS-PYTHON-BY-DEFAULT" if treated_py else ""))

    for r in rows:
        print("\t".join(str(x) for x in r))
    print(f"\ncopies found={len(copies)}  repos (deduped by git common dir)={len(seen)}  rows={len(rows)}")


if __name__ == "__main__":
    sys.exit(main())
