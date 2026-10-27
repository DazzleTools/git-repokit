#!/usr/bin/env python3
"""
Branch utilities for RepoKit.

Provides branch detection and validation for private content protection.
"""

import subprocess
import os
from typing import Set, List, Dict, Optional, Tuple

# Lines RepoKit writes into .git/info/exclude for either branch type. Anything
# else in the file belongs to the user (or another tool) and is kept.
_REPOKIT_EXCLUDE_LINES = {
    "CLAUDE.md", "private/claude/", "private/docs/", "private/notes/", "private/temp/",
    "revisions/", "test-runs/", "test_runs/",
    "# AI integration files", "# Development conversation logs",
    "# Private development documentation", "# Development notes and temporary files",
    "# Revision history (private branch only)", "# Test artifacts", "# Test artifacts (not needed in git)",
    "# Private branches can contain all content",
    "# These files are tracked in 'private' branch but ignored in public branches",
}


def _write_excludes(exclude_file: str, excludes: List[str]) -> None:
    """Write RepoKit's branch excludes, keeping every line that is not RepoKit's.

    The file used to be overwritten, which silently dropped the user's own
    excludes (and git's template comments) each time branch excludes were set up.
    """
    kept: List[str] = []
    if os.path.exists(exclude_file):
        with open(exclude_file, encoding="utf-8", errors="replace") as f:
            for line in f.read().splitlines():
                stripped = line.strip()
                if stripped.startswith("# RepoKit:") or stripped in _REPOKIT_EXCLUDE_LINES:
                    continue
                kept.append(line)
    while kept and not kept[-1].strip():
        kept.pop()
    while kept and not kept[0].strip():
        kept.pop(0)
    with open(exclude_file, "w", encoding="utf-8") as f:
        f.write("\n".join(kept + ([""] if kept else []) + excludes) + "\n")


