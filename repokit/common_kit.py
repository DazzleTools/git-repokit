#!/usr/bin/env python3
"""
git-repokit-common in a project git-repokit creates.

git-repokit-common holds the hooks and tools (version sync, private-content
checks, test gating) that projects use; git-repokit's part is to put a copy
in the project and set it up. Nothing here writes a hook itself: the hooks
come from repokit-common's own install-hooks.sh.

The copy is vendored as a git subtree at scripts/repokit-common/, the layout
the hooks look for first (/create-project, Phase 3).
"""

import os
import shutil
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

DEFAULT_URL = "https://github.com/DazzleTools/git-repokit-common.git"
DEFAULT_REF = "main"
PREFIX = "scripts/repokit-common"

# REPOKIT_COMMON_SOURCE overrides the URL (a local path works); "off" skips
# vendoring. The test suite uses both so it never reaches the network.
SOURCE_ENV = "REPOKIT_COMMON_SOURCE"

# repokit-common's built-in private branches (hooks/lib.sh); a project whose
# private branch is not among them must list it in private-branches.
REPOKIT_COMMON_PRIVATE_BRANCHES = ["local", "private", "feature/*", "feat/*",
                                   "prototype/*", "experiment/*", "spike/*"]


def _git(args: List[str], cwd: str) -> Tuple[int, str]:
    result = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    return result.returncode, (result.stdout + result.stderr).strip()


def source(config: Dict) -> Optional[Tuple[str, str]]:
    """(url, ref) to vendor from, or None when vendoring is switched off."""
    settings = config.get("repokit_common") or {}
    url = os.environ.get(SOURCE_ENV) or settings.get("url") or DEFAULT_URL
    if url.strip().lower() == "off":
        return None
    return url, settings.get("ref") or DEFAULT_REF


def vendor(repo_root: str, url: str, ref: str) -> Optional[str]:
    """Add repokit-common at scripts/repokit-common/ as a squashed subtree.

    Needs a clean tree and at least one commit. The two commits git subtree
    makes are not signed (git builds them with plumbing); git-repokit does not
    rewrite them -- the next steps say how. Returns None or the failure.
    """
    if os.path.exists(os.path.join(repo_root, PREFIX)):
        return f"{PREFIX} already exists"
    if os.path.isdir(url):
        url = os.path.abspath(url)
    rc, out = _git(["subtree", "add", f"--prefix={PREFIX}", url, ref, "--squash"], repo_root)
    return None if rc == 0 else out or "git subtree add failed"


def find_sh() -> Optional[str]:
    """The POSIX shell to run install-hooks.sh with.

    On Windows, Git for Windows' own sh (next to git), never a `bash` found
    on PATH -- that can be WSL's, which would see a different filesystem.
    """
    if sys.platform == "win32":
        rc, exec_path = _git(["--exec-path"], os.getcwd())
        if rc == 0 and exec_path:
            # <git>/mingw64/libexec/git-core -> <git>/bin/sh.exe
            git_root = os.path.normpath(os.path.join(exec_path.strip(), "..", "..", ".."))
            candidate = os.path.join(git_root, "bin", "sh.exe")
            if os.path.isfile(candidate):
                return candidate
    return shutil.which("sh")


def install_hooks(repo_root: str) -> Optional[str]:
    """Run the vendored install-hooks.sh. Returns None or the failure."""
    script = os.path.join(repo_root, PREFIX, "install-hooks.sh")
    if not os.path.isfile(script):
        return f"{PREFIX}/install-hooks.sh not found"
    sh = find_sh()
    if not sh:
        return "no POSIX shell (sh) found to run install-hooks.sh"
    result = subprocess.run([sh, f"{PREFIX}/install-hooks.sh"], cwd=repo_root,
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        return (result.stdout + result.stderr).strip() or "install-hooks.sh failed"
    return None


def private_branch_settings(private_branch: Optional[str], private_paths: List[str]) -> Dict[str, List[str]]:
    """Settings that make repokit-common's pre-commit guard the private-branch model.

    private-patterns: the paths git-repokit's own guard protected (literal
    prefixes; repokit-common adds them to its built-in list).
    private-branches: only when the private branch is not one of
    repokit-common's defaults; the setting replaces the list, so the defaults
    are listed too.
    """
    settings: Dict[str, List[str]] = {}
    if private_paths:
        settings["private-patterns"] = sorted(dict.fromkeys(private_paths))
    if private_branch and private_branch not in REPOKIT_COMMON_PRIVATE_BRANCHES:
        settings["private-branches"] = REPOKIT_COMMON_PRIVATE_BRANCHES + [private_branch]
    return settings


def _toml_list(values: List[str]) -> str:
    return "[" + ", ".join('"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"' for v in values) + "]"


def write_settings(repo_root: str, settings: Dict[str, List[str]]) -> Optional[str]:
    """Write [tool.repokit-common] settings; returns the file written, or None.

    pyproject.toml when the project has one and no table yet, else
    .repokit-common.toml (with the header repokit-common requires).
    """
    if not settings:
        return None
    lines = [f"{key} = {_toml_list(values)}" for key, values in settings.items()]
    body = "[tool.repokit-common]\n" + "\n".join(lines) + "\n"

    pyproject = os.path.join(repo_root, "pyproject.toml")
    if os.path.isfile(pyproject):
        with open(pyproject, encoding="utf-8") as f:
            text = f.read()
        if "[tool.repokit-common]" not in text:
            with open(pyproject, "a", encoding="utf-8") as f:
                f.write(("\n" if text and not text.endswith("\n") else "") + "\n" + body)
            return "pyproject.toml"
        return None  # a table already exists; never merge into it blindly

    path = os.path.join(repo_root, ".repokit-common.toml")
    if os.path.exists(path):
        return None
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Settings for the vendored git-repokit-common hooks and tools\n" + body)
    return ".repokit-common.toml"


RESIGN_HINT = (
    "git subtree made two unsigned commits for scripts/repokit-common/. If this\n"
    "repository signs its commits, re-sign them before pushing (see the\n"
    "/create-project skill, Phase 3), or leave them unsigned."
)
