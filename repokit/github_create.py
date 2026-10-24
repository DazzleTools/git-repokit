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
                     logger=None, report: Optional[List[str]] = None) -> Optional[str]:
    """Create <owner>/<name> on GitHub, run the GitHub-half steps the config
    names (`github_setup`, 0.9.3: labels and the two issues before the push,
    the rest after), and push the public branches.

    Returns None on success, or what went wrong (the local repository is
    left as it is either way). The steps' report lines go into ``report``.
    """
    from . import github_setup
    steps = github_setup.setup_names(config.get("github_setup"))
    report = report if report is not None else []

    gh = gh_command()
    if gh is None:
        return "gh (the GitHub CLI) is not installed; see https://cli.github.com"

    rc, out = _run(gh + ["auth", "status"], repo_root)
    if rc != 0:
        return f"gh is not logged in (run `gh auth login`): {out}"

    rc, out = _run(gh + ["api", "user", "-q", ".login"], repo_root)
    login = out.splitlines()[-1].strip() if rc == 0 and out else None
    if not organization and not login:
        return f"could not read the GitHub user from gh: {out}"
    # Refuse on another account: the config names the person's handle, and gh
    # is logged into someone else (0.9.3).
    github_cfg = config.get("github") if isinstance(config.get("github"), dict) else {}
    configured = (github_cfg or {}).get("username")
    if configured and login and configured.lower() != login.lower():
        return (f"gh is logged into {login!r} but the config's github.username is {configured!r}; "
                "switch with `gh auth switch` or fix the config")
    owner = organization or login

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

    # Before the first push: the labels and the two issues, so they are #1 and #2.
    setup = github_setup.GhSetup(gh, f"{owner}/{name}", lambda cmd: _run(cmd, repo_root))
    project = config.get("name") or name
    if "labels" in steps:
        report += setup.labels()
    if "issues" in steps:
        drafts = os.path.join(repo_root, "private", "claude", "issues")
        report += setup.issues(project, drafts if os.path.isdir(drafts) else None)
    if "pin" in steps:
        report += setup.pin()

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

    # After the push: the settings that need the repository's content or no ordering.
    if "discussions" in steps:
        report += setup.discussions()
    if "topics" in steps:
        report += setup.topics(list(config.get("topics") or []))
    if "pypi-environment" in steps:
        report += setup.pypi_environment(config.get("archetype"))
    if "traffic" in steps:
        report += setup.traffic(project)
    if steps:
        report += github_setup.reminders(f"{owner}/{name}", list(config.get("extras") or []))
    return None
