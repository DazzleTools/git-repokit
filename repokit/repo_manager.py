#!/usr/bin/env python3
"""
RepoKit: Repository Template Generator

Core repository manager that handles repository initialization,
branch creation, worktree setup, and template generation.
"""

import os
import subprocess
import json
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

from .template_engine import TemplateEngine
from .defaults import (
    DEFAULT_PRIVATE_DIRS, DEFAULT_SENSITIVE_FILES, DEFAULT_SENSITIVE_PATTERNS,
    DEFAULT_PRIVATE_BRANCHES, DEFAULT_PUBLIC_BRANCHES, 
    DEFAULT_PRIVATE_PATTERNS, DEFAULT_EXCLUDE_FROM_PUBLIC
)


class RepoManager:
    """Manages repository setup and configuration."""

    def __init__(
        self,
        config: Dict[str, Any],
        templates_dir: Optional[str] = None,
        verbose: int = 0,
    ):
        """
        Initialize the repository manager.

        Args:
            config: Dictionary containing repository configuration
            templates_dir: Optional path to custom templates directory
            verbose: Verbosity level (0=normal, 1=info, 2=debug)
        """
        self.config = config
        self.verbose = verbose
        self.project_name = config.get("name")
        self.project_root = os.path.abspath(self.project_name)

        # The private branch, or None when the strategy has none (main-only).
        # Only a missing key falls back to the legacy "private".
        self.private_branch = config.get("private_branch", "private")

        # How private work is kept: "nested" (private/ is its own repository)
        # or "branch" (on the private branch only). The default follows the
        # strategy, so a private-branch strategy alone behaves as it always did.
        self.private_mode = config.get("private_mode") or (
            "nested" if not self.private_branch else "branch"
        )

        # Vendor git-repokit-common (hooks and tools) into the project: on by
        # default for main-only, opt-in for the private-branch strategies.
        with_common = config.get("with_common")
        self.with_common = (not self.private_branch) if with_common is None else bool(with_common)
        self.common_vendored = False

        if self.private_branch is None and not config.get("worktrees"):
            # Flat layout: the repository is <name>/ itself, one branch,
            # no worktrees beside it.
            self.repo_root = self.project_root
            self.github_root = None
        else:
            # Legacy layout: <name>/local is the repository (on the private
            # branch) and <name>/github holds the main worktree.
            self.repo_root = os.path.join(self.project_root, "local")
            self.github_root = os.path.join(self.project_root, "github")

        # Get logger for repokit
        self.logger = logging.getLogger("repokit")

        # Initialize template engine with same verbosity
        self.template_engine = TemplateEngine(
            templates_dir=templates_dir, verbose=verbose
        )

    def run_git(
        self, args: List[str], cwd: Optional[str] = None, check: bool = True
    ) -> Optional[str]:
        """
        Run a git command and return its output.

        Args:
            args: List of git command arguments
            cwd: Working directory for the command
            check: Whether to check for command success

        Returns:
            Command output as string
        """
        cwd = cwd or self.repo_root
        cmd = ["git"] + args

        if self.verbose >= 2:
            self.logger.debug(f"Running: {' '.join(cmd)} in {cwd}")

        try:
            # Set environment for proper encoding on Windows
            env = os.environ.copy()
            if os.name == 'nt':  # Windows
                env['LANG'] = 'C.UTF-8'
                env['LC_ALL'] = 'C.UTF-8'
            
            result = subprocess.run(
                cmd, cwd=cwd, check=check, capture_output=True, text=True,
                encoding='utf-8', errors='replace', env=env
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Git command failed: {e.stderr}")
            if check:
                raise
            return None

    def setup_repository(self) -> bool:
        """
        Set up the repository structure according to configuration.

        Returns:
            True if successful, False otherwise
        """
        try:
            self.logger.info(f"Setting up repository: {self.project_name}")

            # Create project directory structure
            self._create_directory_structure()

            # Initialize git repositories
            self._init_git_repos()

            # Set up branches
            self._setup_branches()

            # git-repokit-common: vendored while the tree is still clean (one
            # commit), so in the private-branch model the public branches cut
            # later inherit it. Its hooks are installed at the end.
            if self.with_common and not self.config.get("is_adoption", False):
                self._vendor_repokit_common()

            # Set up private content protection BEFORE any commits
            # This is critical to prevent private content from reaching public branches
            self._setup_protection()

            # Nested mode: private/ becomes its own repository, ignored by this one
            if self.private_mode == "nested":
                from .vault import init_private_repo
                if not init_private_repo(self.repo_root, self.project_name, self.logger):
                    raise RuntimeError("could not create the private repository in private/")

            # Generate template files
            self._generate_template_files()

            # The language templates rewrite .gitignore; put the vault's lines back
            if self.private_mode == "nested":
                from .vault import ensure_parent_ignores
                ensure_parent_ignores(self.repo_root)

            # Create initial commit
            self._create_initial_commit()

            # Generate AI integration files if requested (only in private branch, after initial commit)
            if self.config.get("ai_integration"):
                self._generate_ai_templates()

            # Manage .gitkeep files for adopted repositories (but don't cleanup sensitive files here)
            # Sensitive file cleanup now happens during public branch creation in _create_clean_public_branch
            if self.config.get("is_adoption", False):
                gitkeep_results = self.manage_gitkeep_files()
                self.logger.info(f"Managed .gitkeep files: {len(gitkeep_results.get('added', []))} added, {len(gitkeep_results.get('removed', []))} removed")
                # Note: Sensitive file cleanup now happens during public branch creation

            # Set up worktrees AFTER initial commits and branch updates
            # This is the key change - moved worktree setup to the end
            self._setup_worktrees()

            # Nested mode: every worktree reaches the real private/ through a link
            if self.private_mode == "nested":
                self._link_private_into_worktrees()

            # Set up local exclude patterns for branch-conditional ignoring
            self._setup_local_excludes()

            # Set up GitHub integration (copy files to GitHub worktree)
            self._setup_github_integration()

            # repokit-common's hooks, last, so create's own commits never run them
            if self.common_vendored:
                from .common_kit import install_hooks
                problem = install_hooks(self.repo_root)
                if problem:
                    self.logger.warning(f"repokit-common hooks not installed: {problem}")
                    self.logger.warning("Run: sh scripts/repokit-common/install-hooks.sh")

            # Generate RepoKit configuration file with signature
            self._generate_repokit_config()

            self.logger.info(f"Repository setup complete: {self.project_name}")
            self._print_next_steps()

            return True
        except Exception as e:
            self.logger.error(f"Error setting up repository: {str(e)}")
            if self.verbose >= 2:
                import traceback

                traceback.print_exc()
            return False

    def _create_directory_structure(self) -> None:
        """Create the basic directory structure."""
        self.logger.info("Creating directory structure")

        # Create main project directory
        os.makedirs(self.project_root, exist_ok=True)

        # Create local repository directory
        os.makedirs(self.repo_root, exist_ok=True)

        # Create github directory for worktree (legacy layout only)
        if self.github_root:
            os.makedirs(self.github_root, exist_ok=True)

        # Create standard subdirectories
        standard_dirs = self.config.get(
            "directories",
            ["convos", "docs", "logs", "private", "revisions", "scripts", "tests"],
        )

        for directory in standard_dirs:
            dir_path = os.path.join(self.repo_root, directory)
            os.makedirs(dir_path, exist_ok=True)

            # .gitkeep files will be managed properly by manage_gitkeep_files() method
            # which checks if directories are actually empty before adding .gitkeep

    def manage_gitkeep_files(self, recursive: bool = True) -> Dict[str, List[str]]:
        """
        Manage .gitkeep files in the repository.
        
        Args:
            recursive: Whether to process subdirectories recursively
            
        Returns:
            Dictionary with added and removed .gitkeep files
        """
        from .directory_profiles import DirectoryProfileManager
        
        profile_manager = DirectoryProfileManager(verbose=self.verbose)
        
        # Manage .gitkeep files in the local repo
        result = profile_manager.manage_gitkeep_files(self.repo_root, recursive)
        
        self.logger.info(f"Managed .gitkeep files: {len(result['added'])} added, {len(result['removed'])} removed")
        return result

    def _get_git_version(self):
        """Get git version for feature compatibility."""
        try:
            import re
            import subprocess
            version_output = subprocess.check_output(['git', '--version'], text=True, encoding='utf-8', errors='replace')
            # Parse "git version 2.34.1" -> (2, 34, 1)
            match = re.search(r'git version (\d+)\.(\d+)\.(\d+)', version_output)
            if match:
                return tuple(map(int, match.groups()))
            return (0, 0, 0)  # Fallback for unparseable versions
        except Exception:
            return (0, 0, 0)  # Fallback for missing git

    def _supports_initial_branch(self):
        """Check if git supports --initial-branch flag (Git 2.28+)."""
        version = self._get_git_version()
        return version >= (2, 28, 0)

    def _init_git_repos(self) -> None:
        """Initialize git repositories."""
        self.logger.info("Initializing git repositories")

        # Check if git is already initialized
        git_dir = os.path.join(self.repo_root, ".git")
        if os.path.exists(git_dir):
            self.logger.info("Git repository already initialized")
        else:
            # For adoptions, start with the private branch to avoid untracked file conflicts
            is_adoption = self.config.get("is_adoption", False)
            if is_adoption:
                private_branch = self.config.get("private_branch", "private")
                
                if self._supports_initial_branch():
                    # Modern Git: use --initial-branch
                    self.run_git(["init", "--initial-branch", private_branch], cwd=self.repo_root)
                    self.logger.info(f"Initialized git with initial branch: {private_branch}")
                else:
                    # Older Git: use symbolic-ref to set HEAD before first commit
                    self.run_git(["init"], cwd=self.repo_root)
                    self.run_git(["symbolic-ref", "HEAD", f"refs/heads/{private_branch}"], cwd=self.repo_root)
                    self.logger.info(f"Initialized git and set HEAD to: {private_branch}")
            else:
                # Regular project creation
                self.run_git(["init"], cwd=self.repo_root)

        # Git for Windows keeps to MAX_PATH (260 characters for the whole
        # absolute path) unless told otherwise; repokit-common's deepest
        # vendored path is 133, so a project a hundred-odd characters deep
        # failed `git subtree add` with "Filename too long".
        if os.name == "nt":
            self.run_git(["config", "core.longpaths", "true"], cwd=self.repo_root)

        # Configure git user information using enhanced GitConfigManager
        from .git_config import GitConfigManager
        git_config_manager = GitConfigManager(
            repo_path=self.repo_root,
            verbose=self.verbose
        )
        
        # Get comprehensive user info, falling back to config
        user_info = git_config_manager.get_comprehensive_user_info(interactive=False)
        
        # Override with explicit config values if provided
        user = self.config.get("user", {})
        if isinstance(user, dict):
            if user.get("name"):
                user_info["name"] = user["name"]
            if user.get("email"):
                user_info["email"] = user["email"]
        
        # Apply GitHub privacy protection if enabled
        if user_info.get("email"):
            email = user_info["email"]
            
            if self.config.get("use_github_noreply", True) and self.config.get("github", True):
                # If email isn't already a no-reply format
                if "@users.noreply.github.com" not in email:
                    # Extract username from email or use first part
                    username = email.split("@")[0]
                    
                    # Create GitHub no-reply email
                    github_email = f"{username}@users.noreply.github.com"
                    self.logger.info(f"Using GitHub no-reply email format: {github_email}")
                    user_info["email"] = github_email
        
        # Configure git user settings in repository
        git_config_manager.configure_repo_git_user(user_info)

    def _setup_branches(self) -> None:
        """Set up repository branches."""
        self.logger.info("Setting up branches")

        # Check if this is an adoption (existing repo) or new repo
        is_adoption = self.config.get("is_adoption", False)
        
        # For adoptions, check if we need to create an initial commit
        if is_adoption:
            # Check if there are any commits in the repository
            try:
                self.run_git(["rev-parse", "HEAD"], cwd=self.repo_root)
                has_commits = True
                self.logger.info("Found existing commits in repository")
            except Exception:
                has_commits = False
                self.logger.info("No commits found in repository - will create initial commit")
            
            # If no commits exist, we need to create one before we can create branches
            if not has_commits:
                # First, create a .gitignore to handle sensitive files before any commits
                gitignore_path = os.path.join(self.repo_root, ".gitignore")
                
                # Generate the base .gitignore from template
                language = self.config.get("language", "generic")
                context = {
                    "project_name": self.project_name,
                    "description": self.config.get("description", ""),
                    "language": language,
                }
                
                # Use template engine to render the base gitignore
                self.template_engine.render_template_to_file(
                    "gitignore",
                    gitignore_path,
                    context,
                    category="common",  # Use common template
                    preserve_existing=False  # We want to create fresh
                )
                
                # Now append adoption-specific patterns
                adoption_patterns = []
                
                # Add sensitive patterns from config
                sensitive_patterns = self.config.get('sensitive_patterns', [])
                self.logger.debug(f"Found sensitive_patterns in config: {sensitive_patterns}")
                if sensitive_patterns:
                    adoption_patterns.append("\n# Adoption-specific sensitive files")
                    # Handle both comma-separated strings and lists
                    if isinstance(sensitive_patterns, str):
                        patterns = [p.strip() for p in sensitive_patterns.split(',')]
                    else:
                        patterns = sensitive_patterns
                    adoption_patterns.extend(patterns)
                    adoption_patterns.append("")
                
                # Add private directories from config
                private_dirs = self.config.get('private_dirs', [])
                if private_dirs:
                    adoption_patterns.append("# Adoption-specific private directories")
                    # Handle both comma-separated strings and lists
                    if isinstance(private_dirs, str):
                        dirs = [d.strip() for d in private_dirs.split(',')]
                    else:
                        dirs = private_dirs
                    for dir_name in dirs:
                        adoption_patterns.append(f"{dir_name}/")
                    adoption_patterns.append("")
                
                # Append adoption patterns to the template-generated .gitignore
                self.logger.debug(f"Final adoption_patterns list: {adoption_patterns}")
                if adoption_patterns:
                    with open(gitignore_path, "a") as f:
                        f.write("\n".join(adoption_patterns))
                    self.logger.info(f"Added {len(adoption_patterns)} adoption-specific patterns to .gitignore")
                else:
                    self.logger.warning("No adoption patterns to add to .gitignore")
                
                # Create a minimal .gitkeep file with RepoKit adoption metadata
                gitkeep_path = os.path.join(self.repo_root, ".gitkeep")
                
                # Create adoption metadata
                import json
                from datetime import datetime
                
                adoption_metadata = {
                    "repokit_adoption": {
                        "timestamp": datetime.now().isoformat(),
                        "repokit_version": "0.4.0",  # TODO: Get from version
                        "project_name": self.project_name,
                        "description": self.config.get('description', ''),
                        "branch_strategy": self.config.get('branch_strategy', 'standard'),
                        "migration_strategy": self.config.get('migration_strategy', 'safe'),
                        "note": "This file was created to establish git history during RepoKit adoption. It can be safely removed after setup is complete."
                    }
                }
                
                with open(gitkeep_path, "w") as f:
                    f.write("# RepoKit Adoption Bootstrap File\n")
                    f.write("# This file establishes initial git history for RepoKit adoption\n")
                    f.write("# It can be safely removed after project setup is complete\n\n")
                    f.write(json.dumps(adoption_metadata, indent=2))
                
                # Add the bootstrap files and respect the new .gitignore
                self.run_git(["add", ".gitignore", ".gitkeep"], cwd=self.repo_root)
                # Add other files that should be tracked (respecting .gitignore)
                self.run_git(["add", "."], cwd=self.repo_root)
                self.run_git(["commit", "-m", "Initial commit for RepoKit adoption\n\nBootstrap commit to establish git history.\nThis commit can be squashed or removed after adoption is complete."], cwd=self.repo_root)
                self.logger.info("Created initial bootstrap commit for adoption")
        
        # For new repos, create an initial commit
        if not is_adoption:
            # Create an initial commit on main to allow branch creation
            readme_path = os.path.join(self.repo_root, "README.md")

            # Generate README from template
            # Get enhanced git user information using GitConfigManager
            from .git_config import GitConfigManager
            git_config_manager = GitConfigManager(
                repo_path=self.repo_root,
                verbose=self.verbose
            )
            
            # The README's $badges were never filled here (the template carried
            # the literal word into every project since the template was made):
            # the badges need the resolved language, so resolve the layers first.
            self._resolve_layers()
            language = self.config.get("language", "generic")
            base_context = {
                "project_name": self.project_name,
                "description": self.config.get("description", "A new project"),
                "language": language,
                "badges": self._generate_badges(language),
            }

            # Enhance context with comprehensive git user information
            context = git_config_manager.get_template_context(base_context)

            # Check if we should preserve existing README
            preserve_existing = self.config.get("preserve_existing", False)
            
            # Try to render from template, fall back to simple content
            if not self.template_engine.render_template_to_file(
                "README.md", readme_path, context, preserve_existing=preserve_existing
            ):
                # Only create a new README if one doesn't exist
                if not os.path.exists(readme_path):
                    with open(readme_path, "w") as f:
                        f.write(f"# {self.project_name}\n\n")
                        f.write(f"{self.config.get('description', 'A new project')}\n")

            # Only commit if there are changes to commit
            if os.path.exists(readme_path):
                self.run_git(["add", "README.md"], cwd=self.repo_root)
                try:
                    self.run_git(["commit", "-m", "Initial commit"], cwd=self.repo_root)
                except Exception as e:
                    # If commit fails (e.g., nothing to commit), continue
                    self.logger.debug("Initial commit skipped (possibly nothing to commit)")
        else:
            # For adoptions, we already have commits
            self.logger.info("Skipping initial commit for adoption - using existing repository history")

        # Create branches
        branches = self.config.get(
            "branches", ["main", "dev", "staging", "test", "live"]
        )

        # For adoption, handle existing branch structure differently
        is_adoption = self.config.get("is_adoption", False)
        
        if is_adoption:
            # For adoption, we should already be on the private branch from _init_git_repos
            private_branch = self.config.get("private_branch", "private")
            current_branch = self.run_git(["branch", "--show-current"], cwd=self.repo_root)
            
            # Verify we're on the private branch (should be true from git init)
            if current_branch != private_branch:
                self.logger.warning(f"Expected to be on {private_branch} branch, but on {current_branch}")
                # Create private branch if it doesn't exist and switch to it
                existing_branches = self.run_git(["branch", "--list"], cwd=self.repo_root).splitlines()
                branch_names = [b.strip().lstrip('* ') for b in existing_branches]
                
                if private_branch not in branch_names:
                    self.run_git(["branch", private_branch], cwd=self.repo_root)
                
                # Switch to private branch (this should now work since we committed files earlier)
                self.run_git(["checkout", private_branch], cwd=self.repo_root)
            
            self.logger.info(f"Working on private branch: {private_branch}")
            # Note: Public branches (main, dev) will be created in _create_initial_commit
        else:
            # For new repos, follow original logic
            default_branch = self.config.get("default_branch", "main")
            current_branch = self.run_git(["branch", "--show-current"], cwd=self.repo_root)

            if current_branch != default_branch:
                if default_branch not in branches:
                    branches.append(default_branch)
                self.run_git(["branch", "-m", default_branch], cwd=self.repo_root)

            # Create other branches
            for branch in branches:
                if branch != default_branch:  # Skip default branch which already exists
                    self.run_git(["branch", branch], cwd=self.repo_root)

            # No private branch (main-only): stay on the default branch
            if not self.private_branch:
                return

            # Create private branch for personal work
            private_branch = self.private_branch
            if private_branch not in branches:
                self.run_git(["branch", private_branch], cwd=self.repo_root)

            # Switch to private branch (we stay on private in the main repo)
            self.run_git(["checkout", private_branch], cwd=self.repo_root)

    def _setup_worktrees(self) -> None:
        """Set up git worktrees for branches."""
        self.logger.info("Setting up worktrees")

        # Get branches to create worktrees for
        worktree_branches = self.config.get(
            "worktrees", [self.config.get("default_branch", "main"), "dev"]
        )

        # Always add GitHub directory as worktree with the default branch if it�s in the list
        main_branch = self.config.get("default_branch", "main")
        if main_branch in worktree_branches:
            # Get directory name for main branch from branch_config
            branch_config = self.config.get("branch_config", {})
            if not isinstance(branch_config, dict):
                branch_config = {}
            branch_directories = branch_config.get("branch_directories", {})
            if not isinstance(branch_directories, dict):
                branch_directories = {}
            github_dir = branch_directories.get(main_branch, "github")
            github_path = os.path.join(os.path.dirname(self.repo_root), github_dir)

            try:
                self.run_git(
                    ["worktree", "add", github_path, main_branch], cwd=self.repo_root
                )
                self.logger.info(
                    f"Created worktree for branch '{main_branch}' at {github_path}"
                )
            except Exception as e:
                self.logger.error(
                    f"Failed to create worktree for branch '{main_branch}': {str(e)}"
                )

            # Configure Git for the GitHub worktree if user information is provided
            user = self.config.get("user", {})
            if user:
                if user.get("name"):
                    self.run_git(["config", "user.name", user["name"]], cwd=github_path)

                if user.get("email"):
                    self.run_git(
                        ["config", "user.email", user["email"]], cwd=github_path
                    )

        # Add additional worktrees as configured
        worktree_base = os.path.dirname(self.repo_root)
        for branch in worktree_branches:
            if branch == main_branch and main_branch in branch_directories:
                # Skip main branch if it has a custom directory mapping (already handled above)
                continue

            # Get directory name for this branch
            branch_dir = branch_directories.get(branch, branch)
            worktree_path = os.path.join(worktree_base, branch_dir)

            # Skip if already exists (might be the main branch worktree we already created)
            if os.path.exists(worktree_path):
                continue

            try:
                self.run_git(
                    ["worktree", "add", worktree_path, branch], cwd=self.repo_root
                )
                self.logger.info(
                    f"Created worktree for branch '{branch}' at {worktree_path}"
                )

                # Configure Git for this worktree if user information is provided
                if user:
                    if user.get("name"):
                        self.run_git(
                            ["config", "user.name", user["name"]], cwd=worktree_path
                        )

                    if user.get("email"):
                        self.run_git(
                            ["config", "user.email", user["email"]], cwd=worktree_path
                        )
            except Exception as e:
                self.logger.warning(
                    f"Failed to create worktree for branch '{branch}': {str(e)}"
                )

    def _generate_template_files(self) -> None:
        """Generate template files for the repository."""
        self.logger.info("Generating template files")

        # Get language to determine specific templates
        language = self.config.get("language", "generic")
        
        # Check if we should preserve existing files (for adoption)
        preserve_existing = self.config.get("preserve_existing", False)
        
        # Helper function to render templates with preserve_existing
        def render_template(template_name, output_path, context_dict=None, category="common"):
            ctx = context_dict or context
            return self.template_engine.render_template_to_file(
                template_name, output_path, ctx, category=category, preserve_existing=preserve_existing
            )

        # Get enhanced git user information using GitConfigManager
        from .git_config import GitConfigManager
        git_config_manager = GitConfigManager(
            repo_path=self.repo_root,
            verbose=self.verbose
        )
        
        # The code-type resolution first: it settles the language, the archetype
        # and so which CI workflow the README's badge can point at.
        self._resolve_layers()
        language = self.config.get("language", "generic")

        github_config = self.config.get("github", {})
        github_user = (github_config.get("username") if isinstance(github_config, dict) else None) \
            or "YOUR_GITHUB_USERNAME"
        import datetime

        # Context for template rendering with enhanced git config
        base_context = {
            "project_name": self.project_name,
            "language": language,
            "description": self.config.get("description", ""),
            "badges": self._generate_badges(language),
            "github_user": github_user,
            "date": datetime.date.today().isoformat(),
        }
        
        # Enhance context with comprehensive git user information
        context = git_config_manager.get_template_context(base_context)

        # Create .github directory
        github_dir = os.path.join(self.repo_root, ".github")
        os.makedirs(github_dir, exist_ok=True)

        # Create ISSUE_TEMPLATE directory
        issue_dir = os.path.join(github_dir, "ISSUE_TEMPLATE")
        os.makedirs(issue_dir, exist_ok=True)

        # CI comes from the code-type layers (ci-<language>.yml), not from the
        # structure: git-repokit's own workflow used to be written here.

        # Generate issue templates
        render_template(
            "bug-report.md",
            os.path.join(issue_dir, "bug-report.md"),
            category="github/ISSUE_TEMPLATE"
        )

        render_template(
            "feature-request.md",
            os.path.join(issue_dir, "feature-request.md"),
            category="github/ISSUE_TEMPLATE"
        )

        # Generate CODEOWNERS file
        render_template(
            "CODEOWNERS",
            os.path.join(github_dir, "CODEOWNERS"),
            category="github"
        )

        # Generate other common files
        render_template(
            "CONTRIBUTING.md",
            os.path.join(self.repo_root, "CONTRIBUTING.md"),
            category="common"
        )

        # Line-ending normalisation and the vendored-tooling attribute
        render_template(
            "gitattributes",
            os.path.join(self.repo_root, ".gitattributes"),
            category="common"
        )

        # A changelog with the first version's heading, so git-repokit-common's
        # version sync finds its section and compare link from the first commit
        render_template(
            "CHANGELOG.md",
            os.path.join(self.repo_root, "CHANGELOG.md"),
            category="common"
        )

        # The structure's .gitignore and launch.json, then the code type on top
        self._write_gitignore_and_launch(context)
        self._apply_layers(context)

    def _write_gitignore_and_launch(self, context: Dict[str, Any]) -> None:
        """The common .gitignore (keeping an adopted project's own patterns) and
        VS Code's launch.json. The language files that used to be written here
        come from the code-type layers now (_apply_layers)."""
        gitignore_path = os.path.join(self.repo_root, ".gitignore")

        # An adopted repository's own patterns sit after "# Add custom patterns
        # below"; keep them across the rewrite.
        existing_adoption_patterns = ""
        if os.path.exists(gitignore_path):
            with open(gitignore_path, 'r') as f:
                content = f.read()
                if "Adoption-specific" in content:
                    lines = content.split('\n')
                    add_custom_found = False
                    adoption_lines = []
                    for line in lines:
                        if "# Add custom patterns below" in line:
                            add_custom_found = True
                            continue
                        if add_custom_found:
                            adoption_lines.append(line)
                    if adoption_lines:
                        existing_adoption_patterns = '\n'.join(adoption_lines)
                        self.logger.debug(f"Found existing adoption patterns to preserve: {len(adoption_lines)} lines")

        self.template_engine.render_template_to_file(
            "gitignore",
            gitignore_path,
            context,
            category="common",
        )

        if existing_adoption_patterns.strip():
            with open(gitignore_path, "a") as f:
                f.write(existing_adoption_patterns)
            self.logger.info("Preserved adoption-specific patterns in .gitignore")

        vscode_dir = os.path.join(self.repo_root, ".vscode")
        os.makedirs(vscode_dir, exist_ok=True)
        self.template_engine.render_template_to_file(
            "launch.json",
            os.path.join(vscode_dir, "launch.json"),
            context,
            category="common",
        )

    def _resolve_layers(self):
        """Resolve the code-type layers once (repokit/layers.py): returns
        (root, resolution) or None when the package has no layer tree, and
        settles config's `languages`, `archetype` and single-value `language`
        (an archetype implies its language; .repokit.json, the badges and the
        build-command map read them). The CLI has validated the names already,
        so an error here is a broken layer tree and stops the create."""
        from . import layers

        if getattr(self, "_layer_resolution", None) is not None:
            return self._layer_resolution
        languages = self.config.get("languages") or [self.config.get("language") or layers.GENERIC]
        archetype = self.config.get("archetype")
        root = layers.layers_root(self.template_engine)
        if root is None:
            if [l for l in layers.parse_languages(languages) if l != layers.GENERIC] or archetype:
                self.logger.warning("No code-type layers found with the templates; only the structure was written")
            return None
        resolution = layers.resolve(layers.load_manifest(root), languages, archetype)
        self.config["languages"] = resolution.languages
        self.config["archetype"] = resolution.archetype
        self.config["language"] = resolution.languages[0] if resolution.languages else layers.GENERIC
        self._layer_resolution = (root, resolution)
        return self._layer_resolution

    def _ci_workflow(self) -> Optional[str]:
        """The CI workflow file the resolved layers will write, for the README's
        badge: ci-<language>.yml from the first language whose layer or
        archetype ships one; None when none does (then no workflow badge)."""
        resolved = self._resolve_layers()
        if resolved is None:
            return None
        root, resolution = resolved
        for layer in reversed(resolution.layers):
            folder = root / layer / ".github" / "workflows"
            if folder.is_dir():
                names = sorted(p.name for p in folder.iterdir() if p.name.startswith("ci-") and p.suffix == ".yml")
                if names:
                    return names[0]
        return None

    def _apply_layers(self, context: Dict[str, Any]) -> None:
        """Lay the code-type layers (the languages' and the archetype's) over the
        structure, from the resolution _resolve_layers settled."""
        from . import layers
        from .template_engine import token_context

        resolved = self._resolve_layers()
        if resolved is None:
            return
        root, resolution = resolved
        if not resolution.layers:
            return
        ctx = token_context(context, resolution.archetype)
        written = layers.assemble(
            root, resolution.layers, self.repo_root, ctx,
            engine=self.template_engine,
            preserve_existing=self.config.get("preserve_existing", False),
            logger=self.logger,
        )
        self.logger.info(f"Code-type layers {', '.join(resolution.layers)}: {len(written)} files")

        # A layer may ship .repokit-common.toml (or a pyproject table) of its
        # own; in the private-branch model the settings written at vendoring
        # time must still be there, so merge them back (never overwriting).
        if self.private_branch and getattr(self, "common_vendored", False):
            from . import common_kit
            private_paths = ["CLAUDE.md"]
            private_paths += [f"{d.rstrip('/')}/" for d in self.config.get("private_dirs", [])]
            private_paths += list(self.config.get("sensitive_files", []))
            common_kit.write_settings(
                self.repo_root, common_kit.private_branch_settings(self.private_branch, private_paths))

    def _vendor_repokit_common(self) -> None:
        """Add git-repokit-common at scripts/repokit-common/ and commit its settings.

        A failure (offline, no git subtree) is a warning with the commands to
        run by hand, never a failed create; the project then keeps git-repokit's
        own pre-commit hook as its guard (_setup_protection).
        """
        from . import common_kit

        src = common_kit.source(self.config)
        if src is None:
            self.logger.info("git-repokit-common: vendoring switched off")
            return
        url, ref = src
        problem = common_kit.vendor(self.repo_root, url, ref)
        if problem:
            self.logger.warning(f"git-repokit-common not added: {problem}")
            self.logger.warning(
                f"Run: git subtree add --prefix={common_kit.PREFIX} {url} {ref} --squash"
            )
            return
        self.common_vendored = True
        self.logger.info(f"Vendored git-repokit-common at {common_kit.PREFIX}/")

        # The private-branch model: repokit-common's pre-commit must protect the
        # paths git-repokit's guard did, and know a custom private branch.
        if self.private_branch:
            private_paths = ["CLAUDE.md"]
            private_paths += [f"{d.rstrip('/')}/" for d in self.config.get("private_dirs", [])]
            private_paths += list(self.config.get("sensitive_files", []))
            written = common_kit.write_settings(
                self.repo_root,
                common_kit.private_branch_settings(self.private_branch, private_paths),
            )
            if written:
                self.run_git(["add", written], cwd=self.repo_root)
                self.run_git(["commit", "-m", "Configure git-repokit-common for the private-branch model"],
                             cwd=self.repo_root)

    def _link_private_into_worktrees(self) -> None:
        """Link <worktree>/private to the real vault in every worktree but the main one."""
        from .vault import link_private

        private_path = os.path.join(self.repo_root, "private")

        # Every worktree reads the repository's shared info/exclude. "/private"
        # (no trailing slash) also matches the link itself, which git sees as a
        # symlink, not a directory; and public branches may carry no .gitignore.
        common_dir = self.run_git(["rev-parse", "--git-common-dir"], cwd=self.repo_root, check=False) or ".git"
        if not os.path.isabs(common_dir):
            common_dir = os.path.join(self.repo_root, common_dir)
        exclude = os.path.join(common_dir, "info", "exclude")
        os.makedirs(os.path.dirname(exclude), exist_ok=True)
        existing = open(exclude, encoding="utf-8").read() if os.path.exists(exclude) else ""
        if "/private" not in existing.splitlines():
            with open(exclude, "a", encoding="utf-8") as f:
                f.write(("\n" if existing and not existing.endswith("\n") else "")
                        + "# private/ in a worktree is a link to the private repository\n/private\n")

        output = self.run_git(["worktree", "list", "--porcelain"], cwd=self.repo_root, check=False) or ""
        main = os.path.normcase(os.path.abspath(self.repo_root))
        for line in output.splitlines():
            if not line.startswith("worktree "):
                continue
            path = os.path.abspath(line[len("worktree "):].strip())
            if os.path.normcase(path) == main:
                continue
            problem = link_private(path, private_path)
            if problem:
                self.logger.warning(f"Could not link private/ into {path}: {problem}")
            else:
                self.logger.info(f"Linked {path}/private to the private repository")

    def _setup_github_integration(self) -> None:
        """Set up GitHub integration."""
        self.logger.info("Setting up GitHub integration")

        # Skip if GitHub integration is disabled
        if not self.config.get("github", True):
            self.logger.info("GitHub integration is disabled, skipping")
            return

        # Flat layout: .github was generated in the repository itself and
        # committed with everything else
        if not self.github_root:
            return

        # Only proceed if the GitHub worktree exists
        if not os.path.exists(self.github_root):
            self.logger.warning(
                "GitHub worktree not found, skipping GitHub integration"
            )
            return

        # Copy .github directory to github worktree
        github_src = os.path.join(self.repo_root, ".github")
        github_dst = os.path.join(self.github_root, ".github")

        if os.path.exists(github_src):
            if os.path.exists(github_dst):
                shutil.rmtree(github_dst)
            shutil.copytree(github_src, github_dst)

            # Check if there are changes to commit before trying
            if self._has_changes(self.github_root):
                try:
                    self.run_git(["add", ".github"], cwd=self.github_root)
                    self.run_git(
                        ["commit", "-m", "Add GitHub configuration files"],
                        cwd=self.github_root,
                    )
                    self.logger.info("Committed GitHub configuration files")
                except Exception as e:
                    self.logger.warning(f"Failed to commit GitHub files: {str(e)}")
            else:
                self.logger.info("No GitHub files to commit")
        else:
            self.logger.warning(
                "No .github directory found in repository, skipping GitHub integration"
            )

    def _setup_protection(self) -> None:
        """Set up protection for private content."""
        self.logger.info("Setting up private content protection")

        # Check if .gitignore exists and read its content
        gitignore_path = os.path.join(self.repo_root, ".gitignore")
        existing_content = ""
        if os.path.exists(gitignore_path):
            with open(gitignore_path, "r") as f:
                existing_content = f.read()

        # Get private directories from config
        private_dirs = self.config.get(
            "private_dirs", DEFAULT_PRIVATE_DIRS
        )
        
        # Only add entries that don't already exist
        entries_to_add = []
        for private_dir in private_dirs:
            pattern = f"/{private_dir}/"
            if pattern not in existing_content:
                entries_to_add.append(pattern)
        
        # Only append if we have new entries to add
        if entries_to_add:
            with open(gitignore_path, "a") as f:
                f.write("\n# Private content (auto-added)\n")
                for entry in entries_to_add:
                    f.write(f"{entry}\n")
                
                # Add __private__ pattern if not already present
                if "**/__private__*" not in existing_content:
                    f.write("**/__private__*\n")
                f.write("\n")

        # With git-repokit-common vendored, its hooks are the project's hooks
        # (installed at the end of setup_repository); git-repokit writes none.
        if self.common_vendored:
            return

        # Fallback guard when git-repokit-common is not vendored (--no-common,
        # or vendoring failed): git-repokit's own pre-commit hook.
        hooks_dir = os.path.join(self.repo_root, ".git", "hooks")
        os.makedirs(hooks_dir, exist_ok=True)

        # Import BranchContext to get consistent patterns
        from .branch_utils import BranchContext
        
        # Create context with configuration
        branch_context = BranchContext(self.repo_root, self._get_branch_config())
        
        # Generate branch patterns for template
        private_branch_patterns = "|".join(branch_context.PRIVATE_BRANCHES)
        public_branch_patterns = "|".join(branch_context.PUBLIC_BRANCHES)
        
        # Add feature branch patterns (they're considered private in BranchContext)
        private_branch_patterns += "|feature/*|feat/*|prototype/*|experiment/*|spike/*"
        
        # Generate private content patterns for template
        # Start with BranchContext patterns and add config-based patterns
        all_patterns = set()
        
        # Add BranchContext patterns
        all_patterns.update(branch_context.PRIVATE_PATTERNS)
        all_patterns.update(branch_context.EXCLUDE_FROM_PUBLIC)
        
        # Add config-based sensitive patterns
        config_sensitive_patterns = self.config.get('sensitive_patterns', [])
        if config_sensitive_patterns:
            all_patterns.update(config_sensitive_patterns)
            self.logger.debug(f"Added {len(config_sensitive_patterns)} config-based sensitive patterns to hook")
        
        # Add config-based sensitive files  
        config_sensitive_files = self.config.get('sensitive_files', [])
        if config_sensitive_files:
            all_patterns.update(config_sensitive_files)
            self.logger.debug(f"Added {len(config_sensitive_files)} config-based sensitive files to hook")
        
        # Convert all patterns to shell regex patterns (escaped: `*.log` used
        # to become `^.*.log` and refuse catalog.py or search_sesslog.py)
        from .utils import glob_to_ere
        patterns = [glob_to_ere(pattern) for pattern in sorted(all_patterns)]

        # Join all patterns with | for shell regex
        private_content_regex = "|".join(patterns)

        # Render pre-commit hook from template using BranchContext patterns
        context = {
            "private_branch_patterns": private_branch_patterns,
            "public_branch_patterns": public_branch_patterns,
            "private_content_regex": private_content_regex
        }

        pre_commit_path = os.path.join(hooks_dir, "pre-commit")
        if not self.template_engine.render_template_to_file(
            "pre-commit", pre_commit_path, context, category="hooks"
        ):
            # Fallback to creating a simple hook
            with open(pre_commit_path, "w") as f:
                f.write(
                    """#!/bin/sh
# Pre-commit hook to prevent committing private content

# Check for private directories
for file in $(git diff --cached --name-only); do
    if echo "$file" | grep -q -E "^private/|^convos/|^logs/|__private__"; then
        echo "ERROR: Attempting to commit private content: $file"
        echo "Private content should not be committed to the repository."
        exit 1
    fi
done

exit 0
"""
                )

        # Make hook executable on Unix-like systems
        if os.name != "nt":  # not Windows
            os.chmod(pre_commit_path, 0o755)

    def _setup_local_excludes(self) -> None:
        """Set up local exclude patterns for branch-conditional file ignoring."""
        self.logger.info("Setting up local exclude patterns")

        # Path to local exclude file
        exclude_file = os.path.join(self.repo_root, ".git", "info", "exclude")

        # Ensure the info directory exists
        os.makedirs(os.path.dirname(exclude_file), exist_ok=True)

        # Define patterns for files that should be tracked in private but ignored in public branches
        exclude_patterns = [
            "# RepoKit: Branch-conditional excludes",
            "# These files are tracked in 'private' branch but ignored in public branches",
            "",
            "# AI integration files",
            "CLAUDE.md",
            "",
            "# Development conversation logs",
            "private/claude/",
            "",
            "# Private development documentation",
            "private/docs/",
            "",
            "# Development notes and temporary files",
            "private/notes/",
            "private/temp/",
            "",
            "# Revision history (private branch only)",
            "revisions/",
            "",
        ]

        # Read existing exclude file if it exists
        existing_content = []
        if os.path.exists(exclude_file):
            with open(exclude_file, "r") as f:
                existing_content = f.read().splitlines()

        # Check if our patterns are already present
        repokit_marker = "# RepoKit: Branch-conditional excludes"
        if repokit_marker not in existing_content:
            # Append our patterns
            with open(exclude_file, "a") as f:
                if existing_content and not existing_content[-1].strip() == "":
                    f.write("\n")  # Add spacing if file has content
                f.write("\n".join(exclude_patterns))

            self.logger.info("Added branch-conditional exclude patterns")
        else:
            self.logger.debug("Local exclude patterns already configured")

        # Set up local excludes for worktrees as well
        self._setup_worktree_excludes()

    def _setup_worktree_excludes(self) -> None:
        """Set up local exclude patterns for all worktrees."""
        # Get list of worktrees
        try:
            worktree_output = self.run_git(
                ["worktree", "list"], cwd=self.repo_root, check=False
            )
            if not worktree_output:
                return

            # Parse worktree paths
            for line in worktree_output.split("\n"):
                if not line.strip():
                    continue

                # Parse worktree line (format: "/path/to/worktree  abcd1234 [branch]")
                parts = line.split()
                if len(parts) >= 3 and "[" in parts[2] and "]" in parts[2]:
                    worktree_path = parts[0]
                    branch = parts[2].strip("[]")

                    # Skip private branch worktree
                    if branch == self.config.get("private_branch", "private"):
                        continue

                    # Set up exclude file for this worktree
                    exclude_file = os.path.join(
                        worktree_path, ".git", "info", "exclude"
                    )

                    # Worktrees have .git as a file, not directory
                    git_dir_file = os.path.join(worktree_path, ".git")
                    if os.path.isfile(git_dir_file):
                        # Read the git directory path from .git file
                        with open(git_dir_file, "r") as f:
                            git_dir_line = f.read().strip()
                            if git_dir_line.startswith("gitdir: "):
                                git_dir = git_dir_line[8:]  # Remove 'gitdir: ' prefix
                                exclude_file = os.path.join(git_dir, "info", "exclude")

                    # Ensure directory exists
                    os.makedirs(os.path.dirname(exclude_file), exist_ok=True)

                    # Same exclude patterns for worktrees
                    exclude_patterns = [
                        "# RepoKit: Branch-conditional excludes for worktree",
                        "# These files are tracked in 'private' branch but ignored in public branches",
                        "",
                        "# AI integration files",
                        "CLAUDE.md",
                        "",
                        "# Development conversation logs",
                        "private/claude/",
                        "",
                        "# Private development documentation",
                        "private/docs/",
                        "",
                        "# Development notes and temporary files",
                        "private/notes/",
                        "private/temp/",
                        "",
                        "# Revision history (private branch only)",
                        "revisions/",
                        "",
                    ]

                    # Check if already configured
                    existing_content = []
                    if os.path.exists(exclude_file):
                        with open(exclude_file, "r") as f:
                            existing_content = f.read().splitlines()

                    repokit_marker = (
                        "# RepoKit: Branch-conditional excludes for worktree"
                    )
                    if repokit_marker not in existing_content:
                        with open(exclude_file, "a") as f:
                            if (
                                existing_content
                                and not existing_content[-1].strip() == ""
                            ):
                                f.write("\n")
                            f.write("\n".join(exclude_patterns))

                        self.logger.debug(
                            f"Added exclude patterns for worktree: {worktree_path}"
                        )

        except Exception as e:
            self.logger.warning(f"Failed to set up worktree excludes: {str(e)}")

    def _create_initial_commit(self) -> None:
        """Create initial commit in repository."""
        self.logger.info("Creating initial commit")

        # Add all files
        self.run_git(["add", "."], cwd=self.repo_root)

        # Check if there's anything to commit
        try:
            # Use diff --cached to see if there are staged changes
            diff_output = self.run_git(["diff", "--cached", "--name-only"], cwd=self.repo_root)
            if diff_output.strip():
                # Create commit only if there are changes
                self.run_git(
                    ["commit", "-m", "Initial repository setup with RepoKit"],
                    cwd=self.repo_root,
                )
            else:
                self.logger.info("No changes to commit in initial setup")
        except Exception as e:
            # An adoption may have nothing new to commit; anything else (a
            # hook refusing the commit) must be seen, not buried at debug level
            # under the success banner.
            if self.config.get("is_adoption", False):
                self.logger.debug(f"Initial commit skipped: {str(e)}")
            else:
                self.logger.error(
                    f"Initial commit failed; the files are staged but not committed: {str(e)}"
                )

        # No private branch (main-only): the commit above is on main and
        # private paths were never added (.gitignore), so there is nothing
        # to cut public branches from.
        if not self.private_branch:
            return

        # Create public branches with safe content migration using safe-merge-dev
        # This prevents private content from reaching public branches
        branches = self.config.get(
            "branches", ["main", "dev", "staging", "test", "live"]
        )
        private_branch = self.private_branch

        for branch in branches:
            if branch != private_branch:  # Skip private branch
                try:
                    # Choose approach based on whether this is an adoption
                    is_adoption = self.config.get("is_adoption", False)
                    
                    if is_adoption:
                        # Use selective approach for adoptions (privacy-first, no deletion commits)
                        self.logger.info(f"Using selective branch creation for adoption (privacy-first)")
                        self._create_clean_public_branch_selective(branch, private_branch)
                    else:
                        # Use existing approach for new repositories
                        self.logger.info(f"Using standard branch creation for new repository")
                        self._create_clean_public_branch(branch, private_branch)
                    
                    # Verify the branch is actually clean
                    if self._verify_clean_branch(branch):
                        self.logger.info(f"Successfully created and verified clean public branch '{branch}'")
                    else:
                        self.logger.error(f"Branch '{branch}' failed verification - contains private content!")
                        
                    if self.verbose >= 2:
                        approach = "selective" if is_adoption else "standard"
                        self.logger.debug(
                            f"Created clean public branch '{branch}' using {approach} approach"
                        )
                except Exception as e:
                    self.logger.warning(f"Failed to create clean public branch '{branch}': {str(e)}")

        # Switch back to private branch for continued development
        self.run_git(["checkout", private_branch], cwd=self.repo_root)

    def _get_working_directory_files(self) -> List[str]:
        """
        Get all files from working directory (not git index).
        
        This is used for selective branch creation to examine filesystem
        rather than git-tracked files.
        
        Returns:
            List of relative file paths from repo root
        """
        all_files = []
        for root, dirs, files in os.walk(self.repo_root):
            # Skip .git directory
            if ".git" in root.split(os.sep):
                continue
            for file in files:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, self.repo_root)
                all_files.append(relative_path)
        return all_files
    
    @staticmethod
    def _is_vendored(path: str) -> bool:
        """True for files of the vendored git-repokit-common copy.

        Upstream code is never private: its own file names (e.g. tests about
        private-patterns) must not be cut from public branches by the
        private-name patterns.
        """
        from .common_kit import PREFIX
        normalized = str(path).replace("\\", "/").lstrip("./")
        return normalized == PREFIX or normalized.startswith(PREFIX + "/")

    def _filter_files_for_public_branch(self, file_list: List[str]) -> List[str]:
        """
        Filter out sensitive files using existing pattern infrastructure.
        
        Args:
            file_list: List of file paths to filter
            
        Returns:
            List of non-sensitive file paths safe for public branches
        """
        import fnmatch
        from pathlib import Path
        
        clean_files = []
        patterns_to_exclude = DEFAULT_SENSITIVE_PATTERNS.copy()
        
        # Add any additional patterns from config
        config_patterns = self.config.get("sensitive_patterns", [])
        if config_patterns:
            patterns_to_exclude.extend(config_patterns)
        
        # Use existing BranchContext for additional pattern checking
        from .branch_utils import BranchContext
        context = BranchContext(self.repo_root, self._get_branch_config())
        
        for file_path in file_list:
            if self._is_vendored(file_path):
                clean_files.append(file_path)  # vendored upstream code is never private
                continue
            is_sensitive = False
            matching_pattern = None

            # Check against DEFAULT_SENSITIVE_PATTERNS
            for pattern in patterns_to_exclude:
                # Use same cross-platform pattern matching as cleanup
                normalized_file = str(Path(file_path)).replace('\\', '/')
                normalized_pattern = pattern.replace('\\', '/')
                
                matches = [
                    fnmatch.fnmatch(normalized_file, normalized_pattern),
                    fnmatch.fnmatch(os.path.basename(file_path), normalized_pattern),
                    fnmatch.fnmatch(str(Path(file_path)), normalized_pattern),
                ]
                
                if any(matches):
                    is_sensitive = True
                    matching_pattern = pattern
                    break
            
            # Check against BranchContext patterns if not already flagged
            if not is_sensitive:
                # Use BranchContext to check if file should be excluded from public
                private_files = context.check_private_files([file_path])
                if private_files:
                    is_sensitive = True
                    matching_pattern = f"BranchContext: {private_files[0][1]}"
            
            if is_sensitive:
                self.logger.debug(f"Excluding sensitive file from public branch: {file_path} (pattern: {matching_pattern})")
            else:
                clean_files.append(file_path)
        
        return clean_files
    
    def _create_clean_public_branch_selective(self, branch_name: str, source_branch: str) -> None:
        """
        Create public branch by selectively adding only non-sensitive files.
        
        This approach creates a branch with shared history (for merging) but ensures 
        sensitive files are excluded from the initial commit on public branches.
        The guardrails and hooks prevent future commits of private content.
        
        Args:
            branch_name: Name of the public branch to create
            source_branch: Source branch (typically 'private')
        """
        try:
            self.logger.info(f"Creating clean public branch '{branch_name}' using selective approach")
            
            # Get current branch to restore if something goes wrong
            current_branch = self.run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=self.repo_root).strip()
            
            # Check if branch already exists
            existing_branches = self.run_git(["branch", "--list"], cwd=self.repo_root).splitlines()
            branch_exists = any(branch_name in branch.strip() for branch in existing_branches)
            
            if branch_exists:
                self.logger.info(f"Branch '{branch_name}' already exists, will recreate with selective approach")
                # Delete existing branch to recreate cleanly
                self.run_git(["branch", "-D", branch_name], cwd=self.repo_root, check=False)
            
            # Create branch from source (maintains history for merging)
            self.run_git(["checkout", "-b", branch_name], cwd=self.repo_root)
            
            # Clear git index to rebuild with only clean files
            self.run_git(["rm", "-r", "--cached", "."], cwd=self.repo_root)
            
            # Get all files from working directory (not git index)
            all_files = self._get_working_directory_files()
            self.logger.info(f"Found {len(all_files)} files in working directory")
            
            # Filter out sensitive files using existing patterns
            clean_files = self._filter_files_for_public_branch(all_files)
            excluded_count = len(all_files) - len(clean_files)
            self.logger.info(f"Filtered to {len(clean_files)} clean files ({excluded_count} sensitive files excluded)")
            
            # Add only clean files to git index one by one
            for file_path in clean_files:
                try:
                    self.run_git(["add", file_path], cwd=self.repo_root)
                    if self.verbose >= 3:
                        self.logger.debug(f"Added clean file to git index: {file_path}")
                except Exception as e:
                    self.logger.warning(f"Failed to add file {file_path}: {str(e)}")
            
            # Update .gitignore to ensure future privacy protection
            from .branch_utils import BranchContext
            context = BranchContext(self.repo_root, self._get_branch_config())
            self._update_gitignore_for_public_branch(context)
            
            # Create initial commit with only clean files (no deletion history)
            try:
                staged_changes = self.run_git(["diff", "--cached", "--name-status"], cwd=self.repo_root)
                if staged_changes.strip():
                    commit_message = f"Initial {branch_name} branch setup\n\nCreated with selective file addition to exclude sensitive content.\nFiles included: {len(clean_files)}\nExcluded: {excluded_count} sensitive files"
                    
                    self.run_git(["commit", "-m", commit_message], cwd=self.repo_root)
                    self.logger.info(f"Created clean public branch '{branch_name}' with {len(clean_files)} files")
                else:
                    self.logger.warning(f"No clean files to commit for branch '{branch_name}'")
            except Exception as e:
                self.logger.error(f"Failed to commit clean branch '{branch_name}': {str(e)}")
                raise
            
            self.logger.info(f"Successfully created selective public branch '{branch_name}' with shared history")
            
        except Exception as e:
            self.logger.error(f"Failed to create selective public branch '{branch_name}': {str(e)}")
            # Try to switch back to original branch
            try:
                self.run_git(["checkout", current_branch], cwd=self.repo_root, check=False)
            except:
                pass
            raise

    def _create_clean_public_branch(self, branch_name: str, source_branch: str) -> None:
        """
        Create a clean public branch without private content using existing guardrails.
        
        This method creates a new branch and uses the existing BranchContext infrastructure
        to identify and remove private content, ensuring consistency with other guardrails.
        
        Args:
            branch_name: Name of the public branch to create
            source_branch: Source branch (typically 'private')
        """
        # Import here to avoid circular dependencies
        from .branch_utils import BranchContext
        
        try:
            # First, ensure we're in a git repository
            if not os.path.exists(os.path.join(self.repo_root, ".git")):
                raise ValueError(f"Not a git repository: {self.repo_root}")
            
            # Get current branch to restore if something goes wrong
            current_branch = self.run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=self.repo_root).strip()
            
            # Check if branch already exists
            existing_branches = self.run_git(["branch", "--list"], cwd=self.repo_root).splitlines()
            branch_exists = any(branch_name in branch.strip() for branch in existing_branches)
            
            if branch_exists:
                # Branch exists, check it out and reset it
                self.logger.info(f"Branch '{branch_name}' already exists, resetting it")
                self.run_git(["checkout", branch_name], cwd=self.repo_root)
                self.run_git(["reset", "--hard", source_branch], cwd=self.repo_root)
            else:
                # Create the new branch from the source branch
                self.run_git(["checkout", "-b", branch_name, source_branch], cwd=self.repo_root)
            
            # Use existing BranchContext with configuration to identify private content
            context = BranchContext(self.repo_root, self._get_branch_config())
            
            # Get all files tracked by git (check git index, not working directory)
            tracked_files = self.run_git(["ls-files"], cwd=self.repo_root).splitlines()
            
            # Use existing guardrails logic to identify private files
            # (vendored upstream code is never private)
            private_files = [(f, r) for f, r in context.check_private_files(tracked_files)
                             if not self._is_vendored(f)]

            files_removed = []
            if private_files:
                self.logger.info(f"Removing {len(private_files)} private files from branch '{branch_name}'")
                
                # Remove private files from git index
                for file_path, reason in private_files:
                    try:
                        # Remove from git index with proper error checking
                        self.run_git(["rm", "--cached", "--ignore-unmatch", file_path], 
                                   cwd=self.repo_root, check=True)
                        files_removed.append(file_path)
                        self.logger.debug(f"Removed {file_path} from git index: {reason}")
                    except Exception as e:
                        self.logger.error(f"CRITICAL: Failed to remove {file_path} from git index: {e}")
                        raise
            
            # CRITICAL FIX: Perform additional sensitive file cleanup for public branch
            # This ensures working directory files are also cleaned
            self.logger.info(f"Performing comprehensive sensitive file cleanup for public branch '{branch_name}'")
            cleanup_results = self._cleanup_sensitive_files(branch_context=branch_name)
            
            # Add cleanup results to files_removed for commit message
            if cleanup_results.get("working_dir"):
                files_removed.extend(cleanup_results["working_dir"])
            if cleanup_results.get("git_index"):
                files_removed.extend(cleanup_results["git_index"])
            
            # Update .gitignore to ensure private content stays ignored
            self._update_gitignore_for_public_branch(context)
            
            # Commit the changes (both file removals and .gitignore updates)
            try:
                staged_changes = self.run_git(["diff", "--cached", "--name-status"], cwd=self.repo_root)
                if staged_changes.strip():
                    # Deduplicate files_removed list and create commit message
                    unique_files_removed = list(set(files_removed))
                    commit_message = f"Remove private content from {branch_name} branch\n\nRemoved {len(unique_files_removed)} files:\n"
                    for file_path in unique_files_removed[:10]:  # Show first 10 files
                        commit_message += f"- {file_path}\n"
                    if len(unique_files_removed) > 10:
                        commit_message += f"... and {len(unique_files_removed) - 10} more files\n"
                    commit_message += "\nUpdated .gitignore for public branch protection"
                    
                    self.run_git(["commit", "-m", commit_message], cwd=self.repo_root)
                    self.logger.info(f"Committed removal of {len(unique_files_removed)} private files from {branch_name}")
                else:
                    self.logger.info(f"No private content found to remove from {branch_name}")
            except Exception as e:
                self.logger.error(f"CRITICAL: Failed to commit private content removal: {e}")
                raise
            
            self.logger.info(f"Successfully created clean public branch '{branch_name}'")
            
        except Exception as e:
            self.logger.error(f"Failed to create clean public branch '{branch_name}': {str(e)}")
            # Try to switch back to original branch
            try:
                self.run_git(["checkout", current_branch], cwd=self.repo_root, check=False)
            except:
                pass
            raise

    def _verify_clean_branch(self, branch_name: str) -> bool:
        """
        Verify that a branch does not contain private content using existing guardrails.
        
        This method uses the existing BranchContext infrastructure to check for private
        content by examining what git actually tracks, not just the working directory.
        
        Args:
            branch_name: Name of the branch to verify
            
        Returns:
            True if branch is clean, False if private content found
        """
        # Import here to avoid circular dependencies
        from .branch_utils import BranchContext
        
        try:
            # Check current branch
            current_branch = self.run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=self.repo_root).strip()
            
            # Switch to target branch for verification
            self.run_git(["checkout", branch_name], cwd=self.repo_root)
            
            # Use existing BranchContext with configuration for verification
            context = BranchContext(self.repo_root, self._get_branch_config())
            
            # Check what git actually tracks (git index), not working directory
            tracked_files = self.run_git(["ls-files"], cwd=self.repo_root).splitlines()
            
            # Use existing guardrails logic to identify private files
            # (vendored upstream code is never private)
            private_files = [(f, r) for f, r in context.check_private_files(tracked_files)
                             if not self._is_vendored(f)]

            # Switch back to original branch
            self.run_git(["checkout", current_branch], cwd=self.repo_root)
            
            if private_files:
                self.logger.error(f"Branch '{branch_name}' contains {len(private_files)} private files in git index:")
                for file_path, reason in private_files:
                    self.logger.error(f"  {file_path}: {reason}")
                return False
            
            self.logger.info(f"Branch '{branch_name}' verification passed - no private content found")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to verify branch '{branch_name}': {str(e)}")
            return False

    def _update_gitignore_for_public_branch(self, context) -> None:
        """
        Update .gitignore with private content patterns using BranchContext.
        
        Args:
            context: BranchContext instance to get patterns from
        """
        gitignore_path = os.path.join(self.repo_root, ".gitignore")
        gitignore_content = []
        
        # Read existing .gitignore if it exists
        if os.path.exists(gitignore_path):
            with open(gitignore_path, "r") as f:
                gitignore_content = f.readlines()
        
        # Add private content protection section using BranchContext patterns
        protection_marker = "# RepoKit Private Content Protection (DO NOT REMOVE)\n"
        if protection_marker not in "".join(gitignore_content):
            gitignore_content.append("\n")
            gitignore_content.append(protection_marker)
            
            # Add patterns from BranchContext
            for pattern in context.PRIVATE_PATTERNS:
                if pattern not in "".join(gitignore_content):
                    gitignore_content.append(f"{pattern}\n")
            
            for pattern in context.EXCLUDE_FROM_PUBLIC:
                if pattern not in "".join(gitignore_content):
                    gitignore_content.append(f"{pattern}\n")
            
            # Write updated .gitignore
            with open(gitignore_path, "w") as f:
                f.writelines(gitignore_content)
            
            # Stage .gitignore changes
            self.run_git(["add", ".gitignore"], cwd=self.repo_root)
            self.logger.debug("Updated .gitignore with private content protection patterns")

    def _get_branch_config(self) -> Dict:
        """
        Get branch configuration for BranchContext from repo configuration.
        
        Returns:
            Dictionary with branch and pattern configuration
        """
        private_branches = list(self.config.get('private_branches', DEFAULT_PRIVATE_BRANCHES))
        # This repository's own private branch (a strategy's, or
        # --private-branch) must count as private, or the guard treats a
        # custom name as public and refuses the private branch's own commits.
        if self.private_branch and self.private_branch not in private_branches:
            private_branches.append(self.private_branch)

        return {
            'private_branches': private_branches,
            'public_branches': self.config.get('public_branches', DEFAULT_PUBLIC_BRANCHES),
            'private_patterns': self.config.get('private_patterns', DEFAULT_PRIVATE_PATTERNS),
            'exclude_from_public': self.config.get('exclude_from_public', DEFAULT_EXCLUDE_FROM_PUBLIC)
        }

    def _has_changes(self, directory: str) -> bool:
        """
        Check if there are uncommitted changes in the repository.

        Args:
            directory: Directory to check

        Returns:
            True if there are changes, False otherwise
        """
        try:
            # Check for any changes (staged or unstaged)
            output = self.run_git(["status", "--porcelain"], cwd=directory, check=False)
            return bool(output and output.strip())
        except Exception:
            # In case of error, assume there are changes
            return True

    def _print_next_steps(self) -> None:
        """Print next steps for the user."""
        print("\n" + "=" * 80)
        print(f"Repository {self.project_name} has been set up successfully!")

        if not self.private_branch:
            # Flat layout (main-only)
            print(f"\nRepository: {self.repo_root}  (branch: main)")
            print("Private work goes in private/, which git ignores.")
            print("\nNext steps:")
            print("1. Set up a remote GitHub repository")
            print("2. Add it as a remote and push:")
            print(f"   cd {self.repo_root}")
            print("   git remote add origin https://github.com/username/repo.git")
            print("   git push -u origin main")
            print("=" * 80)
            return

        print("\nDirectory structure:")
        print(f"  {self.project_name}/")

        # Use ASCII characters instead of Unicode box-drawing characters
        # This avoids encoding errors on Windows command prompt
        print(
            f"  |-- local/          # Main repository ({self.config.get('private_branch', 'private')} branch)"
        )

        if self.config.get("github", True):
            print(f"  |-- github/         # GitHub worktree (main branch)")

        worktree_branches = self.config.get("worktrees", ["main", "dev"])
        for branch in worktree_branches:
            if branch != "main" or not self.config.get(
                "github", True
            ):  # Skip main if github is enabled
                print(f"  |-- {branch}/           # {branch} branch worktree")

        print("\nNext steps:")
        print("1. Set up a remote GitHub repository")
        print("2. Add it as a remote:")
        print(f"   cd {self.repo_root}")
        print("   git remote add origin https://github.com/username/repo.git")
        print("3. Push your branches:")
        print("   git push -u origin main")
        print("   git push -u origin dev")

        private_branch = self.config.get("private_branch", "private")
        print(
            f"\nRemember: The '{private_branch}' branch is for your local work only and should not be pushed!"
        )
        print("=" * 80)

    def bootstrap_repository(self, source_dir: Optional[str] = None) -> bool:
        """
        Bootstrap a repository with essential files from a source directory.

        This is used to set up the repository with existing code, typically
        used to bootstrap RepoKit itself or to convert an existing project
        to use RepoKit's structure.

        Args:
            source_dir: Source directory containing the files to copy
                    (default: current directory)

        Returns:
            True if successful, False otherwise
        """
        try:
            self.logger.info(f"Bootstrapping repository from {source_dir}")

            # Default to current directory if not specified
            if not source_dir:
                source_dir = os.getcwd()

            # First set up the repository structure
            if not self.setup_repository():
                self.logger.error("Failed to set up repository structure")
                return False

            # Import utils module (avoid circular imports)
            from .utils import copy_files, get_essential_file_patterns

            # Get essential file patterns
            patterns = get_essential_file_patterns()

            # Copy essential files to repository
            copied = copy_files(
                source_dir,
                self.repo_root,
                include_patterns=patterns["include"],
                exclude_patterns=patterns["exclude"],
            )

            if copied == 0:
                self.logger.warning("No files were copied during bootstrap")
                return False

            # Create a commit with the copied files
            try:
                self.run_git(["add", "."], cwd=self.repo_root)
                self.run_git(
                    ["commit", "-m", "Bootstrap repository with source files"],
                    cwd=self.repo_root,
                )
                self.logger.info("Committed bootstrap files")

                # Update branches from private
                self._update_branches_from_private()

                # Update worktrees to match their branches
                self._update_worktrees()
            except Exception as e:
                self.logger.error(f"Error committing bootstrap files: {str(e)}")
                return False

            self.logger.info("Repository bootstrap complete")
            return True
        except Exception as e:
            self.logger.error(f"Error bootstrapping repository: {str(e)}")
            return False

    def _update_branches_from_private(self) -> None:
        """
        Update all branches from the private branch.

        This is used after committing bootstrap files to ensure all branches
        have the same content.
        """
        private_branch = self.config.get("private_branch", "private")
        branches = self.config.get(
            "branches", ["main", "dev", "staging", "test", "live"]
        )

        # Get current branch
        current_branch = self.run_git(["branch", "--show-current"], cwd=self.repo_root)

        # Get the commit hash of the private branch for reset operations
        private_hash = self.run_git(["rev-parse", private_branch], cwd=self.repo_root)

        for branch in branches:
            if branch != private_branch:
                try:
                    # Check if the branch is checked out in a worktree
                    if self._is_branch_in_worktree(branch):
                        # For branches in worktrees, we need to update them directly in the worktree
                        worktree_path = self._get_worktree_path(branch)
                        if worktree_path:
                            # Use a more forceful update approach
                            self.logger.info(
                                f"Updating branch '{branch}' in worktree {worktree_path}"
                            )

                            # First fetch the changes from the main repository
                            self.run_git(
                                ["fetch", "..", private_branch],
                                cwd=worktree_path,
                                check=False,
                            )

                            # Then hard reset to the private branch commit
                            self.run_git(
                                ["reset", "--hard", private_hash],
                                cwd=worktree_path,
                                check=False,
                            )

                            # Verify the update worked
                            current_hash = self.run_git(
                                ["rev-parse", "HEAD"], cwd=worktree_path, check=False
                            )
                            if current_hash == private_hash:
                                self.logger.info(
                                    f"Updated branch '{branch}' from {private_branch}"
                                )
                            else:
                                self.logger.warning(
                                    f"Failed to update branch '{branch}' to match {private_branch}"
                                )
                    else:
                        # For branches not in worktrees, we can update them directly
                        self.run_git(["checkout", branch], cwd=self.repo_root)
                        self.run_git(
                            ["reset", "--hard", private_branch], cwd=self.repo_root
                        )
                        self.logger.info(
                            f"Updated branch '{branch}' from {private_branch}"
                        )
                except Exception as e:
                    self.logger.warning(f"Failed to update branch '{branch}': {str(e)}")

        # Return to original branch
        if current_branch != self.run_git(
            ["branch", "--show-current"], cwd=self.repo_root
        ):
            self.run_git(["checkout", current_branch], cwd=self.repo_root)

    def _update_worktrees(self) -> None:
        """
        Update all worktrees to match their corresponding branches.

        This ensures that all worktree directories reflect the latest state
        of their branches.
        """
        # Check if we have worktrees
        worktree_output = self.run_git(
            ["worktree", "list"], cwd=self.repo_root, check=False
        )
        if not worktree_output:
            return

        # Parse worktree list
        worktrees = {}
        for line in worktree_output.split("\n"):
            if not line.strip():
                continue

            # Parse worktree line (format: "/path/to/worktree  abcd1234 [branch]")
            parts = line.split()
            if len(parts) >= 3 and "[" in parts[2] and "]" in parts[2]:
                path = parts[0]
                branch = parts[2].strip("[]")
                worktrees[branch] = path

        # Update each worktree
        for branch, path in worktrees.items():
            if branch == self.config.get("private_branch", "private"):
                # Skip private branch
                continue

            try:
                # Force synchronization with the branch from the main repository
                branch_hash = self.run_git(["rev-parse", branch], cwd=self.repo_root)

                # Make sure worktree has latest changes from its branch
                self.run_git(["reset", "--hard", branch_hash], cwd=path, check=False)
                self.run_git(["clean", "-fd"], cwd=path, check=False)

                # Verify the update worked
                current_hash = self.run_git(
                    ["rev-parse", "HEAD"], cwd=path, check=False
                )
                if current_hash == branch_hash:
                    self.logger.info(
                        f"Updated worktree for branch '{branch}' at {path}"
                    )
                else:
                    self.logger.warning(
                        f"Failed to update worktree for branch '{branch}' at {path}"
                    )
            except Exception as e:
                self.logger.warning(
                    f"Failed to update worktree for branch '{branch}': {str(e)}"
                )

    def _is_branch_in_worktree(self, branch: str) -> bool:
        """
        Check if a branch is currently checked out in a worktree.

        Args:
            branch: Branch name to check

        Returns:
            True if the branch is checked out in a worktree, False otherwise
        """
        try:
            # Get worktree list
            worktree_output = self.run_git(
                ["worktree", "list"], cwd=self.repo_root, check=False
            )

            # Check if branch is in any worktree
            for line in worktree_output.split("\n"):
                if f"[{branch}]" in line:
                    return True

            return False
        except Exception:
            # If we can't determine, assume it's not in a worktree
            return False

    def _get_worktree_path(self, branch: str) -> Optional[str]:
        """
        Get the path to the worktree containing a branch.

        Args:
            branch: Branch name

        Returns:
            Path to the worktree or None if the branch is not in a worktree
        """
        try:
            # Get worktree list
            worktree_output = self.run_git(
                ["worktree", "list"], cwd=self.repo_root, check=False
            )

            # Find worktree with this branch
            for line in worktree_output.split("\n"):
                if f"[{branch}]" in line:
                    # Extract path from line (it's the first part)
                    return line.split()[0]

            return None
        except Exception:
            # If we can't determine, return None
            return None

    def publish_repository(
        self,
        service: str = "github",
        remote_name: str = "origin",
        private: bool = False,
        push_branches: bool = True,
        organization: Optional[str] = None,
        token_command: Optional[str] = None,
        credentials_file: Optional[str] = None,
    ) -> bool:
        """
        Set up remote repository and push branches.

        This is a convenience method that wraps RemoteIntegration functionality
        directly in the RepoManager class.

        Args:
            service: Remote service ("github" or "gitlab")
            remote_name: Name for the remote
            private: Whether the repository should be private
            push_branches: Whether to push branches
            organization: Organization or group name
            token_command: Command to retrieve token
            credentials_file: Path to credentials file

        Returns:
            True if successful, False otherwise
        """
        try:
            # Import RemoteIntegration (avoid circular imports)
            from .remote_integration import RemoteIntegration

            # Initialize remote integration
            remote_integration = RemoteIntegration(
                self, credentials_file=credentials_file, verbose=self.verbose
            )

            # Set up remote repository
            success = remote_integration.setup_remote_repository(
                service=service,
                remote_name=remote_name,
                private=private,
                push_branches=push_branches,
                organization=organization,
                token_command=token_command,
            )

            if not success:
                self.logger.error(f"Failed to publish repository to {service}")
                return False

            self.logger.info(f"Successfully published repository to {service}")
            return True
        except Exception as e:
            self.logger.error(f"Error publishing repository: {str(e)}")
            return False

    def _generate_ai_templates(self) -> None:
        """Generate AI integration templates (only in private branch)."""
        ai_provider = self.config.get("ai_integration", "").lower()
        if not ai_provider or ai_provider == "none":
            return

        self.logger.info(f"Generating AI integration files for: {ai_provider}")

        # Create private/claude directory structure
        if ai_provider == "claude":
            claude_dir = os.path.join(self.repo_root, "private", "claude")
            instructions_dir = os.path.join(claude_dir, "instructions")
            os.makedirs(instructions_dir, exist_ok=True)

            # Context for AI templates
            import datetime

            context = {
                "project_name": self.project_name,
                "description": self.config.get("description", "A new project"),
                "language": self.config.get("language", "generic"),
                "date": datetime.datetime.now().strftime("%Y-%m-%d"),
                "test_command": self._get_test_command(),
                "lint_command": self._get_lint_command(),
                "build_command": self._get_build_command(),
            }

            # Generate CLAUDE.md
            self.template_engine.render_template_to_file(
                "CLAUDE.md",
                os.path.join(self.repo_root, "CLAUDE.md"),
                context,
                category=f"ai/{ai_provider}",
            )

            # Copy instruction files
            instruction_files = [
                "step1_context_rebuilder.md",
                "step2_dev_workflow_process.md",
                "step3_context_bridge.md",
            ]

            for instruction_file in instruction_files:
                # Try to get template path - for instruction files, try without .template extension first
                src_path = os.path.join(
                    self.template_engine.templates_dir,
                    f"ai/{ai_provider}/instructions",
                    instruction_file,
                )
                if not os.path.exists(src_path):
                    # Try with template engine's path finding
                    src_path = self.template_engine.get_template_path(
                        instruction_file, category=f"ai/{ai_provider}/instructions"
                    )

                if src_path and os.path.exists(src_path):
                    dest_path = os.path.join(instructions_dir, instruction_file)
                    shutil.copy2(src_path, dest_path)
                    self.logger.debug(f"Copied instruction file: {instruction_file}")

            # With no private branch these files would be committed straight to
            # main, the public branch: leave them on disk, uncommitted.
            if not self.private_branch:
                self.logger.info(
                    "AI integration files written but not committed (no private branch)"
                )
                return

            # Add files to git (use -f for private directory since it's in .gitignore).
            # In nested mode private/ is its own repository: its files are the
            # vault's to commit, never this repository's.
            self.run_git(["add", "CLAUDE.md"], cwd=self.repo_root)
            if self.private_mode != "nested":
                self.run_git(["add", "-f", "private/claude/"], cwd=self.repo_root)

            # Only commit if not in adoption mode (in adoption, user commits manually)
            if not self.config.get("is_adoption", False):
                # Commit AI integration files
                self.run_git(
                    ["commit", "-m", "Add Claude AI integration files"], cwd=self.repo_root
                )
            else:
                self.logger.info("AI files staged for adoption - commit manually when ready")

            self.logger.info("AI integration files generated successfully")

    def _get_test_command(self) -> str:
        """Get the appropriate test command for the language."""
        language = self.config.get("language", "generic")
        commands = {
            "python": "pytest",
            "javascript": "npm test",
            "generic": "# Add your test command here",
        }
        return commands.get(language, commands["generic"])

    def _get_lint_command(self) -> str:
        """Get the appropriate lint command for the language."""
        language = self.config.get("language", "generic")
        commands = {
            "python": "black . && flake8",
            "javascript": "npm run lint",
            "generic": "# Add your lint command here",
        }
        return commands.get(language, commands["generic"])

    def _get_build_command(self) -> str:
        """Get the appropriate build command for the language."""
        language = self.config.get("language", "generic")
        commands = {
            "python": "python setup.py build",
            "javascript": "npm run build",
            "generic": "# Add your build command here",
        }
        return commands.get(language, commands["generic"])

    def _cleanup_sensitive_files(self, branch_context: Optional[str] = None, dry_run: bool = False) -> Dict[str, List[str]]:
        """
        Branch-aware cleanup of sensitive files during repository adoption.
        
        This method performs intelligent cleanup based on branch context:
        - For private branches: Only clean git index, preserve working directory
        - For public branches: Clean both working directory and git index
        
        Args:
            branch_context: Branch we're cleaning for (e.g. 'private', 'dev', 'main')
            dry_run: If True, only report what would be cleaned
            
        Returns:
            Dictionary with 'working_dir' and 'git_index' lists of cleaned files
        """
        import fnmatch
        from pathlib import Path
        
        # Set up detailed logging for debugging
        cleanup_logger = logging.getLogger("repokit.cleanup")
        
        cleanup_logger.info(f"Starting sensitive file cleanup (branch: {branch_context}, dry_run: {dry_run})")
        
        cleanup_results = {
            "working_dir": [],
            "git_index": []
        }
        
        # Get patterns to clean - use DEFAULT_SENSITIVE_PATTERNS for consistency
        patterns_to_clean = DEFAULT_SENSITIVE_PATTERNS.copy()
        
        # Add any additional patterns from config
        config_patterns = self.config.get("sensitive_patterns", [])
        if config_patterns:
            patterns_to_clean.extend(config_patterns)
        
        # Determine if this is a private branch (this repository's own private
        # branch counts, whatever its name -- e.g. --private-branch scratch)
        private_branches = DEFAULT_PRIVATE_BRANCHES + self.config.get("private_branches", [])
        if self.private_branch and self.private_branch not in private_branches:
            private_branches = private_branches + [self.private_branch]
        is_private_branch = branch_context in private_branches
        
        cleanup_logger.info(f"Branch context: {branch_context}")
        cleanup_logger.info(f"Is private branch: {is_private_branch}")
        cleanup_logger.info(f"Using {len(patterns_to_clean)} sensitive patterns: {patterns_to_clean}")
        
        # For private branches, we preserve working directory files but clean git index
        # For public branches, we clean both working directory and git index
        clean_working_dir = not is_private_branch
        clean_git_index = True  # Always clean git index
        
        cleanup_logger.info(f"Will clean working directory: {clean_working_dir}")
        cleanup_logger.info(f"Will clean git index: {clean_git_index}")
        
        # Clean working directory files (only for public branches)
        if clean_working_dir:
            cleanup_logger.debug("Scanning working directory for sensitive files")
            for root, dirs, files in os.walk(self.repo_root):
                # Skip .git directory
                if ".git" in root.split(os.sep):
                    continue
                    
                for file in files:
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, self.repo_root)
                    if self._is_vendored(relative_path):
                        continue

                    # Check if file matches any sensitive pattern
                    should_remove = False
                    matching_pattern = None
                    
                    for pattern in patterns_to_clean:
                        # Cross-platform pattern matching using normalized paths
                        normalized_relative = str(Path(relative_path)).replace('\\', '/')
                        normalized_pattern = pattern.replace('\\', '/')
                        
                        # Check multiple match approaches for cross-platform compatibility
                        matches = [
                            fnmatch.fnmatch(normalized_relative, normalized_pattern),  # Full path
                            fnmatch.fnmatch(file, normalized_pattern),                 # Filename only
                            fnmatch.fnmatch(str(Path(file)), normalized_pattern),     # Filename as Path
                        ]
                        
                        if any(matches):
                            should_remove = True
                            matching_pattern = pattern
                            if self.verbose >= 3:
                                cleanup_logger.debug(f"Pattern '{pattern}' matched file '{relative_path}' (normalized: '{normalized_relative}')")
                            break
                    
                    if should_remove:
                        cleanup_results["working_dir"].append(relative_path)
                        
                        if dry_run:
                            cleanup_logger.info(f"Would remove (working dir): {relative_path} (pattern: {matching_pattern})")
                        else:
                            try:
                                os.remove(file_path)
                                cleanup_logger.debug(f"Removed (working dir): {relative_path} (pattern: {matching_pattern})")
                            except Exception as e:
                                cleanup_logger.warning(f"Failed to remove {relative_path}: {str(e)}")
        else:
            cleanup_logger.info("Skipping working directory cleanup (private branch - files preserved)")
        
        # Clean git index files (always done)
        if clean_git_index:
            cleanup_logger.debug("Scanning git index for sensitive files")
            try:
                # Get list of files tracked by git
                tracked_files = self.run_git(["ls-files"], cwd=self.repo_root).splitlines()
                
                files_to_remove_from_index = []
                
                for tracked_file in tracked_files:
                    if self._is_vendored(tracked_file):
                        continue
                    # Check if tracked file matches any sensitive pattern
                    should_remove = False
                    matching_pattern = None
                    
                    for pattern in patterns_to_clean:
                        # Cross-platform pattern matching using normalized paths (same as working directory)
                        normalized_tracked = str(Path(tracked_file)).replace('\\', '/')
                        normalized_pattern = pattern.replace('\\', '/')
                        
                        # Check multiple match approaches for cross-platform compatibility
                        matches = [
                            fnmatch.fnmatch(normalized_tracked, normalized_pattern),  # Full path
                            fnmatch.fnmatch(os.path.basename(tracked_file), normalized_pattern),  # Filename only
                            fnmatch.fnmatch(str(Path(tracked_file)), normalized_pattern),  # Filename as Path
                        ]
                        
                        if any(matches):
                            should_remove = True
                            matching_pattern = pattern
                            if self.verbose >= 3:
                                cleanup_logger.debug(f"Pattern '{pattern}' matched tracked file '{tracked_file}' (normalized: '{normalized_tracked}')")
                            break
                    
                    if should_remove:
                        cleanup_results["git_index"].append(tracked_file)
                        files_to_remove_from_index.append(tracked_file)
                        
                        if dry_run:
                            cleanup_logger.info(f"Would remove (git index): {tracked_file} (pattern: {matching_pattern})")
                        else:
                            cleanup_logger.debug(f"Marking for git index removal: {tracked_file} (pattern: {matching_pattern})")
                
                # Remove files from git index in batch
                if files_to_remove_from_index and not dry_run:
                    try:
                        for file_to_remove in files_to_remove_from_index:
                            file_full_path = os.path.join(self.repo_root, file_to_remove)
                            if not os.path.exists(file_full_path) or clean_working_dir:
                                # File was removed from working dir or we don't want to preserve it
                                self.run_git(["rm", "--cached", "--ignore-unmatch", file_to_remove], cwd=self.repo_root)
                                cleanup_logger.debug(f"Removed from git index: {file_to_remove}")
                            else:
                                # File still exists in working dir and we want to preserve it
                                self.run_git(["rm", "--cached", file_to_remove], cwd=self.repo_root)
                                cleanup_logger.debug(f"Removed from git index (preserved in working dir): {file_to_remove}")
                        
                        cleanup_logger.info(f"Removed {len(files_to_remove_from_index)} files from git index")
                    except Exception as e:
                        cleanup_logger.error(f"Failed to remove files from git index: {str(e)}")
                            
            except Exception as e:
                cleanup_logger.warning(f"Failed to scan git index: {str(e)}")
        
        # Log summary
        total_cleaned = len(cleanup_results["working_dir"]) + len(cleanup_results["git_index"])
        action_word = "Would clean" if dry_run else "Cleaned"
        cleanup_logger.info(f"{action_word} {total_cleaned} sensitive files total")
        cleanup_logger.info(f"  Working directory: {len(cleanup_results['working_dir'])} files")
        cleanup_logger.info(f"  Git index: {len(cleanup_results['git_index'])} files")
        
        # Show some example files cleaned (for debugging)
        if self.verbose >= 2 and not dry_run:
            all_cleaned = cleanup_results["working_dir"] + cleanup_results["git_index"]
            if all_cleaned:
                cleanup_logger.info("Example files cleaned:")
                for file_path in all_cleaned[:5]:
                    cleanup_logger.info(f"  - {file_path}")
                if len(all_cleaned) > 5:
                    cleanup_logger.info(f"  ... and {len(all_cleaned) - 5} more")
        
        return cleanup_results
    
    def _log_cleanup_summary(self, cleanup_results: Dict[str, List[str]], gitkeep_results: Dict[str, List[str]]) -> None:
        """
        Log comprehensive cleanup summary for adoption process.
        
        Args:
            cleanup_results: Results from _cleanup_sensitive_files()
            gitkeep_results: Results from manage_gitkeep_files()
        """
        self.logger.info("=== REPOSITORY ADOPTION CLEANUP SUMMARY ===")
        
        # Sensitive files cleanup summary
        total_sensitive = len(cleanup_results.get("working_dir", [])) + len(cleanup_results.get("git_index", []))
        if total_sensitive > 0:
            self.logger.info(f"Cleaned {total_sensitive} sensitive files:")
            
            if cleanup_results.get("working_dir"):
                self.logger.info(f"  Working directory: {len(cleanup_results['working_dir'])} files")
                if self.verbose >= 2:
                    for file_path in cleanup_results["working_dir"][:5]:
                        self.logger.info(f"    - {file_path}")
                    if len(cleanup_results["working_dir"]) > 5:
                        self.logger.info(f"    ... and {len(cleanup_results['working_dir']) - 5} more")
            
            if cleanup_results.get("git_index"):
                self.logger.info(f"  Git index: {len(cleanup_results['git_index'])} files")
                if self.verbose >= 2:
                    for file_path in cleanup_results["git_index"][:5]:
                        self.logger.info(f"    - {file_path}")
                    if len(cleanup_results["git_index"]) > 5:
                        self.logger.info(f"    ... and {len(cleanup_results['git_index']) - 5} more")
        else:
            self.logger.info("No sensitive files found to clean")
        
        # .gitkeep management summary
        total_gitkeep = len(gitkeep_results.get("added", [])) + len(gitkeep_results.get("removed", []))
        if total_gitkeep > 0:
            self.logger.info(f"Managed {total_gitkeep} .gitkeep files:")
            
            if gitkeep_results.get("added"):
                self.logger.info(f"  Added to empty directories: {len(gitkeep_results['added'])} files")
                if self.verbose >= 2:
                    for file_path in gitkeep_results["added"][:3]:
                        self.logger.info(f"    + {file_path}")
                    if len(gitkeep_results["added"]) > 3:
                        self.logger.info(f"    ... and {len(gitkeep_results['added']) - 3} more")
            
            if gitkeep_results.get("removed"):
                self.logger.info(f"  Removed from non-empty directories: {len(gitkeep_results['removed'])} files")
                if self.verbose >= 2:
                    for file_path in gitkeep_results["removed"][:3]:
                        self.logger.info(f"    - {file_path}")
                    if len(gitkeep_results["removed"]) > 3:
                        self.logger.info(f"    ... and {len(gitkeep_results['removed']) - 3} more")
        else:
            self.logger.info("No .gitkeep file changes needed")
        
        self.logger.info("=== END CLEANUP SUMMARY ===")

    def _generate_repokit_config(self) -> None:
        """
        Generate .repokit.json configuration file with RepoKit signature.
        
        This file serves as the definitive marker that a project is RepoKit-managed
        and contains metadata about the RepoKit setup.
        """
        import datetime
        
        config_path = os.path.join(self.repo_root, ".repokit.json")
        
        # Build configuration with RepoKit signature
        from . import __version__
        repokit_config = {
            "repokit_managed": True,
            "generated_by": "repokit",
            "version": __version__,  # Current RepoKit version
            "created_at": datetime.datetime.now().isoformat() + "Z",
            "project_name": self.project_name,
            "language": self.config.get("language", "generic"),
            "languages": self.config.get("languages") or [self.config.get("language", "generic")],
            "archetype": self.config.get("archetype"),
            "branch_strategy": self.config.get("branch_strategy", "standard"),
            "private_branch": self.config.get("private_branch", "private"),
            "private_mode": self.private_mode,
            "repokit_common": self.common_vendored,
        }
        
        # Add additional config if available
        if self.config.get("description"):
            repokit_config["description"] = self.config["description"]
        
        if self.config.get("user"):
            repokit_config["author"] = self.config["user"]
        
        # Write configuration file
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(repokit_config, f, indent=2)
            
            self.logger.info(f"Generated RepoKit configuration: {config_path}")
            
        except Exception as e:
            self.logger.warning(f"Failed to generate RepoKit configuration: {str(e)}")

    def _generate_badges(self, language: str) -> str:
        """Generate GitHub workflow badges based on language and configuration."""
        # Get GitHub username from config if available
        github_config = self.config.get("github", {})
        if not isinstance(github_config, dict):
            github_config = {}
        github_user = github_config.get("username", "YOUR_GITHUB_USERNAME")

        # Base badges
        badges = []
        badge_links = []

        # Workflow status badge, for the CI file the code-type layers write
        # (ci-<language>.yml); a project with no CI gets no workflow badge.
        workflow = self._ci_workflow()
        if workflow:
            badges.append("[![GitHub Workflow Status][workflow-badge]][workflow-url]")
            badge_links.extend(
                [
                    f"[workflow-badge]: https://github.com/{github_user}/{self.project_name}/actions/workflows/{workflow}/badge.svg",
                    f"[workflow-url]: https://github.com/{github_user}/{self.project_name}/actions",
                ]
            )

        # Version badge
        badges.append("[![Version][version-badge]][version-url]")
        badge_links.extend(
            [
                "[version-badge]: https://img.shields.io/badge/version-1.0.0-blue",
                f"[version-url]: https://github.com/{github_user}/{self.project_name}/releases",
            ]
        )

        # Language-specific badges
        if language == "python":
            badges.append("[![Python][python-badge]][python-url]")
            badge_links.extend(
                [
                    "[python-badge]: https://img.shields.io/badge/python-%3E%3D3.7-darkgreen",
                    "[python-url]: https://python.org/downloads",
                ]
            )
        elif language == "javascript":
            badges.append("[![Node][node-badge]][node-url]")
            badge_links.extend(
                [
                    "[node-badge]: https://img.shields.io/badge/node-%3E%3D14.0.0-darkgreen",
                    "[node-url]: https://nodejs.org/en/download",
                ]
            )
        elif language == "java":
            badges.append("[![Java][java-badge]][java-url]")
            badge_links.extend(
                [
                    "[java-badge]: https://img.shields.io/badge/java-%3E%3D11-darkgreen",
                    "[java-url]: https://openjdk.java.net",
                ]
            )
        else:
            badges.append("[![Build][build-badge]][build-url]")
            badge_links.extend(
                [
                    "[build-badge]: https://img.shields.io/badge/build-passing-brightgreen",
                    f"[build-url]: https://github.com/{github_user}/{self.project_name}/actions",
                ]
            )

        # License badge
        badges.append("[![License][license-badge]][license-url]")
        badge_links.extend(
            [
                "[license-badge]: https://img.shields.io/badge/license-MIT-orange",
                f"[license-url]: https://github.com/{github_user}/{self.project_name}/blob/main/LICENSE",
            ]
        )

        # Discussions badge
        badges.append("[![GitHub Discussions][discussions-badge]][discussions-url]")
        badge_links.extend(
            [
                "[discussions-badge]: https://img.shields.io/badge/discussions-Welcome-lightgrey",
                f"[discussions-url]: https://github.com/{github_user}/{self.project_name}/discussions",
            ]
        )

        # Combine badges and links
        badge_section = "\n".join(badges) + "\n\n" + "\n".join(badge_links)

        return badge_section