class BranchContext:
    """Manages branch context and security rules with configurable patterns."""
    
    def __init__(self, repo_path: str = '.', config: Optional[Dict] = None):
        """
        Initialize branch context for given repository.
        
        Args:
            repo_path: Path to the repository
            config: Optional configuration dictionary to override default patterns
        """
        self.repo_path = os.path.abspath(repo_path)
        self._current_branch = None
        self._branch_type = None
        
        # Load configuration or use defaults
        config = config or {}
        
        # Configure private branches (can contain private content)
        self.PRIVATE_BRANCHES = set(config.get('private_branches', ['private', 'local']))
        
        # Configure public branches (must not contain private content)
        self.PUBLIC_BRANCHES = set(config.get('public_branches', 
            ['main', 'master', 'dev', 'test', 'staging', 'live', 'prod', 'production']))
        
        # Configure private content patterns
        self.PRIVATE_PATTERNS = set(config.get('private_patterns', {
            'CLAUDE.md',
            'private/',
            'convos/',
            'logs/',
            'credentials/',
            'secrets/',
            '.env.local',
            '.env.private',
            '**/__private__*',
            '**/private_*',
        }))
        
        # Configure exclude patterns for public branches
        self.EXCLUDE_FROM_PUBLIC = set(config.get('exclude_from_public', {
            'CLAUDE.md',
            'private/claude/',
            'private/docs/',
            'private/notes/',
            'private/temp/',
            'revisions/',
            'test-runs/',
            'test_runs/',
        }))
    
    @property
    def current_branch(self) -> str:
        """Get current branch name."""
        if self._current_branch is None:
            self._current_branch = self._get_current_branch()
        return self._current_branch
    
    @property
    def branch_type(self) -> str:
        """Get branch type: 'private', 'public', or 'unknown'."""
        if self._branch_type is None:
            self._branch_type = self._determine_branch_type()
        return self._branch_type
    
    def _get_current_branch(self) -> str:
        """Get current git branch name."""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return 'unknown'
    
    def _determine_branch_type(self) -> str:
        """Determine if current branch is private, public, or unknown."""
        branch = self.current_branch.lower()
        
        # Check explicit private branches
        if branch in self.PRIVATE_BRANCHES:
            return 'private'
        
        # Check explicit public branches
        if branch in self.PUBLIC_BRANCHES:
            return 'public'
        
        # Check patterns
        if branch.startswith('private/') or branch.startswith('local/'):
            return 'private'
        
        if branch.startswith('feature/') or branch.startswith('feat/'):
            return 'private'  # Feature branches can have private content
        
        # Default to public for safety
        return 'public'
    
    def is_private_branch(self) -> bool:
        """Check if current branch allows private content."""
        return self.branch_type == 'private'
    
    def is_public_branch(self) -> bool:
        """Check if current branch must not have private content."""
        return self.branch_type == 'public'
    
    def get_staged_files(self) -> List[str]:
        """Files the commit adds or changes (0.9.12: deletions are left out --
        removing a private file from a public branch is what the guard wants,
        not something to refuse)."""
        try:
            result = subprocess.run(
                ['git', 'diff', '--cached', '--name-only', '--diff-filter=ACMR'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
        except subprocess.CalledProcessError:
            return []
    
    def check_private_files(self, files: List[str]) -> List[Tuple[str, str]]:
        """
        Check if files contain private content.
        
        Returns list of (file, reason) tuples for files that are private.
        """
        private_files = []
        
        for file in files:
            # Check exact matches
            if file in self.PRIVATE_PATTERNS:
                private_files.append((file, "Exact match to private pattern"))
                continue
            
            # Check directory prefixes
            for pattern in self.PRIVATE_PATTERNS:
                if pattern.endswith('/') and file.startswith(pattern):
                    private_files.append((file, f"Inside private directory: {pattern}"))
                    break
            
            # Check file patterns
            if 'private' in file.lower() or '__private__' in file:
                private_files.append((file, "Contains 'private' in path"))
            
            # Check specific files that should be excluded
            for exclude in self.EXCLUDE_FROM_PUBLIC:
                if file == exclude or file.startswith(exclude):
                    private_files.append((file, f"Matches exclude pattern: {exclude}"))
                    break
        
        return private_files
    
    def validate_commit(self) -> Tuple[bool, List[str]]:
        """
        Validate if current commit is safe for the branch.
        
        Returns (is_valid, error_messages).
        """
        # Check for override mechanisms
        if self._check_override():
            return True, []
        
        if self.is_private_branch():
            # Private branches can have any content
            return True, []
        
        # Public branch - check for private content
        staged_files = self.get_staged_files()
        private_files = self.check_private_files(staged_files)
        
        if private_files:
            errors = [
                f"ERROR: Attempting to commit private files to public branch '{self.current_branch}':",
                ""
            ]
            for file, reason in private_files:
                errors.append(f"  - {file}: {reason}")
            
            errors.extend([
                "",
                "These files should only exist in private branches.",
                "To fix this:",
                "  1. Switch to private branch: git checkout private",
                "  2. Or unstage these files: git reset HEAD <file>",
                "  3. Or remove from working directory: rm <file>",
                "  4. Or override with: REPOKIT_OVERRIDE=true git commit ...",
                "  5. Or add '[override]' to commit message",
            ])
            return False, errors
        
        return True, []
    
    def _check_override(self) -> bool:
        """Check if guardrails should be overridden."""
        # Environment variable override
        if os.environ.get('REPOKIT_OVERRIDE', '').lower() in ('true', '1', 'yes'):
            print("🔓 REPOKIT_OVERRIDE detected - bypassing guardrails")
            return True
        
        # Check commit message for override flag
        try:
            result = subprocess.run(
                ['git', 'log', '--format=%B', '-n', '1'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=False
            )
            
            # Also check if we're in the middle of a commit (check COMMIT_EDITMSG)
            commit_msg_file = os.path.join(self.repo_path, '.git', 'COMMIT_EDITMSG')
            commit_message = ""
            
            if os.path.exists(commit_msg_file):
                with open(commit_msg_file, 'r') as f:
                    commit_message = f.read().strip()
            elif result.returncode == 0:
                commit_message = result.stdout.strip()
            
            if '[override]' in commit_message.lower() or '[repokit-override]' in commit_message.lower():
                print("🔓 Override flag detected in commit message - bypassing guardrails")
                return True
                
        except Exception:
            pass  # If we can't check commit message, continue with normal validation
        
        return False
    
    def get_merge_excludes(self, source_branch: str, target_branch: str) -> Set[str]:
        """Get list of files to exclude when merging between branches."""
        # If merging from private to public, exclude private files
        if source_branch in self.PRIVATE_BRANCHES and target_branch in self.PUBLIC_BRANCHES:
            return self.EXCLUDE_FROM_PUBLIC
        
        return set()
    
    def setup_branch_excludes(self) -> None:
        """Set up .git/info/exclude for current branch."""
        exclude_file = os.path.join(self.repo_path, '.git', 'info', 'exclude')
        
        if self.is_public_branch():
            # Add private patterns to exclude file
            excludes = [
                "# RepoKit: Branch-conditional excludes for public branch",
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
                "# Test artifacts",
                "test-runs/",
                "test_runs/",
            ]
            
            _write_excludes(exclude_file, excludes)

            print(f"✓ Set up branch excludes for public branch '{self.current_branch}'")
        else:
            # Private branch - minimal excludes
            excludes = [
                "# RepoKit: Minimal excludes for private branch",
                "# Private branches can contain all content",
                "",
                "# Test artifacts (not needed in git)",
                "test-runs/",
                "test_runs/",
            ]
            
            _write_excludes(exclude_file, excludes)

            print(f"✓ Set up branch excludes for private branch '{self.current_branch}'")


def check_branch_safety() -> bool:
    """Quick check if current operations are safe."""
    context = BranchContext()
    is_valid, errors = context.validate_commit()
    
    if not is_valid:
        for error in errors:
            print(error)
        return False
    
    return True


if __name__ == "__main__":
    # Quick test when run directly
    context = BranchContext()
    print(f"Current branch: {context.current_branch}")
    print(f"Branch type: {context.branch_type}")
    print(f"Is private: {context.is_private_branch()}")
    print(f"Is public: {context.is_public_branch()}")
    
    staged = context.get_staged_files()
    if staged:
        print(f"\nStaged files: {staged}")
        private = context.check_private_files(staged)
        if private:
            print("\nPrivate files detected:")
            for file, reason in private:
                print(f"  - {file}: {reason}")