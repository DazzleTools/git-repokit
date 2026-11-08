#!/usr/bin/env python3
"""
Default configuration values for RepoKit.

This module provides centralized default values to prevent duplication
and ensure consistency across the codebase.
"""

from typing import Dict, List

from dazzle_lib.continuum import Continuum

# How exposed a thing is: who can read it. Zero is "controlled" -- readable
# only by people the owner chose -- and the line every private folder must
# stay below is "shared" (a remote that could be public). Agreed with djdarcy,
# 2026-11-01 (git-repokit's vault: notes/...__both_the-exposure-continuum.md).
EXPOSURE_CONTINUUM = Continuum(
    name="exposure",
    ranks={"untracked": -2, "local": -1, "controlled": 0, "shared": 1, "public": 2},
    invariant="who can read it",
)

# How private work is kept (--private-mode):
#   nested         private/ is its own git repository (main-only's default)
#   nested-branch  private/ is still its own repository, and the record
#                  folders (PROMOTED_DIRS) are tracked on the private branch
#                  (the private-branch strategies' default for a create)
#   branch         private/ itself is tracked on the private branch too
#                  (opt-in, warned; adopt's default)
PRIVATE_MODES = ("nested", "nested-branch", "branch")
VAULT_MODES = ("nested", "nested-branch")      # private/ is its own repository
BRANCH_MODES = ("nested-branch", "branch")     # the private branch tracks the record folders

# The record folders a private-branch project tracks at its root, on the
# private branch only: conversations, revisions ("as easy as MOVING an old
# file to ./revisions and it's then still git tracked"), and logs, whose run
# output is ignored (logs/.gitignore) so chosen logs can still be committed.
PROMOTED_DIRS = ("convos", "revisions", "logs")


def private_dir_names(dirs) -> List[str]:
    """Folder names from --private-dirs entries however they were written:
    "convos/", "/revisions" and "logs" are convos, revisions and logs."""
    return [d.strip("/") for d in dirs if d and d.strip("/")]


def mode_exposure(promoted) -> Dict[str, str]:
    """Where a project's private work sits on EXPOSURE_CONTINUUM, recorded in
    .repokit.json: the vault, and each folder the mode promotes to the private
    branch (RepoManager.promoted). Each level is checked against the
    continuum: an unknown name raises, and none may reach "shared" -- the
    line a private folder must stay below."""
    ranks = {"private/": "local"}
    ranks.update({f"{name}/": "local" for name in promoted if name != "private"})
    for path, level in ranks.items():
        if not EXPOSURE_CONTINUUM.is_colder(level, "shared"):
            raise ValueError(f"{path} would be {level}: private work stays below shared")
    return ranks


# Default private directories that should not appear in public branches
DEFAULT_PRIVATE_DIRS = [
    "private",
    "revisions", 
    "logs",
    "convos"
]

# Default sensitive files that should not appear in public branches.
# `.repokit.json` left this list in 0.9.6 (djdarcy, 2026-10-24: "Track it"):
# the record of how a project was made is committed with it, as the template
# route and git-repokit itself do; it holds nothing private.
DEFAULT_SENSITIVE_FILES = [
    "CLAUDE.md",
]

# Default sensitive file patterns (supports glob patterns)
# Cross-platform compatible patterns using Python's fnmatch/pathlib
DEFAULT_SENSITIVE_PATTERNS = [
    "Clipboard Text*",
    "nul",           # Windows reserved name
    "*.tmp",
    "*.log", 
    ".env*",
    "*.backup",
    "*.bak",
    "*.*~",          # Vim backup files (primary pattern for files like listall.cmd~)
    "*~",            # Vim backup files (fallback for single extension)
    "logs/*",        # All files in logs directory
    "logs/**/*",     # All files in logs subdirectories  
    "revisions/*",   # All files in revisions directory
    "revisions/**/*", # All files in revisions subdirectories
]

# Default branch configurations for BranchContext
DEFAULT_PRIVATE_BRANCHES = [
    "private",
    "local"
]

DEFAULT_PUBLIC_BRANCHES = [
    "main", 
    "master", 
    "dev", 
    "test", 
    "staging", 
    "live", 
    "prod", 
    "production"
]

# Files/directories that should only exist in private branches
DEFAULT_PRIVATE_PATTERNS = [
    "CLAUDE.md",
    "private/",
    "convos/",
    "logs/",
    "credentials/",
    "secrets/",
    ".env.local",
    ".env.private",
    "**/__private__*",
    "**/private_*",
    "*~",  # Vim backup files
    "*.*~",  # Vim backup files (multiple extensions)
]

# Files that should be excluded from public branches during merges
DEFAULT_EXCLUDE_FROM_PUBLIC = [
    "CLAUDE.md",
    "private/claude/",
    "private/docs/",
    "private/notes/",
    "private/temp/",
    "revisions/",
    "test-runs/",
    "test_runs/",
]

