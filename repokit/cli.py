#!/usr/bin/env python3
"""
RepoKit: Repository Template Generator

Command-line interface for creating standardized Git repositories.
"""

import os
import sys
import json
import argparse
import logging
import subprocess
from typing import Dict, Any, Optional

from .config import ConfigManager
from .defaults import BRANCH_STRATEGIES, DEFAULT_ADOPT_STRATEGY, PRIVATE_BRANCH_STRATEGIES
from .repo_manager import RepoManager
from .template_engine import TemplateEngine
from .directory_analyzer import (
    analyze_directory,
    plan_migration,
    migrate_directory,
    analyze_project,
    adopt_project,
)

# Set UTF-8 encoding for subprocess on Windows to prevent Unicode errors
if sys.platform == 'win32':
    import locale
    # Force UTF-8 for subprocess communication
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['PYTHONUTF8'] = '1'


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        prog="repokit",
        description="RepoKit - A Git repository template generator with standardized structures",
        epilog="""
Examples:
  # Create a new Python project with standard structure
  repokit create myproject --language python --dir-profile standard
  
  # Adopt an existing project with RepoKit structure
  repokit adopt ./existing-project --strategy safe
  
  # Create with custom branch strategy
  repokit create webapp --branch-strategy gitflow --publish-to github

For detailed help on any command, use: repokit <command> --help
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Version argument
    from . import __version__
    parser.add_argument("--version", action="version", version=f"RepoKit {__version__}")
    
    # Global options that apply to all commands
    parser.add_argument(
        "--config", "-c", 
        help="Path to configuration file (JSON)",
        metavar="FILE"
    )

    parser.add_argument(
        "--save-config",
        help="Save the final configuration to the specified file",
        metavar="FILE"
    )
    
    # Verbosity control
    verbosity_group = parser.add_mutually_exclusive_group()
    verbosity_group.add_argument(
        "--verbose",
        "-v",
        action="count",
        default=0,
        help="Increase verbosity (-v for INFO, -vv for DEBUG, -vvv for detailed DEBUG)"
    )
    verbosity_group.add_argument(
        "--quiet", "-q", action="store_true", help="Suppress all output except errors"
    )

    # Create subparsers for commands
    subparsers = parser.add_subparsers(
        title="Commands",
        description="Available commands",
        dest="command",
        help="Use 'repokit <command> --help' for command-specific help",
        required=True
    )

    # CREATE command
    create_parser = subparsers.add_parser(
        "create",
        help="Create a new repository with RepoKit structure",
        description="""
Create a new Git repository with standardized structure, branches, and templates.

This command initializes a complete project structure including:
- Directory hierarchy based on profiles or custom specification
- Git setup for the chosen branch strategy
- Template files for documentation, CI/CD, and language-specific needs
- Pre-commit hooks for private content protection
- Optional remote repository creation and pushing

Directory Profiles:
  minimal   - Basic structure: src, tests, docs
  standard  - Common structure with config, logs, private directories
  complete  - Full structure including examples, assets, resources

Branch Strategies:
  main-only    - one branch, main; the repository is <name>/ itself and
                 private/ stays out of git

  Private-branch model (work on a local-only 'private' branch, move finished
  work to the public branches; repository in <name>/local/, main checked out
  in <name>/github/):
  standard     - private, main, dev, staging, test, live
  simple       - private, main, dev
  gitflow      - private, main, develop, release, hotfix
  github-flow  - private, main
  minimal      - private, main (no worktrees)
        """,
        epilog="""
Examples:
  # Basic Python project
  repokit create myapp --language python
  
  # Web project with standard profile
  repokit create webapp --dir-profile standard --language javascript
  
  # Enterprise project with custom directories
  repokit create enterprise-app --dir-profile complete --directories "analytics,ml-models"
  
  # Create and publish to GitHub
  repokit create myproject --publish-to github --private-repo
  
Recipe: Data Science Project
  repokit create ml-project \\
    --language python \\
    --dir-profile standard \\
    --directories "data,models,notebooks" \\
    --branch-strategy simple
  
Recipe: Microservice
  repokit create user-service \\
    --dir-profile minimal \\
    --branch-strategy github-flow \\
    --publish-to github \\
    --organization mycompany
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    create_parser.add_argument(
        "name",
        help="Name of the repository to create"
    )
    
    # Language and description. The names come from the code-type layers'
    # manifest (repokit/templates/layers/manifest.toml) and are validated
    # against it before anything is created, so the list here is the help only.
    create_parser.add_argument(
        "--language", "-l",
        action="append",
        metavar="LANG[,LANG...]",
        help=f"The project's language(s), in the order their layers apply; a list or repeated. "
             f"Known: {', '.join(_known_language_names())} (default: generic, no code-type layers)"
    )

    create_parser.add_argument(
        "--with",
        dest="with_layers",
        action="append",
        metavar="NAME[,NAME...]",
        help="What the project is, below its language: a preset such as python/pypi or "
             "js-ts/claude-plugin, a layer such as c-cpp/qt, or bare names when unique "
             "(claude-plugin; cmake-lib,qt). Comma-separated or repeated; each implies its "
             "language; a list that equals a preset is that preset. See `repokit list`."
    )

    create_parser.add_argument(
        "--license",
        metavar="ID|file=PATH|none",
        help="The LICENSE to write: a catalogue id (mit, gpl-3.0, gpl-3.0-or-later, apache-2.0, "
             "all-rights-reserved, ...; `repokit list` shows them), file=PATH to copy a text as is, or "
             "none. Required unless the global config names `license` (or `license_private` for "
             "--private-repo); holder and year come from the git identity and the clock."
    )

    create_parser.add_argument(
        "--extras",
        dest="extras",
        action="append",
        metavar="NAME[,NAME...]",
        help="The structure's optional files, by name: funding, dependabot, stale, pr-template, "
             "release-template, roadmap, platform-support, vscode-settings, placeholders, or all. "
             "Off unless named here or in the global config's `extras` list."
    )
    create_parser.add_argument(
        "--no-extras",
        dest="no_extras",
        action="store_true",
        help="Write none of the extras, whatever the global config says"
    )

    create_parser.add_argument(
        "--github-setup",
        dest="github_setup",
        action="append",
        metavar="STEP[,STEP...]",
        help="With --github, what to set up on the new repository: labels, issues (the Roadmap and "
             "Quick Notes as #1 and #2, before the first push), pin, discussions, topics, "
             "pypi-environment, traffic (prints ghtraf's commands), or all. Off unless named here "
             "or in the global config's `github_setup` list."
    )
    create_parser.add_argument(
        "--topics",
        metavar="TOPIC[,TOPIC...]",
        help="Repository topics for --github-setup topics"
    )

    create_parser.add_argument(
        "--description", "-d",
        help="Short description of the repository"
    )
    
    # Directory configuration - NEW PROFILE SUPPORT
    dir_group = create_parser.add_argument_group("Directory Configuration")
    dir_group.add_argument(
        "--dir-profile",
        choices=["minimal", "standard", "complete"],
        help="Use a predefined directory profile"
    )
    
    dir_group.add_argument(
        "--dir-groups",
        help="Comma-separated list of directory groups (development,documentation,operations,privacy)",
        metavar="GROUPS"
    )
    
    dir_group.add_argument(
        "--directories", "-dir",
        help="Comma-separated list of additional directories to create",
        metavar="DIRS"
    )
    
    dir_group.add_argument(
        "--private-dirs", "-pd",
        help="Comma-separated list of directories to mark as private",
        metavar="DIRS"
    )
    
    dir_group.add_argument(
        "--private-set",
        choices=["standard", "enhanced"],
        default="standard",
        help="Private directory set to use (default: standard)"
    )
    
    dir_group.add_argument(
        "--sensitive-files", "-sf",
        help="Comma-separated list of sensitive files to exclude from public branches",
        metavar="FILES"
    )
    
    dir_group.add_argument(
        "--sensitive-patterns", "-sp",
        help="Comma-separated list of file patterns to exclude from public branches (supports glob)",
        metavar="PATTERNS"
    )
    
    # Branch configuration
    branch_group = create_parser.add_argument_group("Branch Configuration")
    branch_group.add_argument(
        "--branches", "-b",
        help="Comma-separated list of branches to create",
        metavar="BRANCHES"
    )
    
    branch_group.add_argument(
        "--worktrees", "-w",
        help="Comma-separated list of branches to create worktrees for",
        metavar="BRANCHES"
    )
    
    branch_group.add_argument(
        "--private-branch",
        default=None,
        help="Name of the private branch (default: the strategy's; 'private' in the private-branch strategies)"
    )

    branch_group.add_argument(
        "--default-branch",
        help="Name of the default branch (default: main)"
    )

    branch_group.add_argument(
        "--branch-strategy",
        choices=list(BRANCH_STRATEGIES),
        help="Predefined branch strategy to use (default: main-only; or a private-branch strategy)"
    )

    branch_group.add_argument(
        "--private-mode",
        choices=["nested", "branch"],
        help="How private work is kept: 'nested' makes private/ its own git repository "
             "(linked into every worktree); 'branch' keeps it on the private branch only. "
             "Default: nested for main-only, branch for the private-branch strategies"
    )

    common_group = branch_group.add_mutually_exclusive_group()
    common_group.add_argument(
        "--with-common", dest="with_common", action="store_true", default=None,
        help="Vendor git-repokit-common (hooks, version sync, tools) at scripts/repokit-common/ "
             "and install its hooks (default for main-only)"
    )
    common_group.add_argument(
        "--no-common", dest="with_common", action="store_false",
        help="Do not vendor git-repokit-common; git-repokit's own pre-commit guard is installed instead "
             "(default for the private-branch strategies)"
    )

    branch_group.add_argument(
        "--branch-config",
        help="Path to branch configuration file (JSON)",
        metavar="FILE"
    )
    
    branch_group.add_argument(
        "--branch-dir-main",
        help="Directory name for main branch worktree (default: github)"
    )
    
    branch_group.add_argument(
        "--branch-dir-dev",
        help="Directory name for dev branch worktree (default: dev)"
    )
    
    # Git configuration
    git_group = create_parser.add_argument_group("Git Configuration")
    git_group.add_argument(
        "--user-name",
        help="Git user name for commits"
    )
    
    git_group.add_argument(
        "--user-email",
        help="Git user email for commits"
    )
    
    # Remote/Publishing options
    remote_group = create_parser.add_argument_group("Remote Repository")
    remote_group.add_argument(
        "--github",
        action="store_true",
        help="Create the repository on GitHub with the gh CLI (its login is used; private unless "
             "--public) and push the public branches. With --no-push nothing is pushed"
    )
    remote_group.add_argument(
        "--public",
        action="store_true",
        help="With --github: make the GitHub repository public"
    )
    remote_group.add_argument(
        "--publish-to",
        choices=["github", "gitlab"],
        help="Publish repository to a remote service through its REST API and a token"
    )
    
    remote_group.add_argument(
        "--remote-name",
        default="origin",
        help="Name for the remote (default: origin)"
    )
    
    remote_group.add_argument(
        "--private-repo",
        action="store_true",
        help="Create a private repository on remote service"
    )
    
    remote_group.add_argument(
        "--organization", "--org",
        help="GitHub organization or GitLab group name"
    )

    remote_group.add_argument(
        "--no-push",
        action="store_true",
        help="Don't push branches after creating remote repository"
    )

    # Authentication
    auth_group = create_parser.add_argument_group("Authentication")
    auth_group.add_argument(
        "--token",
        help="Authentication token for remote service"
    )
    
    auth_group.add_argument(
        "--token-command",
        help="Command to retrieve token (e.g., 'pass show github/token')"
    )
    
    auth_group.add_argument(
        "--credentials-file",
        help="Path to credentials file",
        metavar="FILE"
    )
    
    # Template options
    template_group = create_parser.add_argument_group("Template Configuration")
    template_group.add_argument(
        "--templates-dir",
        help="Path to custom templates directory",
        metavar="DIR"
    )
    
    template_group.add_argument(
        "--ai",
        choices=["none", "claude"],
        default="claude",
        help="AI tool integration to include (default: claude)"
    )

    # ANALYZE command
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyze an existing directory for RepoKit compatibility",
        description="""
Analyze an existing directory to understand its structure and provide recommendations
for RepoKit adoption or migration.

This command examines:
- Current directory structure and how it maps to RepoKit profiles
- Git repository state and branch configuration
- Existing configuration files and potential conflicts
- Project type detection (language, framework)
- Migration complexity assessment

The analysis provides:
- Recommended migration strategy (safe, replace, merge)
- Suggested branch strategy based on current setup
- List of actions that would be taken during migration
- Potential issues or conflicts to resolve
        """,
        epilog="""
Examples:
  # Analyze current directory
  repokit analyze .
  
  # Analyze a specific project
  repokit analyze /path/to/project
  
  # Verbose analysis with detailed information
  repokit analyze ./myproject -vv
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    analyze_parser.add_argument(
        "name",
        help="Path to directory to analyze"
    )

    # MIGRATE command
    migrate_parser = subparsers.add_parser(
        "migrate",
        help="Migrate an existing directory to RepoKit structure",
        description="""
