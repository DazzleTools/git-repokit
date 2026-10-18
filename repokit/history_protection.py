#!/usr/bin/env python3
"""
History Protection for RepoKit.

Provides tools to protect sensitive commit history when merging development
branches, preventing detailed implementation history from leaking to public
branches.
"""

import os
import re
import logging
import subprocess
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum


class MergeAction(Enum):
    """Actions for handling branch merges."""
    SQUASH = "squash"
    PRESERVE = "preserve"
    INTERACTIVE = "interactive"
    SMART_SQUASH = "smart_squash"


@dataclass
class BranchRule:
    """Rule for handling a branch pattern."""
    pattern: str
    action: MergeAction
    auto: bool = False
    preserve_last: int = 0
    message_template: Optional[str] = None


@dataclass
class CommitInfo:
    """Information about a commit."""
    hash: str
    author: str
    date: str
    message: str
    files_changed: List[str]


class HistoryProtectionManager:
    """
    Manages history protection when merging development branches.
    
    This class provides functionality to:
    - Categorize branches based on patterns
    - Squash or preserve commits based on rules
    - Sanitize commit messages
    - Generate meaningful merge commit messages
    """
    
    # Default sensitive patterns to remove from commit messages
    DEFAULT_SENSITIVE_PATTERNS = [
        r'private/',
        r'secret',
        r'password',
        r'token',
        r'TODO:\s*hack',
        r'FIXME:\s*security',
        r'XXX:',
        r'HACK:',
        r'TEMP:',
        r'DO NOT COMMIT',
        r'@nocommit',
    ]
    
    # Default branch rules
    DEFAULT_BRANCH_RULES = {
        'prototype/*': BranchRule('prototype/*', MergeAction.SQUASH, auto=True),
        'experiment/*': BranchRule('experiment/*', MergeAction.SQUASH, auto=True),
        'spike/*': BranchRule('spike/*', MergeAction.SQUASH, auto=True),
        'feature/*': BranchRule('feature/*', MergeAction.INTERACTIVE, auto=False),
        'bugfix/*': BranchRule('bugfix/*', MergeAction.PRESERVE, auto=True),
        'hotfix/*': BranchRule('hotfix/*', MergeAction.PRESERVE, auto=True),
    }
    
    def __init__(self, repo_path: str = ".", config: Optional[Dict[str, Any]] = None, verbose: int = 0):
        """
        Initialize the history protection manager.
        
        Args:
            repo_path: Path to the git repository
            config: Configuration dictionary
            verbose: Verbosity level
        """
        self.repo_path = os.path.abspath(repo_path)
        self.verbose = verbose
        self.logger = logging.getLogger("repokit.history_protection")
        
        # Load configuration
        self.config = config or {}
        self.history_config = self.config.get('history_protection', {})
        
        # Set up branch rules
        self.branch_rules = self._load_branch_rules()
        
        # Set up sensitive patterns
        self.sensitive_patterns = self._load_sensitive_patterns()
    
    def _load_branch_rules(self) -> Dict[str, BranchRule]:
        """Load branch rules from configuration."""
        rules = {}
        
        # Start with defaults
        for pattern, rule in self.DEFAULT_BRANCH_RULES.items():
            rules[pattern] = rule
        
        # Override with config
        config_rules = self.history_config.get('branch_rules', {})
        for pattern, rule_config in config_rules.items():
            action = MergeAction(rule_config.get('action', 'interactive'))
            auto = rule_config.get('auto', False)
            preserve_last = rule_config.get('preserve_last', 0)
            message_template = rule_config.get('message_template')
            
            rules[pattern] = BranchRule(
                pattern=pattern,
                action=action,
                auto=auto,
                preserve_last=preserve_last,
                message_template=message_template
            )
        
        return rules
    
    def _load_sensitive_patterns(self) -> List[re.Pattern]:
        """Load and compile sensitive patterns."""
        patterns = []
        
        # Start with defaults
        pattern_strings = self.DEFAULT_SENSITIVE_PATTERNS.copy()
        
        # Add config patterns
        config_patterns = self.history_config.get('sensitive_patterns', [])
        pattern_strings.extend(config_patterns)
        
        # Compile patterns
        for pattern in pattern_strings:
            try:
                patterns.append(re.compile(pattern, re.IGNORECASE))
            except re.error as e:
                self.logger.warning(f"Invalid regex pattern '{pattern}': {e}")
        
        return patterns
    
    def get_branch_rule(self, branch_name: str) -> BranchRule:
        """
        Get the rule for a given branch name.
        
        Args:
            branch_name: Name of the branch
            
        Returns:
            BranchRule for the branch
        """
        # Check each pattern
        for pattern, rule in self.branch_rules.items():
            # Convert glob pattern to regex
            regex_pattern = re.escape(pattern).replace('\\*', '.*')
            if re.match(f'^{regex_pattern}$', branch_name):
                return rule
        
        # Default rule
        return BranchRule(
            pattern='*',
            action=MergeAction.INTERACTIVE,
            auto=False
        )
    
    def run_git(self, args: List[str], check: bool = True) -> Optional[str]:
        """Run a git command and return output."""
        cmd = ['git'] + args
        
        if self.verbose >= 2:
            self.logger.debug(f"Running: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                check=check,
                capture_output=True,
                text=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            if check:
                raise
            return None
    
    def get_branch_commits(self, branch: str, base_branch: str = "HEAD") -> List[CommitInfo]:
        """
        Get all commits in a branch that aren't in the base branch.
        
        Args:
            branch: Branch to get commits from
            base_branch: Base branch to compare against
            
        Returns:
            List of CommitInfo objects
        """
        # Get commit hashes
        commit_range = f"{base_branch}..{branch}"
        hashes = self.run_git(['rev-list', '--reverse', commit_range])
        
        if not hashes:
            return []
        
        commits = []
        for hash in hashes.split('\n'):
            if not hash:
                continue
                
            # Get commit info
            info = self.run_git([
                'show',
                '--no-patch',
                '--format=%an|%ad|%s',
                '--date=short',
                hash
            ])
            
            if info:
                author, date, message = info.split('|', 2)
                
                # Get files changed
                files = self.run_git([
                    'diff-tree',
                    '--no-commit-id',
                    '--name-only',
                    '-r',
                    hash
                ])
                
                files_list = files.split('\n') if files else []
                
                commits.append(CommitInfo(
                    hash=hash,
                    author=author,
                    date=date,
                    message=message,
                    files_changed=files_list
                ))
        
        return commits
    
    def sanitize_message(self, message: str) -> str:
        """
        Remove sensitive patterns from a commit message.
        
        Args:
            message: Original message
            
        Returns:
            Sanitized message
        """
        sanitized = message
        
        for pattern in self.sensitive_patterns:
            sanitized = pattern.sub('[REDACTED]', sanitized)
        
        return sanitized
    
    def generate_squash_message(self, commits: List[CommitInfo], branch_name: str) -> str:
        """
        Generate a meaningful squash commit message from multiple commits.
        
        Args:
            commits: List of commits to squash
            branch_name: Name of the branch being merged
            
        Returns:
            Generated commit message
        """
        if not commits:
            return f"Merge {branch_name}"
        
        # Extract key information
        authors = list(set(c.author for c in commits))
        file_changes = {}
        key_messages = []
        
        for commit in commits:
            # Track file changes
            for file in commit.files_changed:
                if file not in file_changes:
                    file_changes[file] = 0
                file_changes[file] += 1
            
            # Extract key messages (skip merge commits and trivial ones)
            msg = commit.message.lower()
            if not any(skip in msg for skip in ['merge', 'wip', 'temp', 'fix typo']):
                sanitized = self.sanitize_message(commit.message)
                if sanitized and sanitized != '[REDACTED]':
                    key_messages.append(sanitized)
        
        # Build the message
        lines = []
        
        # Summary line
        feature_name = branch_name.split('/')[-1].replace('-', ' ').replace('_', ' ')
        lines.append(f"feat: {feature_name}")
        lines.append("")
        
        # Key changes
        if key_messages:
            lines.append("Key changes:")
            # Deduplicate and take top 5
            seen = set()
            for msg in key_messages[:5]:
                if msg not in seen:
                    lines.append(f"- {msg}")
                    seen.add(msg)
            lines.append("")
        
        # Statistics
        lines.append(f"Squashed {len(commits)} commits from {branch_name}")
        lines.append(f"Authors: {', '.join(authors[:3])}" + (" and others" if len(authors) > 3 else ""))
        lines.append(f"Files changed: {len(file_changes)}")
        
        return '\n'.join(lines)
    
    def preview_squash(self, branch: str, base_branch: str = "HEAD") -> Tuple[List[CommitInfo], str]:
        """
        Preview what would happen if we squashed a branch.
        
        Args:
            branch: Branch to squash
            base_branch: Base branch to merge into
            
        Returns:
            Tuple of (commits that would be squashed, generated message)
        """
        commits = self.get_branch_commits(branch, base_branch)
        message = self.generate_squash_message(commits, branch)
        
        return commits, message
    
    def safe_merge_dev(
        self,
        branch: str,
        target_branch: Optional[str] = None,
        squash: Optional[bool] = None,
        message: Optional[str] = None,
        preserve_last: Optional[int] = None,
        dry_run: bool = False
    ) -> bool:
        """
        Safely merge a development branch with history protection.
        
        Args:
            branch: Branch to merge
            target_branch: Target branch (default: current branch)
            squash: Whether to squash (None = use rules)
            message: Custom merge message
            preserve_last: Number of recent commits to preserve
            dry_run: Preview without merging
            
        Returns:
            True if successful
        """
        # Get branch rule
        rule = self.get_branch_rule(branch)
        
        # Determine action
        if squash is not None:
            action = MergeAction.SQUASH if squash else MergeAction.PRESERVE
        else:
            action = rule.action
        
        # Get commits
        commits = self.get_branch_commits(branch, target_branch or "HEAD")
        
        if not commits:
            self.logger.info(f"No commits to merge from {branch}")
            return True
        
        # Handle based on action
        if action == MergeAction.PRESERVE:
            self.logger.info(f"Preserving all {len(commits)} commits from {branch}")
            if not dry_run:
                self.run_git(['merge', branch, '--no-ff'])
            
        elif action == MergeAction.SQUASH:
            # Generate message if not provided
            if not message:
                message = self.generate_squash_message(commits, branch)
            
            self.logger.info(f"Squashing {len(commits)} commits from {branch}")
            if self.verbose >= 1:
                print(f"\nGenerated commit message:\n{message}\n")
            
            if not dry_run:
                # Perform squash merge
                self.run_git(['merge', branch, '--squash'])
                self.run_git(['commit', '-m', message])
        
        elif action == MergeAction.INTERACTIVE:
            # Show preview and ask user
            preview_message = self.generate_squash_message(commits, branch)
            
            print(f"\nBranch: {branch}")
            print(f"Commits: {len(commits)}")
            print(f"Rule: {rule.pattern} ({action.value})")
            print(f"\nCommits to be merged:")
            for commit in commits[-10:]:  # Show last 10
                print(f"  {commit.hash[:8]} {commit.message}")
            if len(commits) > 10:
                print(f"  ... and {len(commits) - 10} more")
            
            print(f"\nSuggested squash message:")
            print(preview_message)
            
            if not dry_run:
                response = input("\nSquash these commits? [Y/n/e(dit)]: ").lower()
                if response == 'n':
                    print("Performing regular merge...")
                    self.run_git(['merge', branch, '--no-ff'])
                elif response == 'e':
                    # TODO: Implement message editing
                    print("Message editing not yet implemented")
                    return False
                else:
                    print("Performing squash merge...")
                    self.run_git(['merge', branch, '--squash'])
                    self.run_git(['commit', '-m', message or preview_message])
        
        return True