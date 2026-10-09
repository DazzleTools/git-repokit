#!/usr/bin/env python3
"""
`repokit create --github`: the repository on GitHub, through the gh CLI.

gh holds the login (`gh auth login`), so git-repokit never handles a token on
this path -- the ease the GitHub template used to give, where GitHub made the
repository and the tooling only configured it (djdarcy, 2026-10-07).

Only public branches are pushed: in the private-branch model the private
branch never leaves the machine, so `gh repo create --push` (which pushes the
current branch -- the private one there) is not used; branches are pushed
explicitly.
"""

import os
import shutil
import subprocess
import sys
from typing import List, Optional, Tuple

from .defaults import strategy_push_branches

GH_ENV = "REPOKIT_GH"  # override the gh executable (tests use a stub)


def gh_command() -> Optional[List[str]]:
    override = os.environ.get(GH_ENV)
    if override:
        return [sys.executable, override] if override.endswith(".py") else [override]
    found = shutil.which("gh")
    return [found] if found else None


def _run(cmd: List[str], cwd: str) -> Tuple[int, str]:
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                                encoding="utf-8", errors="replace")
    except OSError as e:  # the executable does not exist or cannot run
        return 127, str(e)
    return result.returncode, (result.stdout + result.stderr).strip()


def branches_to_push(config: dict, private_branch: Optional[str], existing: List[str]) -> List[str]:
    """The strategy's public branches that exist locally; never the private branch."""
    wanted = strategy_push_branches(config.get("branch_strategy", "main-only")) or ["main"]
    return [b for b in wanted if b in existing and b != private_branch]


def create_on_github(repo_root: str, name: str, config: dict, private_branch: Optional[str],
                     organization: Optional[str] = None, public: bool = False,
                     logger=None) -> Optional[str]:
    """Create <owner>/<name> on GitHub and push the public branches.

    Returns None on success, or what went wrong (the local repository is
    left as it is either way).
    """
    gh = gh_command()
    if gh is None:
        return "gh (the GitHub CLI) is not installed; see https://cli.github.com"

    rc, out = _run(gh + ["auth", "status"], repo_root)
    if rc != 0:
        return f"gh is not logged in (run `gh auth login`): {out}"

    owner = organization
    if not owner:
        rc, out = _run(gh + ["api", "user", "-q", ".login"], repo_root)
        if rc != 0 or not out:
            return f"could not read the GitHub user from gh: {out}"
        owner = out.splitlines()[-1].strip()

    create = gh + ["repo", "create", f"{owner}/{name}",
                   "--public" if public else "--private",
                   "--source", repo_root, "--remote", "origin"]
    description = config.get("description")
    if description:
        create += ["--description", description]
    rc, out = _run(create, repo_root)
    if rc != 0:
        return f"gh repo create failed: {out}"
    if logger:
        logger.info(f"Created {owner}/{name} on GitHub ({'public' if public else 'private'})")

    rc, out = _run(["git", "for-each-ref", "--format=%(refname:short)", "refs/heads"], repo_root)
    existing = out.split()
    pushed = []
    for branch in branches_to_push(config, private_branch, existing):
        rc, out = _run(["git", "push", "-u", "origin", branch], repo_root)
        if rc != 0:
            return f"git push of '{branch}' failed: {out}"
        pushed.append(branch)
    if logger:
        logger.info(f"Pushed: {', '.join(pushed) or 'nothing'}")
    return None