Migrate an existing directory to use RepoKit's standardized structure.

Migration Strategies:
  safe     - Preserve all existing files, only add missing RepoKit elements
  replace  - Replace conflicting files with RepoKit templates
  merge    - Attempt to merge existing content with RepoKit templates

This command will:
- Create missing standard directories
- Add RepoKit configuration files
- Set up Git hooks for private content protection
- Generate appropriate .gitignore entries
- Create template files where needed
        """,
        epilog="""
Examples:
  # Safe migration (preserves all existing files)
  repokit migrate ./myproject
  
  # Replace strategy for clean template files
  repokit migrate ./myproject --migration-strategy replace
  
  # Dry run to see what would happen
  repokit migrate ./myproject --dry-run
  
  # Migrate and publish to GitHub
  repokit migrate ./myproject --publish-to github
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    migrate_parser.add_argument(
        "name",
        help="Path to directory to migrate"
    )
    
    migrate_parser.add_argument(
        "--migration-strategy",
        choices=["safe", "replace", "merge"],
        default="safe",
        help="Migration strategy (default: safe)"
    )
    
    migrate_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    
    migrate_parser.add_argument(
        "--backup",
        action="store_true",
        help="Create a backup of the directory before making changes"
    )
    
    migrate_parser.add_argument(
        "--backup-location",
        help="Custom backup location (default: <dir>_backup_<timestamp>)",
        metavar="PATH"
    )
    
    migrate_parser.add_argument(
        "--publish-to",
        choices=["github", "gitlab"],
        help="Publish to remote after migration"
    )

    # ADOPT command
    adopt_parser = subparsers.add_parser(
        "adopt",
        help="Adopt RepoKit in an existing Git repository",
        description="""
Adopt RepoKit structure in an existing Git repository without disrupting
current development workflow.

This is the recommended approach for active projects. It:
- Preserves all existing Git history
- Adds RepoKit structure incrementally
- Sets up branches according to detected or specified strategy
- Maintains existing remote connections
- Can optionally publish to a new remote

The adopt command is safer than migrate for repositories with:
- Active development
- Existing CI/CD pipelines
- Multiple contributors
- Production deployments
        """,
        epilog="""
Examples:

BASIC ADOPTION:
  # Adopt current directory with minimal setup
  repokit adopt
  
  # Adopt specific directory with standard profile
  repokit adopt ./my-project --dir-profile standard

PYTHON PROJECT ADOPTION (Real Example):
  # Adopt a Python project with comprehensive setup and GitHub publishing
  # This is the command used for the UNCtools project deployment
  repokit adopt ./my-python-project \\
    --branch-strategy simple \\
    --migration-strategy safe \\
    --dir-profile standard \\
    --language python \\
    --description "Universal Naming Convention (UNC) path tools for Python" \\
    --publish-to github \\
    --repo-name MyPythonTools \\
    --private-repo \\
    --ai claude \\
    --backup \\
    --backup-location ../backup-before-adoption

GITHUB DEPLOYMENT RECIPES:
  # Public GitHub repository
  repokit adopt ./open-source-project \\
    --publish-to github \\
    --repo-name awesome-open-source \\
    --language javascript \\
    --dir-profile complete
    
  # Private GitHub repository with organization
  repokit adopt ./company-project \\
    --publish-to github \\
    --repo-name internal-tools \\
    --organization mycompany \\
    --private-repo \\
    --language python
    
  # Personal project with full configuration
  repokit adopt ./personal-project \\
    --publish-to github \\
    --repo-name my-awesome-project \\
    --private-repo \\
    --description "My personal coding project" \\
    --user-name "John Doe" \\
    --user-email "john@example.com"

BRANCH STRATEGY EXAMPLES:
  # Simple strategy (main, dev, private)
  repokit adopt --branch-strategy simple --language python
  
  # GitFlow strategy (main, dev, feature, release, hotfix branches)
  repokit adopt --branch-strategy gitflow --dir-profile complete
  
  # GitHub Flow (main, feature branches)
  repokit adopt --branch-strategy github-flow
  
  # Custom branches
  repokit adopt --branches "main,staging,production" --default-branch main

DIRECTORY PROFILE EXAMPLES:
  # Minimal profile (docs, tests, scripts)
  repokit adopt --dir-profile minimal
  
  # Standard profile (docs, tests, scripts, examples, config)
  repokit adopt --dir-profile standard
  
  # Complete profile (all directories including logs, private, revisions)
  repokit adopt --dir-profile complete
  
  # Custom directories
  repokit adopt --directories "data,models,notebooks,experiments"

SENSITIVE FILE PROTECTION:
  # Specify sensitive files to exclude from public branches
  repokit adopt --sensitive-files ".env,secrets.json,api_keys.txt"
  
  # Specify sensitive patterns (vim backups, logs, private dirs)
  repokit adopt --sensitive-patterns "*.log,*~,private/*,secrets/*"
  
  # Use enhanced privacy protection
  repokit adopt --private-set enhanced --private-dirs "experiments,drafts"

BACKUP AND SAFETY:
  # Create backup before adoption
  repokit adopt --backup --backup-location ../project-backup-$(date +%Y%m%d)
  
  # Dry run to preview all changes
  repokit adopt --dry-run -vv
  
  # Clean git history during adoption
  repokit adopt --clean-history --cleaning-recipe pre-open-source

AI INTEGRATION:
  # Add Claude AI integration files
  repokit adopt --ai claude
  
  # Skip AI integration
  repokit adopt --ai none

COMMON WORKFLOWS:
  1. Test adoption (recommended first step):
     repokit adopt ./my-project --dry-run -vv
     
  2. Safe adoption with backup:
     repokit adopt ./my-project --backup --backup-location ../backup
     
  3. GitHub deployment:
     repokit adopt ./my-project --publish-to github --repo-name my-project --private-repo
     
  4. Complete adoption (full features):
     repokit adopt ./my-project \\
       --dir-profile complete \\
       --branch-strategy simple \\
       --language python \\
       --ai claude \\
       --publish-to github \\
       --private-repo
       
For more detailed documentation, see: docs/Adoption-Guide.md
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    adopt_parser.add_argument(
        "name",
        nargs="?",
        help="Path to repository (default: current directory)"
    )
    
    # Language and description (the same names as create; the layers are laid
    # down without overwriting the adopted project's own files)
    adopt_parser.add_argument(
        "--language", "-l",
        action="append",
        metavar="LANG[,LANG...]",
        help=f"The project's language(s). Known: {', '.join(_known_language_names())} (default: generic)"
    )

    adopt_parser.add_argument(
        "--with",
        dest="with_layers",
        action="append",
        metavar="NAME[,NAME...]",
        help="Presets and layers to lay down without overwriting the project's own files, "
             "as for create (see `repokit list`)"
    )

    adopt_parser.add_argument(
        "--license",
        metavar="ID|file=PATH|none",
        help="The LICENSE to write when the project has none, as for create; an existing LICENSE is kept"
    )

    adopt_parser.add_argument(
        "--description", "-d",
        help="Short description of the repository"
    )
    
    # Directory configuration - NEW PROFILE SUPPORT
    adopt_dir_group = adopt_parser.add_argument_group("Directory Configuration")
    adopt_dir_group.add_argument(
        "--dir-profile",
        choices=["minimal", "standard", "complete"],
        help="Use a predefined directory profile"
    )
    
    adopt_dir_group.add_argument(
        "--dir-groups",
        help="Comma-separated list of directory groups (development,documentation,operations,privacy)",
        metavar="GROUPS"
    )
    
    adopt_dir_group.add_argument(
        "--directories", "-dir",
        help="Comma-separated list of additional directories to create",
        metavar="DIRS"
    )
    
    adopt_dir_group.add_argument(
        "--private-dirs", "-pd",
        help="Comma-separated list of directories to mark as private",
        metavar="DIRS"
    )
    
    adopt_dir_group.add_argument(
        "--private-set",
        choices=["standard", "enhanced"],
        default="standard",
        help="Private directory set to use (default: standard)"
    )
    
    adopt_dir_group.add_argument(
        "--sensitive-files", "-sf",
        help="Comma-separated list of sensitive files to exclude from public branches",
        metavar="FILES"
    )
    
    adopt_dir_group.add_argument(
        "--sensitive-patterns", "-sp",
        help="Comma-separated list of file patterns to exclude from public branches (supports glob)",
        metavar="PATTERNS"
    )
    
    # Branch configuration
    adopt_branch_group = adopt_parser.add_argument_group("Branch Configuration")
    adopt_branch_group.add_argument(
        "--branches", "-b",
        help="Comma-separated list of branches to create",
        metavar="BRANCHES"
    )
    
    adopt_branch_group.add_argument(
        "--worktrees", "-w",
        help="Comma-separated list of branches to create worktrees for",
        metavar="BRANCHES"
    )
    
    adopt_branch_group.add_argument(
        "--private-branch",
        default=None,
        help="Name of the private branch (default: the strategy's; 'private' in the private-branch strategies)"
    )

    adopt_branch_group.add_argument(
        "--default-branch",
        help="Name of the default branch (default: main)"
    )

    # Adoption builds the private-branch model only; main-only adoption is not
    # implemented yet.
    adopt_branch_group.add_argument(
        "--branch-strategy",
        choices=PRIVATE_BRANCH_STRATEGIES,
        help="Branch strategy to implement"
    )
    
    adopt_branch_group.add_argument(
        "--branch-config",
        help="Path to branch configuration file (JSON)",
        metavar="FILE"
    )
    
    adopt_branch_group.add_argument(
        "--branch-dir-main",
        help="Directory name for main branch worktree (default: github)"
    )
    
    adopt_branch_group.add_argument(
        "--branch-dir-dev",
        help="Directory name for dev branch worktree (default: dev)"
    )
    
    # Git configuration
    adopt_git_group = adopt_parser.add_argument_group("Git Configuration")
    adopt_git_group.add_argument(
        "--user-name",
        help="Git user name for commits"
    )
    
    adopt_git_group.add_argument(
        "--user-email",
        help="Git user email for commits"
    )
    
    # Migration strategy
    adopt_parser.add_argument(
        "--migration-strategy",
        choices=["safe", "replace", "merge"],
        default="safe",
        help="File handling strategy (default: safe)"
    )
    
    adopt_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying repository"
    )
    
    adopt_parser.add_argument(
        "--backup",
        action="store_true",
        help="Create a backup of the repository before making changes"
    )
    
    adopt_parser.add_argument(
        "--backup-location",
        help="Custom backup location (default: <repo>_backup_<timestamp>)",
        metavar="PATH"
    )
    
    adopt_parser.add_argument(
        "--clean-history",
        action="store_true", 
        help="Clean private content from git history before creating public branches"
    )
    
    adopt_parser.add_argument(
        "--cleaning-recipe",
        choices=["pre-open-source", "windows-safe", "remove-secrets"],
        default="pre-open-source",
        help="Recipe for cleaning history (default: pre-open-source)"
    )
    
    # Remote/Publishing options
    adopt_remote_group = adopt_parser.add_argument_group("Remote Repository")
    adopt_remote_group.add_argument(
        "--publish-to",
        choices=["github", "gitlab"],
        help="Publish repository to a remote service"
    )
    
    adopt_remote_group.add_argument(
        "--repo-name",
        help="Name for the remote repository (default: directory name)"
    )
    
    adopt_remote_group.add_argument(
        "--remote-name",
        default="origin",
        help="Name for the remote (default: origin)"
    )
    
    adopt_remote_group.add_argument(
        "--private-repo",
        action="store_true",
        help="Create a private repository on remote service"
    )
    
    adopt_remote_group.add_argument(
        "--organization",
        help="GitHub organization or GitLab group name"
    )
    
    adopt_remote_group.add_argument(
        "--no-push",
        action="store_true",
        help="Don't push branches after creating remote repository"
    )
    
    # Authentication
    adopt_auth_group = adopt_parser.add_argument_group("Authentication")
    adopt_auth_group.add_argument(
        "--token",
        help="Authentication token for remote service"
    )
    
    adopt_auth_group.add_argument(
        "--token-command",
        help="Command to retrieve token (e.g., 'pass show github/token')"
    )
    
    adopt_auth_group.add_argument(
        "--credentials-file",
        help="Path to credentials file",
        metavar="FILE"
    )
    
    # Template options
    adopt_template_group = adopt_parser.add_argument_group("Template Configuration")
    adopt_template_group.add_argument(
        "--templates-dir",
        help="Path to custom templates directory",
        metavar="DIR"
    )
    
    adopt_template_group.add_argument(
        "--ai",
        choices=["none", "claude"],
        default="claude",
        help="AI tool integration to include (default: claude)"
    )

    # PUBLISH command
    publish_parser = subparsers.add_parser(
        "publish",
        help="Publish an existing repository to GitHub/GitLab",
        description="""
Publish an existing RepoKit repository to a remote service.

This command:
- Creates a remote repository on GitHub or GitLab
- Sets up authentication using tokens or stored credentials
- Configures remote tracking for all branches
- Pushes all branches and tags
- Can work with organization/group repositories
        """,
        epilog="""
Examples:
  # Publish current repository to GitHub
  repokit publish . --publish-to github
  
  # Publish to organization with private visibility
  repokit publish ./myproject --publish-to github --organization myorg --private-repo
  
  # Publish to GitLab group
  repokit publish . --publish-to gitlab --organization mygroup
  
  # Publish without pushing branches
  repokit publish . --publish-to github --no-push
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    publish_parser.add_argument(
        "name",
        help="Path to repository to publish"
    )
    
    publish_parser.add_argument(
        "--repo-name",
        help="Name for the remote repository (default: directory name)"
    )
    
    publish_parser.add_argument(
        "--publish-to",
        choices=["github", "gitlab"],
        required=True,
        help="Remote service to publish to"
    )
    
    publish_parser.add_argument(
        "--remote-name",
        default="origin",
        help="Name for the remote (default: origin)"
    )
    
    publish_parser.add_argument(
        "--private-repo",
        action="store_true",
        help="Create as private repository"
    )
    
    publish_parser.add_argument(
        "--organization",
        help="Organization/group name"
    )
    
    publish_parser.add_argument(
        "--no-push",
        action="store_true",
        help="Create remote but don't push"
    )
    
    publish_parser.add_argument(
        "--token",
        help="Authentication token"
    )
    
    publish_parser.add_argument(
        "--token-command",
        help="Command to retrieve token"
    )
    
    publish_parser.add_argument(
        "--credentials-file",
        help="Path to credentials file"
    )
    
    publish_parser.add_argument(
        "--templates-dir",
        help="Path to custom templates directory",
        metavar="DIR"
    )
    
    publish_parser.add_argument(
        "--include-branches",
        nargs="+",
        help="Only push these specific branches (overrides strategy defaults)"
    )
    
    publish_parser.add_argument(
        "--exclude-branches", 
        nargs="+",
        help="Exclude these branches from publishing (in addition to private)"
    )

    # BOOTSTRAP command
    bootstrap_parser = subparsers.add_parser(
        "bootstrap",
        help="Generate a bootstrap script for RepoKit setup",
        description="""
Generate a self-contained Python script that can bootstrap a complete
RepoKit project with a single command.

The bootstrap script:
- Checks for Git installation
- Configures Git user if needed
- Creates the repository structure
- Sets up all branches and worktrees
- Can optionally publish to remote
- Includes all RepoKit functionality in one file

This is useful for:
- Quick project initialization
- CI/CD pipelines
- Containerized environments
- Sharing project templates
        """,
        epilog="""
Examples:
  # Generate basic bootstrap script
  repokit bootstrap --name myproject
  
  # Bootstrap with GitHub publishing
  repokit bootstrap --name webapp --service github --private
  
  # Custom output location
  repokit bootstrap --name api --output setup_api.py
  
  # For organization project
  repokit bootstrap --name service --service github --organization mycompany
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    bootstrap_parser.add_argument(
        "--name",
        help="Project name for the bootstrap script"
    )
    
    bootstrap_parser.add_argument(
        "--output", "-o",
        default="bootstrap_repokit.py",
        help="Output file path (default: bootstrap_repokit.py)"
    )
    
    bootstrap_parser.add_argument(
        "--service",
        choices=["github", "gitlab"],
        help="Include remote publishing in bootstrap"
    )
    
    bootstrap_parser.add_argument(
        "--private",
        action="store_true",
        help="Create private repository"
    )
    
    bootstrap_parser.add_argument(
        "--organization",
        help="Organization/group name"
    )
    
    bootstrap_parser.add_argument(
        "--no-publish",
        action="store_true",
        help="Skip publishing step in bootstrap"
    )
    
    bootstrap_parser.add_argument(
        "--git-user-name",
        help="Git user name for bootstrap"
    )
    
    bootstrap_parser.add_argument(
        "--git-user-email",
        help="Git user email for bootstrap"
    )

    # Other simple commands
    list_parser = subparsers.add_parser(
        "list",
        help="List the languages, presets and layers that --language and --with accept",
        description="Per language: its presets (name = layers; planned ones marked), then each "
                    "facet with its choices and whether one or any may be picked."
    )
    list_parser.add_argument("language", nargs="?", help="One language only")

    subparsers.add_parser(
        "list-templates",
        help="List all available templates",
        description="Display all available template files that RepoKit can use."
    )
    
    init_config_parser = subparsers.add_parser(
        "init-config",
        help="Initialize a .repokit.json configuration file",
        description="""
Create a default .repokit.json configuration file in the current directory.

This file can be customized to set project-specific defaults for:
- Directory structure and profiles
- Branch strategies and names
- Git user configuration
- Remote service preferences
- Template directories
        """
    )
    
    store_creds_parser = subparsers.add_parser(
        "store-credentials",
        help="Store credentials for GitHub/GitLab",
        description="""
Securely store authentication credentials for GitHub or GitLab.

Credentials are stored in:
- ~/.repokit/credentials.json (default)
- Or a custom location specified by --credentials-file

The stored credentials are used automatically when publishing repositories.
        """
    )
    
    store_creds_parser.add_argument(
        "--publish-to",
        choices=["github", "gitlab"],
        required=True,
        help="Service to store credentials for"
    )
    
    store_creds_parser.add_argument(
        "--token",
        help="Authentication token to store"
    )
    
    store_creds_parser.add_argument(
        "--token-command",
        help="Command to retrieve token"
    )
    
    store_creds_parser.add_argument(
        "--organization",
        help="Default organization/group"
    )
    
    store_creds_parser.add_argument(
        "--credentials-file",
        help="Custom credentials file path"
    )
    
    # Add guardrails commands
    guardrails_parser = subparsers.add_parser(
        "setup-guardrails",
        help="Set up private content protection guardrails",
        description="""
Set up guardrails that keep private content off public branches.

The hooks are git-repokit-common's: this installs them from the project's
vendored copy (scripts/repokit-common/), writes the settings the private-branch
model needs, and configures branch-specific exclusions.
        """,
        epilog="""
Examples:
  # Install git-repokit-common's hooks from the vendored copy
  repokit setup-guardrails

  # No copy yet: vendor git-repokit-common first (makes two commits)
  repokit setup-guardrails --vendor

  # The previous git-repokit hooks (pre-commit + post-checkout restore)
  repokit setup-guardrails --legacy --force
        """
    )

    guardrails_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing hooks (--legacy only; install-hooks.sh always rewrites its stubs)"
    )
    guardrails_parser.add_argument(
        "--vendor",
        action="store_true",
        help="Add git-repokit-common at scripts/repokit-common/ first if the project has no copy "
             "(git subtree; needs a clean working tree)"
    )
    guardrails_parser.add_argument(
        "--legacy",
        action="store_true",
        help="Install git-repokit's previous hooks instead (its own pre-commit and the post-checkout "
             "that restores private files from the private branch)"
    )
    
    check_guardrails_parser = subparsers.add_parser(
        "check-guardrails",
        help="Check guardrails status and validate current state",
        description="Check if guardrails are properly installed and validate staged changes."
    )
    
    safe_merge_parser = subparsers.add_parser(
        "safe-merge",
        help="Merge branches with private content protection",
        description="""
Safely merge branches while automatically excluding private content when
merging from private to public branches.
        """,
        epilog="""
Examples:
  # Preview merge from private to current branch
  repokit safe-merge private --preview
  
  # Perform safe merge
  repokit safe-merge private --no-ff --no-commit
        """
    )
    
    safe_merge_parser.add_argument(
        "source_branch",
        help="Branch to merge from"
    )
    
    safe_merge_parser.add_argument(
        "--no-commit",
        action="store_true",
        default=True,
        help="Perform merge without committing (default)"
    )
    
    safe_merge_parser.add_argument(
        "--no-ff",
        action="store_true",
        default=True,
        help="Create merge commit even if fast-forward (default)"
    )
    
    safe_merge_parser.add_argument(
        "--preview",
        action="store_true",
        help="Preview what would be merged without doing it"
    )

    # Add safe-merge-dev command
    safe_merge_dev_parser = subparsers.add_parser(
        "safe-merge-dev",
        help="Merge development branches with history protection",
        description="""
Merge development branches while protecting sensitive commit history.

This command helps prevent detailed implementation history from leaking
to public branches by intelligently squashing or preserving commits based
on branch patterns and configurable rules.

Branch categories and default behaviors:
- prototype/*, experiment/*, spike/*: Always squash (development/exploration)
- feature/*: Interactive mode (ask whether to squash)
- bugfix/*, hotfix/*: Preserve history (important for tracking)

The command will:
- Analyze commits in the branch
- Remove sensitive patterns from messages
- Generate meaningful squash commit messages
- Provide interactive options for feature branches
        """,
        epilog="""
Examples:
  # Merge a prototype branch (auto-squashes)
  repokit safe-merge-dev prototype/new-feature
  
  # Merge a feature branch (interactive)
  repokit safe-merge-dev feature/oauth-integration
  
  # Force squash with custom message
  repokit safe-merge-dev feature/api --squash --message "Add REST API"
  
  # Preserve full history
  repokit safe-merge-dev feature/refactor --no-squash
  
  # Preview without merging
  repokit safe-merge-dev experiment/ml-model --preview
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    safe_merge_dev_parser.add_argument(
        "branch",
        help="Development branch to merge"
    )
    
    safe_merge_dev_parser.add_argument(
        "--target",
        help="Target branch (default: current branch)"
    )
    
    safe_merge_dev_parser.add_argument(
        "--squash",
        action="store_true",
        help="Force squash merge regardless of branch rules"
    )
    
    safe_merge_dev_parser.add_argument(
        "--no-squash",
        action="store_true",
        help="Preserve all commits regardless of branch rules"
    )
    
    safe_merge_dev_parser.add_argument(
        "--message", "-m",
        help="Custom commit message for squashed merge"
    )
    
    safe_merge_dev_parser.add_argument(
        "--preserve-last",
        type=int,
        help="Preserve the last N commits (not yet implemented)"
    )
    
    safe_merge_dev_parser.add_argument(
        "--preview",
        action="store_true",
        help="Preview merge without executing"
    )

    # Add clean-history command
    clean_history_parser = subparsers.add_parser(
        "clean-history",
        help="Clean sensitive data from repository history",
        description="""
Clean sensitive data from repository history using git filter-repo.

This command provides safe, user-friendly tools to remove private files,
secrets, and other sensitive data from git history. It includes pre-built
recipes for common scenarios and comprehensive safety features.

WARNING: This rewrites repository history and requires force-push!

Pre-built recipes:
- pre-open-source: Remove common private files (private/, CLAUDE.md, etc.)
- windows-safe: Fix Windows reserved names (nul, con, aux, etc.)
- remove-secrets: Remove API keys and passwords (coming soon)
- cutoff-date: Remove old private data before a date (coming soon)

Safety features:
- Automatic backup before cleaning
- Dry-run preview mode
- Confirmation prompts
- Clear warnings and instructions
        """,
        epilog="""
Examples:
  # Interactive mode - analyze and suggest cleaning
  repokit clean-history
  
  # Remove common private files before open-sourcing
  repokit clean-history --recipe pre-open-source
  
  # Preview what would be removed
  repokit clean-history --recipe pre-open-source --dry-run
  
  # Fix Windows compatibility issues
  repokit clean-history --recipe windows-safe
  
  # Remove specific paths
  repokit clean-history --remove-paths private/ logs/ secrets/
  
  # Skip backup (not recommended)
  repokit clean-history --recipe pre-open-source --no-backup
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    clean_history_parser.add_argument(
        "--recipe",
        choices=["pre-open-source", "windows-safe", "remove-secrets", "cutoff-date"],
        help="Use a pre-built cleaning recipe"
    )
    
    clean_history_parser.add_argument(
        "--remove-paths",
        nargs="+",
        help="Specific paths to remove from history"
    )
    
    clean_history_parser.add_argument(
        "--cutoff-sha",
        help="Remove private data only before this commit"
    )
    
    clean_history_parser.add_argument(
        "--cutoff-date",
        help="Remove private data only before this date (YYYY-MM-DD)"
    )
    
    clean_history_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying repository"
    )
    
    clean_history_parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip creating backup (not recommended)"
    )
    
    clean_history_parser.add_argument(
        "--backup-location",
        help="Custom backup location (default: <repo>_backup_<timestamp>)"
    )
    
    clean_history_parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompts"
    )

    # Add manage-gitkeep command
    gitkeep_parser = subparsers.add_parser(
        "manage-gitkeep",
        help="Manage .gitkeep files in directories",
        description="""
Manage .gitkeep files based on directory contents.

This command automatically:
- Adds .gitkeep files to empty directories to ensure they are tracked by Git
- Removes .gitkeep files from directories that contain other files

This is useful for maintaining clean Git history while ensuring empty directories
are properly tracked.
        """,
        epilog="""
Examples:
  # Manage .gitkeep files in current directory
  repokit manage-gitkeep
  
  # Manage .gitkeep files in specific directory
  repokit manage-gitkeep --directory ./src
  
  # Process only top-level directories (no recursion)
  repokit manage-gitkeep --no-recursive
  
  # Preview changes without applying them
  repokit manage-gitkeep --dry-run
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    gitkeep_parser.add_argument(
        "--directory",
        "-d",
        default=".",
        help="Directory to process (default: current directory)"
    )
    
    gitkeep_parser.add_argument(
        "--recursive",
        action="store_true",
        default=True,
        help="Process subdirectories recursively (default: True)"
    )
    
    gitkeep_parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Do not process subdirectories recursively"
    )
    
    gitkeep_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without actually making changes"
    )

    # Add analyze-history command
    analyze_history_parser = subparsers.add_parser(
        "analyze-history",
        help="Analyze repository history for sensitive data",
        description="""
Analyze repository history to identify sensitive data that should be cleaned.

This command scans your repository history and reports:
- Private directories (private/, logs/, etc.)
- Windows compatibility issues (nul, con, aux files)
- Large files that might not belong
- Potential secrets (coming soon)
- Branch structure and commit count

Use this before clean-history to understand what needs cleaning.
        """,
        epilog="""
Examples:
  # Analyze current repository
  repokit analyze-history
  
  # Analyze with detailed output
  repokit analyze-history -v
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    return parser.parse_args()


def setup_logging(verbosity: int, quiet: bool = False) -> None:
    """
    Set up logging based on verbosity level.

    Args:
        verbosity: Verbosity level (0-3+)
        quiet: Whether to suppress all output except errors
    """
    if quiet:
        log_level = logging.ERROR
    else:
        # Map verbosity levels to logging levels
        log_levels = {
            0: logging.WARNING,  # Default - only warnings and errors
            1: logging.INFO,     # -v - basic operations
            2: logging.DEBUG,    # -vv - file operations and detailed flow
            3: logging.DEBUG,    # -vvv - pattern matching and cleanup details
        }
        # Cap at maximum level
        capped_verbosity = min(verbosity, 3)
        log_level = log_levels[capped_verbosity]

    # Configure basic logging
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # For highest verbosity, adjust formatter to include more details
    if verbosity >= 3:
        for handler in logging.root.handlers:
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(levelname)s - %(name)s - %(filename)s:%(lineno)d - %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )

    # Get logger for repokit
    logger = logging.getLogger("repokit")

    # Set up verbosity-specific loggers for detailed debugging
    if verbosity >= 2:
        # Enable detailed file operation logging
        logging.getLogger("repokit.utils").setLevel(logging.DEBUG)
        logging.getLogger("repokit.repo_manager").setLevel(logging.DEBUG)
        
    if verbosity >= 3:
        # Enable pattern matching and cleanup debugging
        logging.getLogger("repokit.cleanup").setLevel(logging.DEBUG)
        logging.getLogger("repokit.patterns").setLevel(logging.DEBUG)

    # Log verbosity level for debugging
    if verbosity >= 1:
        logger.info(f"Verbosity level: {verbosity} (-{'v' * verbosity})")
        if verbosity >= 2:
            logger.info("File operations debugging enabled")
        if verbosity >= 3:
            logger.info("Pattern matching and cleanup debugging enabled")


def _known_language_names():
    """The languages the layers' manifest names (for help text); generic alone
    when the manifest cannot be read."""
    try:
        from . import layers
        root = layers.layers_root()
        return layers.known_languages(layers.load_manifest(root)) if root else [layers.GENERIC]
    except Exception:
        return ["generic"]


def args_to_config(args: argparse.Namespace) -> Dict[str, Any]:
    """
    Convert command-line arguments to configuration dictionary.

    Args:
        args: Parsed command-line arguments

    Returns:
        Configuration dictionary
    """
    # --language is a list (repeated, or comma-separated); `language` keeps the
    # first for everything that reads one value, `languages` carries them all.
    languages = []
    if getattr(args, "language", None):
        from .layers import parse_languages
        languages = parse_languages(args.language)

    # Base configuration from CLI arguments
    cli_config = {
        "name": getattr(args, "name", None),
        "language": languages[0] if languages else None,
        "description": getattr(args, "description", None),
        "private_branch": getattr(args, "private_branch", None),
        "user": (
            {"name": args.user_name, "email": args.user_email}
            if getattr(args, "user_name", None) or getattr(args, "user_email", None)
            else None
        ),
    }

    if languages:
        cli_config["languages"] = languages
    if getattr(args, "with_layers", None):
        from .layers import parse_languages
        cli_config["with"] = parse_languages(args.with_layers)
    if getattr(args, "license", None):
        cli_config["license"] = args.license
        cli_config["license_cli"] = True      # the flag beats license_private; a config value does not
    if getattr(args, "organization", None):
        cli_config["organization"] = args.organization    # the owner in the extras' URLs
    if getattr(args, "github_setup", None):
        from .layers import parse_languages as _split_steps
        cli_config["github_setup"] = _split_steps(args.github_setup)
    if getattr(args, "topics", None):
        cli_config["topics"] = [t.strip() for t in args.topics.split(",") if t.strip()]
    if getattr(args, "no_extras", False):
        cli_config["extras"] = []
    elif getattr(args, "extras", None):
        from .layers import parse_languages as _split
        cli_config["extras"] = _split(args.extras)
    if getattr(args, "private_repo", False):
        cli_config["private_repo"] = True

    # Handle directory profile configuration
    if hasattr(args, "dir_profile") and args.dir_profile:
        cli_config["directory_profile"] = args.dir_profile
    
    if hasattr(args, "dir_groups") and args.dir_groups:
        cli_config["directory_groups"] = [
            group.strip() for group in args.dir_groups.split(",")
        ]
    
    if hasattr(args, "private_set") and args.private_set:
        cli_config["private_set"] = args.private_set

    # Handle list-type arguments
    if hasattr(args, "branches") and args.branches:
        cli_config["branches"] = [branch.strip() for branch in args.branches.split(",")]

    if hasattr(args, "worktrees") and args.worktrees:
        cli_config["worktrees"] = [
            worktree.strip() for worktree in args.worktrees.split(",")
        ]

    if hasattr(args, "directories") and args.directories:
        cli_config["directories"] = [
            directory.strip() for directory in args.directories.split(",")
        ]

    if hasattr(args, "private_dirs") and args.private_dirs:
        cli_config["private_dirs"] = [
            dir.strip() for dir in args.private_dirs.split(",")
        ]

    if hasattr(args, "sensitive_files") and args.sensitive_files:
        cli_config["sensitive_files"] = [
            file.strip() for file in args.sensitive_files.split(",")
        ]

    if hasattr(args, "sensitive_patterns") and args.sensitive_patterns:
        cli_config["sensitive_patterns"] = [
            pattern.strip() for pattern in args.sensitive_patterns.split(",")
        ]

    # Handle branch strategy
    if hasattr(args, "branch_strategy") and args.branch_strategy:
        cli_config["branch_strategy"] = args.branch_strategy
    elif getattr(args, "command", None) in ("adopt", "migrate"):
        # Adoption builds the private-branch model only (see defaults)
        cli_config["branch_strategy"] = DEFAULT_ADOPT_STRATEGY

    if getattr(args, "private_mode", None):
        cli_config["private_mode"] = args.private_mode

    if getattr(args, "with_common", None) is not None:
        cli_config["with_common"] = args.with_common

    # Handle AI integration
    if hasattr(args, "ai") and args.ai and args.ai != "none":
        cli_config["ai_integration"] = args.ai

    # Handle backup configuration
    if hasattr(args, "backup") and args.backup:
        cli_config["backup"] = True
    
    if hasattr(args, "backup_location") and args.backup_location:
        cli_config["backup_location"] = args.backup_location

    # Handle migration strategy
    if hasattr(args, "migration_strategy") and args.migration_strategy:
        cli_config["migration_strategy"] = args.migration_strategy

    # Handle remote publishing configuration  
    if hasattr(args, "publish_to") and args.publish_to:
        cli_config["publish_to"] = args.publish_to
    
    if hasattr(args, "repo_name") and args.repo_name:
        cli_config["repo_name"] = args.repo_name
        
    if hasattr(args, "private_repo") and args.private_repo:
        cli_config["private_repo"] = True

    # Handle branch directory mappings
    branch_directories = {}

    if hasattr(args, "branch_dir_main") and args.branch_dir_main:
        branch_directories["main"] = args.branch_dir_main

    if hasattr(args, "branch_dir_dev") and args.branch_dir_dev:
        branch_directories["dev"] = args.branch_dir_dev

    if branch_directories:
        cli_config["branch_config"] = {"branch_directories": branch_directories}

    # default branch from CLI
    if hasattr(args, "default_branch") and args.default_branch:
        cli_config["default_branch"] = args.default_branch

    # Remove None values from config
    return {k: v for k, v in cli_config.items() if v is not None}


def main() -> int:
    """
    Main entry point.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    # Status output uses symbols a non-UTF-8 console (Windows' default code
    # page, output piped to a tool) cannot encode; replace them rather than
    # crash after the work is done.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass

    args = parse_arguments()

    # Set up logging based on verbosity
    setup_logging(args.verbose, args.quiet)
    logger = logging.getLogger("repokit")

    # Initialize configuration manager
    config_manager = ConfigManager(verbose=args.verbose)

    # Load config file if provided
    if args.config and os.path.exists(args.config):
        config_manager.load_config_file(args.config)

    # Load branch configuration file if provided
    if hasattr(args, 'branch_config') and args.branch_config and os.path.exists(args.branch_config):
        config_manager.load_branch_config_file(args.branch_config)

    # Add CLI arguments to configuration
    cli_config = args_to_config(args)
    config_manager.set_cli_config(cli_config)

    # Get the final, merged configuration
    config = config_manager.get_config()

    # Add remote integration configuration
    if hasattr(args, 'publish_to') and args.publish_to:
        service_config = config.get(args.publish_to, {})
        # Ensure service_config is a dict, not a boolean
        if not isinstance(service_config, dict):
            service_config = {}
        if hasattr(args, 'organization') and args.organization:
            if args.publish_to == "github":
                service_config["organization"] = args.organization
            else:
                service_config["group"] = args.organization
        config[args.publish_to] = service_config

    # Validate configuration
    errors = config_manager.validate_config()
    if errors:
        for error in errors:
            logger.error(f"Configuration error: {error}")
        return 1

    # Save configuration if requested
    if hasattr(args, 'save_config') and args.save_config:
        config_manager.save_config(args.save_config)

    # Handle commands
    if args.command == "list":
        from . import layers as _layers
        from .template_engine import TemplateEngine as _TemplateEngine
        _root = _layers.layers_root(_TemplateEngine(templates_dir=getattr(args, "templates_dir", None)))
        if _root is None:
            logger.error("no code-type layers found with the templates")
            return 1
        try:
            for line in _layers.catalogue_lines(_layers.load_manifest(_root), args.language):
                print(line)
        except _layers.LayerError as e:
            logger.error(str(e))
            return 1
        return 0

    elif args.command == "list-templates":
        template_engine = TemplateEngine(
            templates_dir=args.templates_dir, verbose=args.verbose
        )
        templates = template_engine.list_templates()
        print("Available templates:")
        for template in sorted(templates):
            print(f"  {template}")
        return 0

    elif args.command == "init-config":
        # Create a default configuration file in the current directory
        config_path = os.path.join(os.getcwd(), ".repokit.json")
        if os.path.exists(config_path):
            logger.error(f"Configuration file already exists at {config_path}")
            return 1

        config_manager.save_config(config_path)
        logger.info(f"Created default configuration at {config_path}")
        print(f"Created default configuration at {config_path}")
        print("Edit this file to customize your repository settings.")
        return 0

    elif args.command == "store-credentials":
        from .remote_integration import RemoteIntegration
        from .auth_integration import AuthenticationHandler

        if not args.publish_to:
            logger.error(
                "Please specify a service with --publish-to (github or gitlab)"
            )
            return 1

        if not args.token and not args.token_command:
            logger.error("Please provide either --token or --token-command")
            return 1

        auth_handler = AuthenticationHandler(verbose=args.verbose)

        # If token_command is provided, use it to get the token
        if args.token_command:
            token = auth_handler.get_token(args.publish_to, args.token_command)
            if not token:
                logger.error(
                    f"Failed to retrieve token using command: {args.token_command}"
                )
                return 1
        else:
            token = args.token

        # Store the credentials
        success = auth_handler.store_credentials(
            args.publish_to, token, args.organization, args.credentials_file
        )

        if success:
            logger.info(f"Successfully stored credentials for {args.publish_to}")
            print(f"Credentials stored successfully for {args.publish_to}")
            return 0
        else:
            logger.error(f"Failed to store credentials for {args.publish_to}")
            return 1

    elif args.command == "setup-guardrails":
        from .guardrails import setup_guardrails_command
        return setup_guardrails_command(args)

    elif args.command == "check-guardrails":
        from .guardrails import check_guardrails_command
        return check_guardrails_command(args)

    elif args.command == "safe-merge":
        from .guardrails import GuardrailsManager
        
        manager = GuardrailsManager()
        
        if args.preview:
            success = manager.safe_merge(args.source_branch, preview=True)
        else:
            success = manager.safe_merge(
                args.source_branch,
                no_commit=args.no_commit,
                no_ff=args.no_ff
            )
        
        return 0 if success else 1

    elif args.command == "safe-merge-dev":
        from .history_protection import HistoryProtectionManager
        
        # Get configuration for history protection
        history_config = config.get('history_protection', {})
        
        # Initialize manager
        manager = HistoryProtectionManager(
            repo_path=os.getcwd(),
            config=config,
            verbose=args.verbose
        )
        
        # Determine squash behavior
        squash = None
        if args.squash:
            squash = True
        elif args.no_squash:
            squash = False
        
        # Perform the merge
        success = manager.safe_merge_dev(
            branch=args.branch,
            target_branch=args.target,
            squash=squash,
            message=args.message,
            preserve_last=args.preserve_last,
            dry_run=args.preview
        )
        
        return 0 if success else 1

    elif args.command == "clean-history":
        from .history_cleaner import HistoryCleaner, CleaningConfig, CleaningRecipe, GitFilterRepoNotFound
        
        try:
            # Initialize cleaner
            cleaner = HistoryCleaner(repo_path=os.getcwd(), verbose=args.verbose)
            
            # Interactive mode if no recipe specified
            if not args.recipe and not args.remove_paths:
                # Analyze repository
                analysis = cleaner.analyze_repository()
                
                print("\n=== Repository Analysis ===")
                print(f"Total commits: {analysis['total_commits']}")
                print(f"Branches: {len(analysis['branches'])}")
                
                if analysis['private_paths']:
                    print(f"\nFound {len(analysis['private_paths'])} private files:")
                    for path in analysis['private_paths'][:10]:
                        print(f"  - {path}")
                    if len(analysis['private_paths']) > 10:
                        print(f"  ... and {len(analysis['private_paths']) - 10} more")
                
                if analysis['windows_issues']:
                    print(f"\nFound {len(analysis['windows_issues'])} Windows compatibility issues:")
                    for path in analysis['windows_issues'][:5]:
                        print(f"  - {path}")
                    if len(analysis['windows_issues']) > 5:
                        print(f"  ... and {len(analysis['windows_issues']) - 5} more")
                
                # Suggest recipe
                if analysis['private_paths']:
                    print("\n💡 Suggestion: Use --recipe pre-open-source to remove private files")
                if analysis['windows_issues']:
                    print("💡 Suggestion: Use --recipe windows-safe to fix Windows issues")
                
                return 0
            
            # Build configuration
            if args.recipe:
                recipe = CleaningRecipe(args.recipe)
                config = cleaner.get_recipe_config(recipe)
            else:
                config = CleaningConfig(recipe=CleaningRecipe.CUSTOM)
            
            # Override with command-line options
            if args.remove_paths:
                config.paths_to_remove = args.remove_paths
            if args.cutoff_sha:
                config.cutoff_sha = args.cutoff_sha
            if args.cutoff_date:
                config.cutoff_date = args.cutoff_date
            
            config.dry_run = args.dry_run
            config.force = args.force
            if args.no_backup:
                config.backup_location = 'skip'
            elif args.backup_location:
                config.backup_location = args.backup_location
            
            # Preview if requested
            if args.dry_run:
                preview = cleaner.preview_cleaning(config)
                print("\n=== Cleaning Preview ===")
                print(f"Recipe: {preview['recipe']}")
                if preview['paths_to_remove']:
                    print(f"Paths to remove: {', '.join(preview['paths_to_remove'])}")
                if preview['estimated_impact']:
                    print(f"Estimated impact: {preview['estimated_impact']}")
                if preview['warnings']:
                    print("\nWarnings:")
                    for warning in preview['warnings']:
                        print(f"  ⚠️  {warning}")
            
            # Execute cleaning
            success = cleaner.clean_history(config)
            return 0 if success else 1
            
        except GitFilterRepoNotFound as e:
            logger.error(str(e))
            print("\nTo install git filter-repo:")
            print("  pip install git-filter-repo")
            print("\nOr see: https://github.com/newren/git-filter-repo")
            return 1
        except Exception as e:
            logger.error(f"Error cleaning history: {str(e)}")
            if args.verbose >= 2:
                import traceback
                traceback.print_exc()
            return 1

    elif args.command == "manage-gitkeep":
        from .directory_profiles import DirectoryProfileManager
        
        try:
            # Resolve directory path
            directory = os.path.abspath(args.directory)
            if not os.path.exists(directory):
                logger.error(f"Directory does not exist: {directory}")
                return 1
            
            if not os.path.isdir(directory):
                logger.error(f"Path is not a directory: {directory}")
                return 1
            
            # Determine recursiveness (--no-recursive overrides default)
            recursive = args.recursive and not args.no_recursive
            
            # Initialize directory profile manager
            profile_manager = DirectoryProfileManager(verbose=args.verbose)
            
            if args.dry_run:
                logger.info(f"DRY RUN: Analyzing .gitkeep files in {directory} (recursive: {recursive})")
                
                # Create a temporary function to simulate the changes
                def simulate_manage_gitkeep(base_path: str, recursive: bool = True):
                    result = {"added": [], "removed": []}
                    
                    def process_directory(dir_path: str, relative_path: str = ""):
                        if not os.path.isdir(dir_path):
                            return
                            
                        gitkeep_path = os.path.join(dir_path, ".gitkeep")
                        gitkeep_exists = os.path.exists(gitkeep_path)
                        
                        try:
                            items = [item for item in os.listdir(dir_path) if item != ".gitkeep"]
                        except PermissionError:
                            return
                        
                        non_hidden_items = [item for item in items if not item.startswith(".")]
                        is_empty = len(non_hidden_items) == 0
                        
                        if is_empty and not gitkeep_exists:
                            result["added"].append(os.path.join(relative_path, ".gitkeep") if relative_path else ".gitkeep")
                        elif not is_empty and gitkeep_exists:
                            result["removed"].append(os.path.join(relative_path, ".gitkeep") if relative_path else ".gitkeep")
                            
                        if recursive:
                            for item in items:
                                item_path = os.path.join(dir_path, item)
                                if os.path.isdir(item_path) and not item.startswith("."):
                                    item_relative = os.path.join(relative_path, item) if relative_path else item
                                    process_directory(item_path, item_relative)
                    
                    process_directory(base_path)
                    return result
                
                result = simulate_manage_gitkeep(directory, recursive)
            else:
                # Actually manage the .gitkeep files
                logger.info(f"Managing .gitkeep files in {directory} (recursive: {recursive})")
                result = profile_manager.manage_gitkeep_files(directory, recursive)
            
            # Report results
            if result["added"]:
                if args.dry_run:
                    print(f"\nWould ADD .gitkeep files to {len(result['added'])} empty directories:")
                else:
                    print(f"\nADDED .gitkeep files to {len(result['added'])} empty directories:")
                for file_path in result["added"]:
                    print(f"  + {file_path}")
            
            if result["removed"]:
                if args.dry_run:
                    print(f"\nWould REMOVE .gitkeep files from {len(result['removed'])} non-empty directories:")
                else:
                    print(f"\nREMOVED .gitkeep files from {len(result['removed'])} non-empty directories:")
                for file_path in result["removed"]:
                    print(f"  - {file_path}")
            
            if not result["added"] and not result["removed"]:
                print("\nNo .gitkeep file changes needed.")
            else:
                total_changes = len(result["added"]) + len(result["removed"])
                if args.dry_run:
                    print(f"\nDry run complete. {total_changes} changes would be made.")
                else:
                    print(f"\nManagement complete. {total_changes} changes made.")
            
            return 0
            
        except Exception as e:
            logger.error(f"Error managing .gitkeep files: {str(e)}")
            if args.verbose >= 2:
                import traceback
                traceback.print_exc()
            return 1

    elif args.command == "analyze-history":
        from .history_cleaner import HistoryCleaner, GitFilterRepoNotFound
        
        try:
            # Initialize cleaner
            cleaner = HistoryCleaner(repo_path=os.getcwd(), verbose=args.verbose)
            
            # Analyze repository
            analysis = cleaner.analyze_repository()
            
            print("\n=== Repository History Analysis ===")
            print(f"Repository: {os.getcwd()}")
            print(f"Total commits: {analysis['total_commits']}")
            print(f"Branches: {', '.join(analysis['branches'][:5])}")
            if len(analysis['branches']) > 5:
                print(f"         ... and {len(analysis['branches']) - 5} more")
            
            # Private paths
            if analysis['private_paths']:
                print(f"\n🔒 Private/Sensitive Paths ({len(analysis['private_paths'])} found):")
                by_type = {}
                for path in analysis['private_paths']:
                    if path.startswith('private/'):
                        by_type.setdefault('private/', []).append(path)
                    elif path.startswith('logs/'):
                        by_type.setdefault('logs/', []).append(path)
                    elif path == 'CLAUDE.md':
                        by_type.setdefault('AI files', []).append(path)
                    else:
                        by_type.setdefault('other', []).append(path)
                
                for type_name, paths in by_type.items():
                    print(f"\n  {type_name}: {len(paths)} files")
                    for path in paths[:3]:
                        print(f"    - {path}")
                    if len(paths) > 3:
                        print(f"    ... and {len(paths) - 3} more")
            
            # Windows issues
            if analysis['windows_issues']:
                print(f"\n⚠️  Windows Compatibility Issues ({len(analysis['windows_issues'])} found):")
                for path in analysis['windows_issues'][:5]:
                    print(f"  - {path}")
                if len(analysis['windows_issues']) > 5:
                    print(f"  ... and {len(analysis['windows_issues']) - 5} more")
            
            # Recommendations
            print("\n📋 Recommendations:")
            if analysis['private_paths']:
                print("  1. Remove private files with: repokit clean-history --recipe pre-open-source")
            if analysis['windows_issues']:
                print("  2. Fix Windows issues with: repokit clean-history --recipe windows-safe")
            if not analysis['private_paths'] and not analysis['windows_issues']:
                print("  ✅ No sensitive data detected!")
            
            print("\n💡 Tip: Use --dry-run to preview changes before cleaning")
            
            return 0
            
        except GitFilterRepoNotFound as e:
            logger.error(str(e))
            print("\nTo install git filter-repo:")
            print("  pip install git-filter-repo")
            return 1
        except Exception as e:
            logger.error(f"Error analyzing history: {str(e)}")
            if args.verbose >= 2:
                import traceback
                traceback.print_exc()
            return 1

    elif args.command == "bootstrap":
        bootstrap_script = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "scripts", "bootstrap.py"
        )

        if not os.path.exists(bootstrap_script):
            logger.error(f"Bootstrap script not found at {bootstrap_script}")
            return 1

        # Build arguments for bootstrap script
        bootstrap_args = [sys.executable, bootstrap_script]

        # Pass through relevant arguments
        if args.name:
            bootstrap_args.extend(["--name", args.name])

        if args.publish_to:
            bootstrap_args.extend(["--service", args.publish_to])

        if args.private_repo:
            bootstrap_args.append("--private")

        if args.organization:
            bootstrap_args.extend(["--organization", args.organization])

        if args.output:
            bootstrap_args.extend(["--config-path", args.output])

        if args.no_push:
            bootstrap_args.append("--no-publish")

        if args.user_name:
            bootstrap_args.extend(["--git-user-name", args.user_name])

        if args.user_email:
            bootstrap_args.extend(["--git-user-email", args.user_email])

        # Add verbosity flags
        for _ in range(args.verbose):
            bootstrap_args.append("-v")

        # Execute the bootstrap script
        logger.info(f"Running bootstrap script: {' '.join(bootstrap_args)}")

        try:
            # Use subprocess.run for better control over encoding
            result = subprocess.run(bootstrap_args, encoding='utf-8', errors='replace')
            exit_code = result.returncode
            return exit_code
        except Exception as e:
            logger.error(f"Error running bootstrap script: {str(e)}")
            return 1

    elif args.command == "analyze":
        if not args.name:
            logger.error("Directory path is required for 'analyze' command")
            return 1

        try:
            # Analyze the directory
            dir_path = os.path.abspath(args.name)
            if not os.path.exists(dir_path):
                logger.error(f"Directory not found: {dir_path}")
                return 1

            # Use comprehensive project analysis
            summary = analyze_project(dir_path, verbose=args.verbose)

            # Display the enhanced analysis results
            print(f"\n=== PROJECT ANALYSIS: {dir_path} ===")
            print(f"  Project type: {summary['project_type']}")
            print(f"  Detected language: {summary['detected_language']}")
            print(f"  Migration complexity: {summary['migration_complexity']}")
            print(f"  Recommended strategy: {summary['recommended_strategy']}")
            print(
                f"  Recommended branch strategy: {summary['recommended_branch_strategy']}"
            )

            # Git state information
            git_state = summary.get("git_state", {})
            if git_state.get("is_repo"):
                print(f"\n  Git repository:")
                print(
                    f"    Current branch: {git_state.get('current_branch', 'Unknown')}"
                )
                print(f"    Branches: {', '.join(git_state.get('branches', []))}")
                print(
                    f"    Has uncommitted changes: {'Yes' if git_state.get('has_uncommitted_changes') else 'No'}"
                )
                print(
                    f"    Remotes: {', '.join(git_state.get('remotes', {}).keys()) or 'None'}"
                )
                print(f"    Branch strategy: {summary['branch_strategy']}")
            else:
                print(f"  Git repository: No")

            # Directory structure
            print(f"\n  Directory structure:")
            print(
                f"    Existing standard directories: {', '.join(summary['existing_dirs']) or 'None'}"
            )
            print(
                f"    Missing standard directories: {', '.join(summary['missing_dirs']) or 'None'}"
            )
            print(
                f"    Special directories: {', '.join(summary['special_dirs']) or 'None'}"
            )
            print(
                f"    Has template conflicts: {'Yes' if summary['has_template_conflicts'] else 'No'}"
            )

            # File information
            print(f"\n  File counts:")
            for category, count in summary["file_counts"].items():
                if count > 0:
                    print(f"    {category}: {count}")
            print(f"    Total: {summary['total_files']}")

            # Migration recommendations
            print(f"\n  Migration steps:")
            for i, step in enumerate(summary["migration_steps"], 1):
                print(f"    {i}. {step}")

            # Command suggestions
            print(f"\n=== NEXT STEPS ===")
            if summary["project_type"] == "repokit":
                print("  Project is already using RepoKit structure.")
            elif summary["project_type"] == "empty":
                print("  Create new RepoKit project:")
                print(
                    f"    repokit create {os.path.basename(dir_path)} --language {summary['detected_language']}"
                )
            else:
                print("  Migrate to RepoKit structure:")
                print(
                    f"    repokit migrate {args.name} --migration-strategy {summary['recommended_strategy']}"
                )
                print("  Or adopt in-place:")
                print(
                    f"    repokit adopt {args.name} --strategy {summary['recommended_strategy']}"
                )
                if getattr(args, "publish_to", None):
                    print(f"  With publishing:")
                    print(
                        f"    repokit adopt {args.name} --publish-to {args.publish_to}"
                    )

            return 0
        except Exception as e:
            logger.error(f"Error analyzing directory: {str(e)}")
            if args.verbose >= 2:
                import traceback

                traceback.print_exc()
            return 1

    elif args.command == "migrate":
        if not args.name:
            logger.error("Directory path is required for 'migrate' command")
            return 1

        try:
            # Analyze and migrate the directory
            dir_path = os.path.abspath(args.name)
            if not os.path.exists(dir_path):
                logger.error(f"Directory not found: {dir_path}")
                return 1

            # First show the analysis
            summary = analyze_directory(dir_path, verbose=args.verbose)

            print(f"\nAnalysis of {dir_path}:")
            print(
                f"  Existing standard directories: {', '.join(summary['existing_dirs']) or 'None'}"
            )
            print(
                f"  Missing standard directories: {', '.join(summary['missing_dirs']) or 'None'}"
            )
            print(
                f"  Special directories: {', '.join(summary['special_dirs']) or 'None'}"
            )
            print(
                f"  Has Git repository: {'Yes' if summary['has_git_repository'] else 'No'}"
            )
            print(
                f"  Has template conflicts: {'Yes' if summary['has_template_conflicts'] else 'No'}"
            )

            # Get migration plan
            plan = plan_migration(
                dir_path, strategy=args.migration_strategy, verbose=args.verbose
            )

            # Show migration plan
            print("\nMigration plan:")
            print(f"  Strategy: {plan['strategy']}")
            print(
                f"  Directories to create: {', '.join(plan['create_dirs']) or 'None'}"
            )

            for dirname, info in plan["special_dirs"].items():
                print(f"  Special directory '{dirname}': {info['action']}")

            for template_dir, info in plan["template_conflicts"].items():
                print(
                    f"  Template conflicts in '{template_dir}' ({info['conflicts']} files): {info['action']}"
                )

            # Create backup if requested
            if hasattr(args, 'backup') and args.backup and not args.dry_run:
                import shutil
                import datetime
                
                # Determine backup location
                if hasattr(args, 'backup_location') and args.backup_location:
                    backup_path = os.path.abspath(args.backup_location)
                else:
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_path = os.path.abspath(f"{os.path.basename(dir_path)}_backup_{timestamp}")
                
                try:
                    print(f"\nCreating backup at: {backup_path}")
                    shutil.copytree(dir_path, backup_path, symlinks=True)
                    print(f"✓ Backup created successfully")
                except Exception as e:
                    logger.error(f"Failed to create backup: {str(e)}")
                    return 1

            # Confirm migration
            if not args.dry_run and not args.quiet:
                confirm = input("\nProceed with migration? [y/N]: ")
                if confirm.lower() != "y":
                    print("Migration cancelled.")
                    return 0

            # Execute migration
            success = migrate_directory(
                dir_path,
                strategy=args.migration_strategy,
                dry_run=args.dry_run,
                verbose=args.verbose,
            )

            if success:
                msg = (
                    "Migration analysis completed (dry run)"
                    if args.dry_run
                    else "Migration completed successfully"
                )
                print(f"\n{msg}")
                print("\nNext steps:")

                if summary["has_git_repository"]:
                    print("  - Your directory already has a Git repository.")
                    print("  - You may want to update templates and configuration.")
                else:
                    print("  - Initialize a Git repository (if not already done):")
                    print("    git init")
                    print("  - Set up your initial branches:")
                    print("    git branch dev")
                    print("    git branch staging")
                    print("    git branch test")
                    print("    git branch live")

                if args.publish_to:
                    print(f"  - Publish to {args.publish_to}:")
                    print(
                        f"    repokit publish {dir_path} --publish-to {args.publish_to}"
                    )

                return 0
            else:
                logger.error("Migration failed.")
                return 1
        except Exception as e:
            logger.error(f"Error migrating directory: {str(e)}")
            if args.verbose >= 2:
                import traceback

                traceback.print_exc()
            return 1

    elif args.command == "adopt":
        # Use current directory if no name provided
        dir_path = os.path.abspath(args.name) if args.name else os.getcwd()

        if not os.path.exists(dir_path):
            logger.error(f"Directory not found: {dir_path}")
            return 1

        try:
            # Update configuration with adopt-specific options
            adopt_config = config.copy()
            
            # Set repo name based on --repo-name or directory name
            repo_name = getattr(args, 'repo_name', None) or os.path.basename(dir_path)
            adopt_config["name"] = repo_name
            
            # Override language if specified
            if hasattr(args, 'language') and args.language:
                adopt_config["language"] = args.language
            if getattr(args, "with_layers", None):
                from .layers import parse_languages as _parse
                adopt_config["with"] = _parse(args.with_layers)
            if getattr(args, "license", None):
                adopt_config["license"] = args.license

            # Override description if specified
            if hasattr(args, 'description') and args.description:
                adopt_config["description"] = args.description
            
            # Merge adoption-specific sensitive patterns (CLI args + config file)
            if hasattr(args, 'sensitive_patterns') and args.sensitive_patterns:
                # Get existing patterns from config file
                existing_patterns = adopt_config.get("sensitive_patterns", [])
                # Add CLI patterns
                cli_patterns = [pattern.strip() for pattern in args.sensitive_patterns.split(",")]
                # Merge and deduplicate
                adopt_config["sensitive_patterns"] = list(set(existing_patterns + cli_patterns))
            
            # Merge adoption-specific private directories (CLI args + config file)
            if hasattr(args, 'private_dirs') and args.private_dirs:
                # Get existing private dirs from config file
                existing_dirs = adopt_config.get("private_dirs", [])
                # Add CLI dirs
                cli_dirs = [dir_name.strip() for dir_name in args.private_dirs.split(",")]
                # Merge and deduplicate
                adopt_config["private_dirs"] = list(set(existing_dirs + cli_dirs))

            # First analyze the project
            summary = analyze_project(dir_path, verbose=args.verbose)

            print(f"\n=== ADOPTING PROJECT: {dir_path} ===")
            print(f"  Project type: {summary['project_type']}")
            print(f"  Detected language: {summary['detected_language']}")
            print(f"  Migration complexity: {summary['migration_complexity']}")

            # Check if already RepoKit
            if summary["project_type"] == "repokit":
                print("  Project is already using RepoKit structure.")
                if not args.publish_to:
                    return 0

            # Warn about uncommitted changes
            git_state = summary.get("git_state", {})
            if git_state.get("has_uncommitted_changes"):
                print("  WARNING: Uncommitted changes detected!")
                if not args.dry_run and not args.quiet:
                    confirm = input(
                        "  Continue with adoption? Changes should be committed first. [y/N]: "
                    )
                    if confirm.lower() != "y":
                        print("  Adoption cancelled.")
                        return 0

            # Determine strategies
            strategy = (
                args.migration_strategy
                if hasattr(args, "migration_strategy")
                else summary["recommended_strategy"]
            )
            branch_strategy = getattr(args, "branch_strategy", None)
            if not branch_strategy:
                branch_strategy = summary["recommended_branch_strategy"]

            print(f"  Using migration strategy: {strategy}")
            print(f"  Using branch strategy: {branch_strategy}")

            if args.dry_run:
                print(f"  DRY RUN - No changes will be made")

            # Create backup if requested
            if hasattr(args, 'backup') and args.backup and not args.dry_run:
                import shutil
                import datetime
                
                # Determine backup location
                if hasattr(args, 'backup_location') and args.backup_location:
                    backup_path = os.path.abspath(args.backup_location)
                else:
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_path = os.path.abspath(f"{os.path.basename(dir_path)}_backup_{timestamp}")
                
                try:
                    print(f"  Creating backup at: {backup_path}")
                    shutil.copytree(dir_path, backup_path, symlinks=True)
                    print(f"  ✓ Backup created successfully")
                except Exception as e:
                    logger.error(f"Failed to create backup: {str(e)}")
                    return 1

            # Clean history if requested
            if hasattr(args, 'clean_history') and args.clean_history and not args.dry_run:
                try:
                    from .history_cleaner import HistoryCleaner, CleaningConfig, CleaningRecipe, GitFilterRepoNotFound
                    
                    print(f"  Cleaning repository history using '{args.cleaning_recipe}' recipe...")
                    
                    # Initialize cleaner
                    cleaner = HistoryCleaner(repo_path=dir_path, verbose=args.verbose)
                    
                    # Build cleaning config using default settings
                    recipe_map = {
                        "pre-open-source": CleaningRecipe.PRE_OPEN_SOURCE,
                        "windows-safe": CleaningRecipe.WINDOWS_SAFE, 
                        "remove-secrets": CleaningRecipe.REMOVE_SECRETS
                    }
                    
                    # Get default config for the recipe
                    recipe_enum = recipe_map[args.cleaning_recipe]
                    config = cleaner.get_recipe_config(recipe_enum)
                    
                    # Override with adopt-specific settings
                    config.backup_location = f"{backup_path}_pre_clean" if 'backup_path' in locals() else None
                    config.dry_run = False
                    config.force = True  # Skip confirmation prompts during adopt
                    
                    # Execute history cleaning
                    success = cleaner.clean_history(config)
                    if not success:
                        logger.error("History cleaning failed - aborting adoption")
                        return 1
                    
                    print(f"  ✓ Repository history cleaned successfully")
                    
                except GitFilterRepoNotFound as e:
                    logger.error(str(e))
                    print("\nTo install git filter-repo:")
                    print("  pip install git-filter-repo")
                    print("\nOr see: https://github.com/newren/git-filter-repo")
                    return 1
                except Exception as e:
                    logger.error(f"Failed to clean history: {str(e)}")
                    return 1

            # Execute adoption using enhanced RepoManager approach
            # Use RepoManager for non-repokit projects OR when publishing/templates are needed
            if (summary["project_type"] != "repokit" or args.publish_to):
                if args.dry_run:
                    print(f"\n=== DRY RUN MODE - No changes will be made ===")
                    print(f"Would execute RepoManager setup_repository() for:")
                    print(f"  Project: {repo_name}")
                    print(f"  Path: {dir_path}")
                    print(f"  Language: {adopt_config.get('language', 'generic')}")
                    print(f"  Branch strategy: {adopt_config.get('branch_strategy', 'standard')}")
                    publish_to = getattr(args, 'publish_to', None) or adopt_config.get('publish_to')
                    print(f"  Would publish to: {publish_to if publish_to else 'none'}")
                    print(f"  Would create backup: {hasattr(args, 'backup') and args.backup}")
                    print(f"  Would clean history: {hasattr(args, 'clean_history') and args.clean_history}")
                    
                    # Show what sensitive file cleanup would do
                    from .defaults import DEFAULT_SENSITIVE_PATTERNS
                    print(f"\nWould clean files matching these patterns:")
                    for pattern in DEFAULT_SENSITIVE_PATTERNS[:5]:
                        print(f"  - {pattern}")
                    if len(DEFAULT_SENSITIVE_PATTERNS) > 5:
                        print(f"  ... and {len(DEFAULT_SENSITIVE_PATTERNS) - 5} more patterns")
                    
                    print(f"\n=== DRY RUN COMPLETE - No actual changes made ===")
                    return 0
                # Initialize RepoManager with the merged configuration for in-place adoption
                adopt_config["name"] = repo_name
                # Set preserve_existing flag for adoption to avoid overwriting project files
                adopt_config["preserve_existing"] = True
                adopt_config["is_adoption"] = True  # Flag to indicate this is an adoption
                
                # Debug: Log final adopt_config
                logger.debug(f"Final adopt_config before RepoManager: {adopt_config}")
                logger.debug(f"Sensitive patterns in adopt_config: {adopt_config.get('sensitive_patterns', 'NOT FOUND')}")
                
                repo_manager = RepoManager(
                    adopt_config, templates_dir=getattr(args, 'templates_dir', None), verbose=args.verbose
                )
                
                # Override the project_root and repo_root to adopt in-place
                repo_manager.project_root = os.path.dirname(dir_path)
                repo_manager.repo_root = dir_path
                # Fix github_root path after override to ensure proper template deployment
                repo_manager.github_root = os.path.join(repo_manager.project_root, "github")
                
                # Set up repository structure (this will add missing RepoKit structure)
                success = repo_manager.setup_repository()
                if not success:
                    logger.error("Failed to set up RepoKit structure")
                    return 1
            else:
                # Use the simple adopt_project for dry runs or already RepoKit projects
                success = adopt_project(
                    directory=dir_path,
                    strategy=strategy,
                    branch_strategy=branch_strategy,
                    publish_to=args.publish_to,
                    dry_run=args.dry_run,
                    verbose=args.verbose,
                )
                if not success:
                    logger.error("Project adoption failed.")
                    return 1

            # Handle remote publishing if requested (from CLI args or config file)
            publish_to = getattr(args, 'publish_to', None) or adopt_config.get('publish_to')
            if publish_to and not args.dry_run:
                from .remote_integration import RemoteIntegration
                
                # Update configuration for remote publishing
                organization = getattr(args, 'organization', None) or adopt_config.get('organization')
                if organization:
                    if publish_to == "github":
                        adopt_config.setdefault("github", {})["organization"] = organization
                    else:
                        adopt_config.setdefault("gitlab", {})["group"] = organization

                # Initialize RepoManager for publishing (if not already done)
                if summary["project_type"] == "repokit":
                    repo_manager = RepoManager(
                        adopt_config, templates_dir=getattr(args, 'templates_dir', None), verbose=args.verbose
                    )
                    repo_manager.project_root = os.path.dirname(dir_path)
                    repo_manager.repo_root = dir_path

                remote_integration = RemoteIntegration(
                    repo_manager,
                    credentials_file=getattr(args, 'credentials_file', None),
                    verbose=args.verbose,
                )

                # Handle token - if direct token provided, create a command that echoes it
                token_cmd = getattr(args, 'token_command', None)
                if hasattr(args, 'token') and args.token and not token_cmd:
                    token_cmd = f"echo {args.token}"

                publish_success = remote_integration.setup_remote_repository(
                    service=publish_to,
                    remote_name=getattr(args, 'remote_name', None) or adopt_config.get('remote_name', 'origin'),
                    private=getattr(args, 'private_repo', None) or adopt_config.get('private_repo', False),
                    push_branches=not getattr(args, 'no_push', False),
                    organization=organization,
                    token_command=token_cmd,
                )

                if not publish_success:
                    logger.error(f"Failed to publish repository to {publish_to}")
                    return 1

                logger.info(f"Successfully published repository to {publish_to}")

            if args.dry_run:
                print(f"\nAdoption analysis completed (dry run)")
            else:
                print(f"\nProject adopted successfully!")

                print("\nNext steps:")
                print(f"  - Your project now uses RepoKit structure")
                print(f"  - Check the generated templates and configuration")
                print(f"  - Commit any new files to your repository")

                if publish_to:
                    print(f"  - Repository has been published to {publish_to}")
                elif not git_state.get("remotes"):
                    print(f"  - Consider publishing to a remote service:")
                    print(f"    repokit publish {dir_path} --publish-to github")

            return 0

        except Exception as e:
            logger.error(f"Error adopting project: {str(e)}")
            if args.verbose >= 2:
                import traceback

                traceback.print_exc()
            return 1

    elif args.command == "create":
        if not args.name:
            logger.error("Repository name is required for 'create' command")
            return 1

        # The code-type names are checked here, before a folder or a repository
        # exists: an unknown language or archetype, or a stub that is not built
        # yet, stops with the known names.
        from . import layers as _layers
        from .template_engine import TemplateEngine as _TemplateEngine
        try:
            _root = _layers.layers_root(_TemplateEngine(templates_dir=args.templates_dir))
            if _root is not None:
                _layers.resolve(_layers.load_manifest(_root),
                                config.get("languages") or [config.get("language") or _layers.GENERIC],
                                config.get("with"))
            elif config.get("with"):
                raise _layers.LayerError("no code-type layers found with the templates, so --with cannot be used")
        except _layers.LayerError as e:
            logger.error(str(e))
            return 1

        # The GitHub login, before any file is written: the files' URLs,
        # CODEOWNERS and FUNDING name it (0.9.6; before, they carried the
        # YOUR_GITHUB_USERNAME placeholder even with --github)
        if getattr(args, "github", False) and not args.no_push:
            from .github_create import gh_login
            config["github_create"] = True
            login = gh_login(os.getcwd())
            if login:
                config["github_login"] = login

        try:
            # Initialize RepoManager with the merged configuration
            repo_manager = RepoManager(
                config, templates_dir=args.templates_dir, verbose=args.verbose
            )

            # Set up repository
            success = repo_manager.setup_repository()
            if not success:
                return 1

            # GitHub through gh (its login, no token here)
            if getattr(args, "github", False):
                if args.no_push:
                    logger.info("--github with --no-push: nothing created on GitHub")
                else:
                    from .github_create import create_on_github
                    setup_report: list = []
                    # repo_manager.config carries what the create settled
                    # (the archetype, the extras) beside the person's settings
                    problem = create_on_github(
                        repo_manager.repo_root, repo_manager.project_name, repo_manager.config,
                        repo_manager.private_branch, organization=args.organization,
                        public=getattr(args, "public", False), logger=logger,
                        report=setup_report,
                    )
                    for line in setup_report:
                        print(f"GitHub: {line}")
                    if problem:
                        logger.error(f"GitHub: {problem}")
                        logger.error("The local repository is complete; retry with gh once fixed.")
                        return 1

            # Publish to remote if requested
            if args.publish_to:
                # --token reaches the token lookup through its environment variable
                if getattr(args, "token", None):
                    os.environ[f"{args.publish_to.upper()}_TOKEN"] = args.token
                from .remote_integration import RemoteIntegration

                remote_integration = RemoteIntegration(
                    repo_manager,
                    credentials_file=args.credentials_file,
                    verbose=args.verbose,
                )

                publish_success = remote_integration.setup_remote_repository(
                    service=args.publish_to,
                    remote_name=args.remote_name,
                    private=args.private_repo,
                    push_branches=not args.no_push,
                    organization=args.organization,
                    token_command=args.token_command,
                )

                if not publish_success:
                    logger.error(f"Failed to publish repository to {args.publish_to}")
                    return 1

                logger.info(f"Successfully published repository to {args.publish_to}")

            return 0
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            if args.verbose >= 2:
                import traceback

                traceback.print_exc()
            return 1

    elif args.command == "publish":
        if not args.name:
            logger.error("Repository path is required for 'publish' command")
            return 1

        if not args.publish_to:
            logger.error("--publish-to is required for 'publish' command")
            return 1

        try:
            # Use the provided path as the repository root
            repo_path = os.path.abspath(args.name)
            if not os.path.exists(repo_path):
                logger.error(f"Repository not found at {repo_path}")
                return 1

            # Update configuration with the correct path and name
            repo_name = args.repo_name if args.repo_name else os.path.basename(repo_path)
            config["name"] = repo_name

            # Initialize RepoManager with the repository path
            repo_manager = RepoManager(
                config, templates_dir=args.templates_dir, verbose=args.verbose
            )

            # Override the project_root and repo_root
            repo_manager.project_root = os.path.dirname(repo_path)
            repo_manager.repo_root = repo_path

            # Publish to remote
            from .remote_integration import RemoteIntegration

            remote_integration = RemoteIntegration(
                repo_manager,
                credentials_file=args.credentials_file,
                verbose=args.verbose,
            )

            # Handle token - if direct token provided, create a command that echoes it
            token_cmd = args.token_command
            if args.token and not token_cmd:
                token_cmd = f"echo {args.token}"
            
            publish_success = remote_integration.setup_remote_repository(
                service=args.publish_to,
                remote_name=args.remote_name,
                private=args.private_repo,
                push_branches=not args.no_push,
                organization=args.organization,
                token_command=token_cmd,
                include_branches=getattr(args, 'include_branches', None),
                exclude_branches=getattr(args, 'exclude_branches', None),
            )

            if not publish_success:
                logger.error(f"Failed to publish repository to {args.publish_to}")
                return 1

            logger.info(f"Successfully published repository to {args.publish_to}")
            return 0
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            if args.verbose >= 2:
                import traceback

                traceback.print_exc()
            return 1

    # Unknown command (should not happen due to choices in argparse)
    logger.error(f"Unknown command: {args.command}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
