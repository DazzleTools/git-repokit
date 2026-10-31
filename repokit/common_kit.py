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
import re
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
    if rc == 0:
        return None
    # A failure midway (Windows' path limit on a deep project directory, a
    # lost connection) leaves what git read into the index and part of the
    # checkout behind; take it back out so the project's first commit is not
    # made of, or refused for, half of repokit-common.
    prefix = os.path.join(repo_root, PREFIX)
    if os.path.exists(prefix):
        _git(["reset", "-q", "--", PREFIX], repo_root)
        target = prefix
        if sys.platform == "win32" and not prefix.startswith("\\\\?\\"):
            target = "\\\\?\\" + os.path.abspath(prefix)
        shutil.rmtree(target, ignore_errors=True)
    return out or "git subtree add failed"


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


def languages_setting(languages: List[str], layer_folders: List[str]) -> List[str]:
    """The `languages` value a create writes for git-repokit-common's hooks.

    repokit's language names mapped to repokit-common's, in the composed
    order (the first is primary): js-ts is "typescript" when the ts layer is
    part of the composition, else "javascript"; python, c-cpp and paradox
    are the same names; generic and the `any` pseudo-language add nothing.
    Writing it, rather than leaving the hooks to detect it from the root,
    keeps a project whose markers sit in a subfolder (a plugin in plugin/)
    from reading as Python (design 2026-10-30__08-28-15, Addendum 2).
    """
    out: List[str] = []
    for lang in languages:
        if lang == "js-ts":
            name = "typescript" if any(f.endswith("js-ts/ts") for f in layer_folders) else "javascript"
        elif lang in ("python", "c-cpp", "paradox"):
            name = lang
        else:
            continue
        if name not in out:
            out.append(name)
    return out


def _toml_list(values: List[str]) -> str:
    return "[" + ", ".join('"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"' for v in values) + "]"


_TABLE_HEADER = re.compile(r"^[ \t]*\[[ \t]*tool[ \t]*\.[ \t]*\"?repokit-common\"?[ \t]*\][ \t]*\r?\n", re.MULTILINE)


# Keys whose list only ever protects more as it grows: when the table already
# has one, the entries it lacks are added to it rather than the key being
# skipped (0.9.12). A layer's pyproject.toml ships its own private-patterns, and
# skipping the key dropped CLAUDE.md and the private dirs from the guard.
_UNION_KEYS = ("private-patterns",)
_TOML_STRING = re.compile(r'"((?:[^"\\]|\\.)*)"|\'([^\']*)\'')


def _union_into_list(table: str, key: str, values: List[str]) -> Optional[str]:
    """`table` with the `values` its `key = [...]` list lacks appended inside
    the brackets (a list written over several lines is kept as written).
    None when the key is not a list or nothing is missing."""
    found = re.search(rf"^([ \t]*{re.escape(key)}[ \t]*=[ \t]*\[)(.*?)(\])", table, re.MULTILINE | re.DOTALL)
    if not found:
        return None
    inner = found.group(2)
    present = {(m.group(1) if m.group(1) is not None else m.group(2)).replace('\\"', '"').replace("\\\\", "\\")
               for m in _TOML_STRING.finditer(inner)}
    missing = [v for v in values if v not in present]
    if not missing:
        return None
    kept = inner.rstrip()
    tail = inner[len(kept):]
    sep = "" if not kept.strip() else (" " if kept.endswith(",") else ", ")
    added = _toml_list(missing)[1:-1]
    return table[: found.start(2)] + kept + sep + added + tail + table[found.end(2):]


def _merge_into_table(text: str, settings: Dict[str, List[str]]) -> Optional[str]:
    """Add the keys the existing [tool.repokit-common] table lacks, right after
    its header. A key already present is never overwritten, except that a
    `_UNION_KEYS` list gains the entries it lacks. Returns the new text, or
    None when nothing was missing."""
    header = _TABLE_HEADER.search(text)
    if not header:
        return None
    rest = text[header.end():]
    next_table = re.search(r"^[ \t]*\[", rest, re.MULTILINE)   # the table ends at the next header
    table = rest[: next_table.start()] if next_table else rest
    after = rest[len(table):]
    missing = [key for key in settings
               if not re.search(rf"^[ \t]*{re.escape(key)}[ \t]*=", table, re.MULTILINE)]
    grown = table
    for key in _UNION_KEYS:
        if key in settings and key not in missing:
            unioned = _union_into_list(grown, key, settings[key])
            if unioned is not None:
                grown = unioned
    if not missing and grown == table:
        return None
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = "".join(f"{key} = {_toml_list(settings[key])}{nl}" for key in missing)
    return text[: header.end()] + lines + grown + after


def write_settings(repo_root: str, settings: Dict[str, List[str]]) -> Optional[str]:
    """Write [tool.repokit-common] settings; returns the file written, or None.

    pyproject.toml when the project has one (the table is added, or the keys
    it lacks are merged into the table it has), else .repokit-common.toml
    (created with the header repokit-common requires, or merged the same way).
    A key already present is never overwritten: a code-type layer may ship
    the file with its own version-source, and the private-branch settings go
    in beside it rather than being dropped. The one exception is
    private-patterns, whose existing list gains the entries it lacks.
    """
    if not settings:
        return None
    lines = [f"{key} = {_toml_list(values)}" for key, values in settings.items()]
    body = "[tool.repokit-common]\n" + "\n".join(lines) + "\n"

    pyproject = os.path.join(repo_root, "pyproject.toml")
    if os.path.isfile(pyproject):
        with open(pyproject, encoding="utf-8", newline="") as f:
            text = f.read()
        if _TABLE_HEADER.search(text):
            merged = _merge_into_table(text, settings)
            if merged is None:
                return None
            with open(pyproject, "w", encoding="utf-8", newline="") as f:
                f.write(merged)
            return "pyproject.toml"
        with open(pyproject, "a", encoding="utf-8") as f:
            f.write(("\n" if text and not text.endswith("\n") else "") + "\n" + body)
        return "pyproject.toml"

    path = os.path.join(repo_root, ".repokit-common.toml")
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as f:
            text = f.read()
        merged = _merge_into_table(text, settings)
        if merged is None:
            return None
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(merged)
        return ".repokit-common.toml"
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Settings for the vendored git-repokit-common hooks and tools\n" + body)
    return ".repokit-common.toml"


RESIGN_HINT = (
    "git subtree made two unsigned commits for scripts/repokit-common/. If this\n"
    "repository signs its commits, re-sign them before pushing (see the\n"
    "/create-project skill, Phase 3), or leave them unsigned."
)
