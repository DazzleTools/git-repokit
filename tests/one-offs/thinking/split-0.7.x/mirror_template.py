"""Build what git-repokit-template's setup workflow would produce, locally.

The template repository (C:/code/git-repokit-template) turns itself into a
project through .github/workflows/setup-from-template.yml on the first push of
a repository created from it. This script replays that workflow on a local
checkout so `repokit create <name> --language python` can be compared with it
file for file -- djdarcy's test for the python layer: "it should perfectly
mirror the git-repokit-template and how we create a project from that."

    python mirror_template.py <dest-dir> [--name demo] [--template C:/code/git-repokit-template]

Writes <dest-dir>/<name>/ and prints the file list. Nothing in the template
checkout is touched. Compare with:

    diff <(cd <dest>/<name> && git ls-files | sort) <(cd <created>/<name> && git ls-files | sort)
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

SKIP_DIRS = {".git", "private"}
SKIP_FILES = {".github/workflows/setup-from-template.yml", "pyproject.toml.comfyui"}


def heredocs(workflow_text: str) -> dict[str, str]:
    """The three files the workflow writes with heredocs, by target name."""
    out: dict[str, str] = {}
    pattern = re.compile(
        r'cat > "\$PACKAGE_NAME/(?P<name>[^"]+)" << \'?PYEOF\'?\n(?P<body>.*?)\n\s*PYEOF',
        re.S,
    )
    for m in pattern.finditer(workflow_text):
        body = "\n".join(line[10:] if line.startswith(" " * 10) else line
                         for line in m.group("body").split("\n"))
        out[m.group("name")] = body + "\n"
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dest")
    ap.add_argument("--name", default="demo")
    ap.add_argument("--template", default="C:/code/git-repokit-template")
    ap.add_argument("--org", default="DazzleTools")
    ap.add_argument("--user", default="djdarcy")
    a = ap.parse_args(argv)

    src = Path(a.template)
    dst = Path(a.dest) / a.name
    if dst.exists():
        print(f"refusing: {dst} exists", file=sys.stderr)
        return 2

    values = {
        "PROJECT_NAME": a.name,
        "PACKAGE_NAME": a.name.replace("-", "_"),
        "GITHUB_ORG": a.org,
        "GITHUB_USER": a.user,
        "AUTHOR_EMAIL": f"{a.user}@users.noreply.github.com",
        "CLI_COMMAND": a.name.replace("_", "-"),
        "DESCRIPTION": "A new project created from git-repokit-template",
    }

    def fill(text: str) -> str:
        for key, val in values.items():
            text = text.replace(f"${key}", val)
        return text

    workflow = (src / ".github/workflows/setup-from-template.yml").read_text(encoding="utf-8")

    for path in sorted(src.rglob("*")):
        rel = path.relative_to(src)
        if any(part in SKIP_DIRS for part in rel.parts) or not path.is_file():
            continue
        rel_posix = rel.as_posix()
        if rel_posix in SKIP_FILES:
            continue
        if rel_posix == "pyproject.toml.pypi":
            rel_posix = "pyproject.toml"
        target = dst / rel_posix
        target.parent.mkdir(parents=True, exist_ok=True)
        data = path.read_bytes()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            target.write_bytes(data)
            continue
        if rel_posix == "README.md":
            # sed '/^---$/,/^```$/d' -- drops the Template Variables section
            lines, out, skipping = text.split("\n"), [], False
            for line in lines:
                if not skipping and line == "---":
                    skipping = True
                    continue
                if skipping:
                    if line == "```":
                        skipping = False
                    continue
                out.append(line)
            text = "\n".join(out)
        target.write_text(fill(text), encoding="utf-8", newline="\n")

    pkg = dst / values["PACKAGE_NAME"]
    pkg.mkdir(exist_ok=True)
    for name, body in heredocs(workflow).items():
        body = body.replace("${PACKAGE_NAME}", values["PACKAGE_NAME"])
        body = body.replace("$PROJECT_NAME", values["PROJECT_NAME"])
        (pkg / name).write_text(body, encoding="utf-8", newline="\n")

    files = sorted(p.relative_to(dst).as_posix() for p in dst.rglob("*") if p.is_file())
    print("\n".join(files))
    print(f"-- {len(files)} files in {dst}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