# Branch-specific excludes - files that should only exist in certain branches
BRANCH_SPECIFIC_EXCLUDES = {
    "private": [],  # Private branch can contain everything
    "dev": DEFAULT_PRIVATE_DIRS + DEFAULT_SENSITIVE_FILES,
    "main": DEFAULT_PRIVATE_DIRS + DEFAULT_SENSITIVE_FILES,
    "staging": DEFAULT_PRIVATE_DIRS + DEFAULT_SENSITIVE_FILES,
    "test": DEFAULT_PRIVATE_DIRS + DEFAULT_SENSITIVE_FILES,
    "live": DEFAULT_PRIVATE_DIRS + DEFAULT_SENSITIVE_FILES,
}

# Branch strategies -- the one definition. Everything else (config defaults,
# CLI choices and help, the branches publish pushes, directory_analyzer's
# list) derives from this table.
#
#   branches        branches created (and pushed on publish)
#   worktrees       branches checked out as worktrees beside the repository
#   private_branch  the local-only branch for private work, or None for none
#   push            branches publish pushes (default: branches)
#
# main-only is the recommended model: one branch, private notes kept out of
# git (in S3, in a separate repository under private/). The others are the
# private-branch model: private work on a local-only branch, finished work
# moved to the public branches. Valid, more involved, fully supported.
BRANCH_STRATEGIES = {
    "main-only": {
        "branches": ["main"],
        "worktrees": [],
        "private_branch": None,
    },
    "standard": {
        "branches": ["main", "dev", "staging", "test", "live"],
        "worktrees": ["main", "dev"],
        "private_branch": "private",
    },
    "simple": {
        "branches": ["main", "dev"],
        "worktrees": ["main"],
        "private_branch": "private",
    },
    "gitflow": {
        "branches": ["main", "develop", "release", "hotfix"],
        "worktrees": ["main", "develop"],
        "private_branch": "private",
        # release/hotfix are local working branches; publish pushes these two
        "push": ["main", "develop"],
    },
    "github-flow": {
        "branches": ["main"],
        "worktrees": ["main"],
        "private_branch": "private",
    },
    # minimal used to declare private_branch "main", but --private-branch's
    # CLI default always overrode it, so `create` has always made a "private"
    # branch beside main. Honouring "main" would commit private files to the
    # public branch (the pre-commit guard refuses them), so the table states
    # what minimal has always done.
    "minimal": {
        "branches": ["main"],
        "worktrees": [],
        "private_branch": "private",
    },
}

PRIVATE_BRANCH_STRATEGIES = [name for name in BRANCH_STRATEGIES if name != "main-only"]

# What a bare `repokit create` makes. adopt and migrate build the private-branch
# model only, so they default to the strategy below instead.
DEFAULT_BRANCH_STRATEGY = "main-only"
DEFAULT_ADOPT_STRATEGY = "standard"


def strategy_branch_list(name: str) -> List[str]:
    """All branches a strategy has, its private branch first when it has one."""
    strategy = BRANCH_STRATEGIES[name]
    private = strategy["private_branch"]
    branches = list(strategy["branches"])
    if private and private not in branches:
        branches.insert(0, private)
    return branches


def strategy_push_branches(name: str) -> List[str]:
    """Branches publish pushes for a strategy; [] for an unknown strategy."""
    strategy = BRANCH_STRATEGIES.get(name)
    if strategy is None:
        return []
    return list(strategy.get("push", strategy["branches"]))


# Branch lists per strategy, private branch included (used by directory_analyzer)
DEFAULT_BRANCH_STRATEGIES = {name: strategy_branch_list(name) for name in BRANCH_STRATEGIES}

# Default directory profiles - centralized from directory_profiles.py
# The text is 0.9.12's again (0.10.3). A profile entry in the private set
# (logs, private, convos, revisions) goes to private_dirs, the protection
# list, never to the folders created -- so this text never changed a layout.
# Where convos/, revisions/ and logs/ are made follows the private mode:
# inside the vault in nested, promoted to the root on the private branch in
# nested-branch and branch (PROMOTED_DIRS).
DEFAULT_DIRECTORY_PROFILES = {
    "minimal": ["src", "tests", "docs"],
    "standard": [
        "src", "tests", "docs", "scripts", "config",
        "logs", "private", "convos", "revisions"
    ],
    "complete": [
        "src", "tests", "docs", "scripts", "config", "logs",
        "private", "convos", "revisions", "data", "examples",
        "tools", "resources", "assets"
    ]
}

# Directory groups by purpose - centralized from directory_profiles.py
DEFAULT_DIRECTORY_GROUPS = {
    "development": ["src", "tests", "scripts", "tools"],
    "documentation": ["docs", "examples", "resources"],
    "operations": ["config", "logs", "data"],
    "privacy": ["private", "convos", "credentials"],
}

# Directory type mapping (conceptual → actual name) - from directory_profiles.py
DEFAULT_DIRECTORY_TYPE_MAPPING = {
    "src": "src",  # Will be customized for each project (e.g., "repokit")
    "tests": "tests",
    "docs": "docs",
    "config": "config",
    "scripts": "scripts",
    "private": "private",
    "convos": "convos",
    "logs": "logs",
}

# Enhanced private directory sets - from directory_profiles.py
DEFAULT_PRIVATE_DIR_SETS = {
    "standard": DEFAULT_PRIVATE_DIRS.copy(),
    "enhanced": DEFAULT_PRIVATE_DIRS + ["credentials", "secrets", "local"],
}