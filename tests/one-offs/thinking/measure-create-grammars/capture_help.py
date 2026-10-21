"""Measure: how do the generators people already use ask for a project TYPE?

Before designing how `repokit create` names a language, a type and a sub-type
(js-ts / web / vite-react; python / script; c-cpp / lib / qt), count how the
tools in daily use do it. This captures each tool's own `--help` text (and a
template listing where the tool has one) into help/<tool>.txt beside this
script, so the comparison table in the analysis cites a file, not a memory.

    python capture_help.py            # captures everything that is installed
    python capture_help.py --offline  # skips the npm ones (they download a package)

Read-only: nothing is created, no project is generated. The npm entries run
`npx <create-package>@latest --help`, which downloads the package into npm's
cache; that is the only network use, and --offline skips it.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "help"

# tool -> (needs, [commands]); each command's output is appended to help/<tool>.txt
CAPTURES = {
    "dotnet":        ("dotnet", [["dotnet", "new", "--help"],
                                 ["dotnet", "new", "list"],
                                 ["dotnet", "new", "console", "--help"]]),
    "cargo":         ("cargo", [["cargo", "new", "--help"],
                                ["cargo", "init", "--help"]]),
    "flutter":       ("flutter", [["flutter", "create", "--help"]]),
    "cookiecutter":  ("cookiecutter", [["cookiecutter", "--help"]]),
    "gh":            ("gh", [["gh", "repo", "create", "--help"]]),
    "npm-init":      ("npm", [["npm", "init", "--help"]]),
    "create-vite":   ("npx", [["npx", "--yes", "create-vite@latest", "--help"]]),
    "create-next":   ("npx", [["npx", "--yes", "create-next-app@latest", "--help"]]),
    "create-react-router": ("npx", [["npx", "--yes", "create-react-router@latest", "--help"]]),
}
NETWORK = {"create-vite", "create-next", "create-react-router"}


def run(cmd: list[str]) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=180, shell=(sys.platform == "win32"))
        return f"$ {' '.join(cmd)}\n(exit {r.returncode})\n{r.stdout}{r.stderr}\n"
    except subprocess.TimeoutExpired:
        return f"$ {' '.join(cmd)}\n(timed out)\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args(argv)
    OUT.mkdir(exist_ok=True)
    for tool, (needs, cmds) in CAPTURES.items():
        if a.offline and tool in NETWORK:
            print(f"skip  {tool} (--offline)")
            continue
        if not shutil.which(needs):
            print(f"skip  {tool} ({needs} not installed)")
            continue
        text = "".join(run(c) for c in cmds)
        (OUT / f"{tool}.txt").write_text(text, encoding="utf-8")
        print(f"wrote {tool}.txt ({len(text.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
