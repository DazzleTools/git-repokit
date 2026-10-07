#!/usr/bin/env python3
"""
Remote integration for RepoKit.

Handles creating and configuring remote repositories on GitHub, GitLab, etc.
"""

import os
import logging
import json
import subprocess
import requests
from typing import Dict, Any, Optional, List, Union, Tuple

from .auth_integration import AuthenticationHandler
from .defaults import strategy_push_branches


class RemoteIntegration:
    """
    Manages integration with remote Git hosting services like GitHub, GitLab, etc.
    """

    def __init__(
        self, repo_manager, credentials_file: Optional[str] = None, verbose: int = 0
    ):
        """
        Initialize the remote integration manager.

        Args:
            repo_manager: Reference to the repository manager
            credentials_file: Optional path to credentials file
            verbose: Verbosity level (0=normal, 1=info, 2=debug)
        """
        self.repo_manager = repo_manager
        self.verbose = verbose
        self.logger = logging.getLogger("repokit.remote")

        # Initialize authentication handler
        self.auth_handler = AuthenticationHandler(verbose=verbose)
        if credentials_file:
            self.auth_handler.load_credentials(credentials_file)
        else:
            self.auth_handler.load_credentials()

    def create_github_repository(
        self,
        repo_name: str,
        description: str = "",
        private: bool = False,
        organization: Optional[str] = None,
        token_command: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Create a new repository on GitHub.

        Args:
            repo_name: Name of the repository
            description: Repository description
            private: Whether the repository should be private
            organization: GitHub organization name (or None for personal account)
            token_command: Command to retrieve token from password manager

        Returns:
            Tuple of (success, url or error message)
        """
        # Get token from auth handler
        token = self.auth_handler.get_token("github", token_command)
        if not token:
            return (
                False,
                "GitHub token not found. See Authentication Guide for setup instructions.",
            )

        # Get organization from auth handler if not provided
        if not organization:
            organization = self.auth_handler.get_organization("github")

        # Get API URL
        api_url = self.auth_handler.get_api_url("github")

        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }

        default_branch = self.repo_manager.config.get("default_branch", "main")
        data = {
            "name": repo_name,
            "description": description,
            "private": private,
            "auto_init": False,  # Don't initialize with README
            "default_branch": default_branch,
        }

        # API endpoint - either user repos or organization repos
        if organization:
            url = f"{api_url}/orgs/{organization}/repos"
        else:
            url = f"{api_url}/user/repos"

        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()

            repo_info = response.json()
            repo_url = repo_info["html_url"]

            self.logger.info(f"Created GitHub repository: {repo_url}")

            # Set default branch to main if not already set
            # This is necessary because GitHub doesn't let you set default branch at creation
            # if the repo is empty
            try:
                default_branch_url = f"{api_url}/repos/{organization if organization else 'user'}/{repo_name}/default_branch"
                default_branch_data = {"default_branch": "main"}
                default_branch_response = requests.patch(
                    default_branch_url, headers=headers, json=default_branch_data
                )
                if default_branch_response.status_code == 200:
                    self.logger.info("Set default branch to 'main'")
            except Exception as e:
                self.logger.warning(f"Could not set default branch: {str(e)}")

            return True, repo_url
        except requests.RequestException as e:
            error_msg = f"Failed to create GitHub repository: {str(e)}"
            if hasattr(e, "response") and e.response:
                try:
                    error_details = e.response.json()
                    error_msg += f" - {error_details.get('message', '')}"
                except ValueError:
                    pass

            self.logger.error(error_msg)
            return False, error_msg

    def create_gitlab_repository(
        self,
        repo_name: str,
        description: str = "",
        private: bool = False,
        group: Optional[str] = None,
        token_command: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Create a new repository on GitLab.

        Args:
            repo_name: Name of the repository
            description: Repository description
            private: Whether the repository should be private
            group: GitLab group path (or None for personal account)
            token_command: Command to retrieve token from password manager

        Returns:
            Tuple of (success, url or error message)
        """
        # Get token from auth handler
        token = self.auth_handler.get_token("gitlab", token_command)
        if not token:
            return (
                False,
                "GitLab token not found. See Authentication Guide for setup instructions.",
            )

        # Get group from auth handler if not provided
        if not group:
            group = self.auth_handler.get_organization("gitlab")

        # Get API URL
        api_url = self.auth_handler.get_api_url("gitlab")

        headers = {"PRIVATE-TOKEN": token, "Content-Type": "application/json"}

        # Convert private flag to GitLab's visibility level
        visibility = "private" if private else "public"

        data = {
            "name": repo_name,
            "description": description,
            "visibility": visibility,
            "initialize_with_readme": False,
        }

        # API endpoint - either user projects or group projects
        if group:
            data["namespace_id"] = group
            url = f"{api_url}/projects"
        else:
            url = f"{api_url}/projects"

        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()

            repo_info = response.json()
            repo_url = repo_info["web_url"]

            self.logger.info(f"Created GitLab repository: {repo_url}")
            return True, repo_url
        except requests.RequestException as e:
            error_msg = f"Failed to create GitLab repository: {str(e)}"
            if hasattr(e, "response") and e.response:
                try:
                    error_details = e.response.json()
                    error_msg += f" - {error_details.get('message', '')}"
                except ValueError:
                    pass

            self.logger.error(error_msg)
            return False, error_msg

    def add_remote(self, remote_url: str, remote_name: str = "origin") -> bool:
        """
        Add a remote to the local repository.

        Args:
            remote_url: URL of the remote repository
            remote_name: Name of the remote (default: origin)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if remote already exists
            existing_remote = self.repo_manager.run_git(
                ["remote", "get-url", remote_name], check=False
            )

            if existing_remote:
                # Remote exists, update URL
                self.repo_manager.run_git(
                    ["remote", "set-url", remote_name, remote_url]
                )
                self.logger.info(f"Updated remote '{remote_name}' to {remote_url}")
            else:
                # Add new remote
                self.repo_manager.run_git(["remote", "add", remote_name, remote_url])
                self.logger.info(f"Added remote '{remote_name}' at {remote_url}")

            return True
        except Exception as e:
            self.logger.error(f"Failed to add remote: {str(e)}")
            return False

    def push_to_remote(
        self, branch_name: str, remote_name: str = "origin", set_upstream: bool = True
    ) -> bool:
        """
        Push a branch to the remote repository.

        Args:
            branch_name: Name of the branch to push
            remote_name: Name of the remote (default: origin)
            set_upstream: Whether to set up branch tracking

        Returns:
            True if successful, False otherwise
        """
        try:
            # First ensure we're on the correct branch or this will fail
            current_branch = self.repo_manager.run_git(["branch", "--show-current"])
            current_branch = current_branch.strip() if current_branch else ""

            if current_branch != branch_name:
                self.logger.warning(
                    f"Not on branch {branch_name}, currently on {current_branch}"
                )
                # Instead of checking out, use push with refspec
                # Make sure there are no spaces in the branch name and that it's properly formatted
                # Remove the "+" that was mistakenly being added before the branch name
                branch_name = branch_name.strip().replace(" ", "_")
                push_cmd = [
                    "push",
                    remote_name,
                    f"refs/heads/{branch_name}:refs/heads/{branch_name}",
                ]
            else:
                # Standard push with optional upstream setting
                push_cmd = ["push"]
                if set_upstream:
                    push_cmd.append("--set-upstream")
                push_cmd.extend([remote_name, branch_name])

            self.repo_manager.run_git(push_cmd)
            self.logger.info(f"Pushed branch '{branch_name}' to {remote_name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to push branch '{branch_name}': {str(e)}")
            return False

    def push_all_branches(
        self, exclude_branches: Optional[List[str]] = None, remote_name: str = "origin"
    ) -> Tuple[List[str], List[str]]:
        """
        Push all branches to the remote repository, except those explicitly excluded.

        Args:
            exclude_branches: List of branch names to exclude (default: ["private"])
            remote_name: Name of the remote (default: origin)

        Returns:
            Tuple of (successful_branches, failed_branches)
        """
        if exclude_branches is None:
            exclude_branches = ["private"]

        # Get all branches - use a better approach to avoid plus signs
        try:
            branches_output = self.repo_manager.run_git(["branch", "--list"])
            branches = []

            for branch in branches_output.split("\n"):
                # Strip the leading "* " or "  " and any "+" from each branch name
                branch_name = branch.strip().lstrip("*+").strip()

                # Make sure the branch name is valid and not empty
                if branch_name and branch_name not in exclude_branches:
                    branches.append(branch_name)
        except Exception as e:
            self.logger.error(f"Failed to get branches: {str(e)}")
            return [], []

        # Prioritize main branch first for initial push (important for GitHub)
        if "main" in branches:
            branches.remove("main")
            branches.insert(0, "main")

        successful_branches = []
        failed_branches = []

        # Get the current branch
        current_branch = self.repo_manager.run_git(["branch", "--show-current"])

        for branch in branches:
            try:
                # For branches that are currently checked out in worktrees, we need a different approach
                if self.is_branch_checked_out(branch) and branch != current_branch:
                    # For branches checked out in worktrees, we use a different approach:
                    # 1. First check if the remote exists and branch is tracked
                    remote_check = self.repo_manager.run_git(
                        ["config", "--get", f"branch.{branch}.remote"], check=False
                    )

                    if remote_check:
                        # Branch is tracked, push it
                        self.repo_manager.run_git(["push", remote_name, branch])
                    else:
                        # Branch is not tracked, set up tracking first
                        # This is trickier - we need to use the git command with the refspec
                        self.repo_manager.run_git(
                            [
                                "push",
                                "-u",
                                remote_name,
                                f"refs/heads/{branch}:refs/heads/{branch}",
                            ],
                            check=True,
                        )
                else:
                    # Normal push for branches that aren't checked out in worktrees
                    # or if we're on this branch
                    if current_branch == branch:
                        # We're on this branch, regular push
                        self.repo_manager.run_git(["push", "-u", remote_name, branch])
                    else:
                        # We need to checkout the branch first
                        self.repo_manager.run_git(["checkout", branch])
                        self.repo_manager.run_git(["push", "-u", remote_name, branch])
                        # Go back to the original branch
                        self.repo_manager.run_git(["checkout", current_branch])

                self.logger.info(f"Pushed branch '{branch}' to {remote_name}")
                successful_branches.append(branch)
            except Exception as e:
                self.logger.error(f"Failed to push branch '{branch}': {str(e)}")
                failed_branches.append(branch)

        if successful_branches:
            self.logger.info(
                f"Successfully pushed branches: {', '.join(successful_branches)}"
            )

        if failed_branches:
            self.logger.warning(
                f"Failed to push branches: {', '.join(failed_branches)}"
            )

        return successful_branches, failed_branches

    def push_allowed_branches(
        self, allowed_branches: List[str], exclude_branches: Optional[List[str]] = None, remote_name: str = "origin"
    ) -> Tuple[List[str], List[str]]:
        """
        Push only the allowed branches to the remote repository.

        Args:
            allowed_branches: List of branch names that are allowed to be pushed
            exclude_branches: List of branch names to exclude (additional safety check)
            remote_name: Name of the remote (default: origin)

        Returns:
            Tuple of (successful_branches, failed_branches)
        """
        if exclude_branches is None:
            exclude_branches = ["private"]

        # Get all existing local branches
        try:
            branches_output = self.repo_manager.run_git(["branch", "--list"])
            existing_branches = []

            for branch in branches_output.split("\n"):
                # Strip the leading "* " or "  " and any "+" from each branch name
                branch_name = branch.strip().lstrip("*+").strip()
                if branch_name:
                    existing_branches.append(branch_name)
        except Exception as e:
            self.logger.error(f"Failed to get branches: {str(e)}")
            return [], []

        # Only push branches that exist locally AND are in the allowed list AND not excluded
        branches_to_push = []
        for branch in allowed_branches:
            if branch in existing_branches and branch not in exclude_branches:
                branches_to_push.append(branch)
            elif branch not in existing_branches:
                self.logger.info(f"Branch '{branch}' not found locally, skipping")

        self.logger.info(f"Pushing allowed branches: {branches_to_push}")
        
        # Prioritize main branch first for initial push (important for GitHub)
        if "main" in branches_to_push:
            branches_to_push.remove("main")
            branches_to_push.insert(0, "main")

        successful_branches = []
        failed_branches = []

        # Get the current branch
        current_branch = self.repo_manager.run_git(["branch", "--show-current"])

        for branch in branches_to_push:
            try:
                # For branches that are currently checked out in worktrees, we need a different approach
                if self.is_branch_checked_out(branch) and branch != current_branch:
                    # Use refspec to push without checkout
                    self.repo_manager.run_git(
                        [
                            "push",
                            "-u",
                            remote_name,
                            f"refs/heads/{branch}:refs/heads/{branch}",
                        ],
                        check=True,
                    )
                else:
                    # Normal push for branches that aren't checked out in worktrees
                    if current_branch == branch:
                        # We're on this branch, regular push
                        self.repo_manager.run_git(["push", "-u", remote_name, branch])
                    else:
                        # We need to checkout the branch first
                        self.repo_manager.run_git(["checkout", branch])
                        self.repo_manager.run_git(["push", "-u", remote_name, branch])
                        # Go back to the original branch
                        self.repo_manager.run_git(["checkout", current_branch])

                self.logger.info(f"Pushed branch '{branch}' to {remote_name}")
                successful_branches.append(branch)
            except Exception as e:
                self.logger.error(f"Failed to push branch '{branch}': {str(e)}")
                failed_branches.append(branch)

        if successful_branches:
            self.logger.info(
                f"Successfully pushed branches: {', '.join(successful_branches)}"
            )

        if failed_branches:
            self.logger.warning(
                f"Failed to push branches: {', '.join(failed_branches)}"
            )

        return successful_branches, failed_branches

    def is_branch_checked_out(self, branch: str) -> bool:
        """
        Check if a branch is currently checked out in a worktree.

        Args:
            branch: Branch name to check

        Returns:
            True if the branch is checked out, False otherwise
        """
        try:
            # Get all worktrees
            worktree_output = self.repo_manager.run_git(
                ["worktree", "list"], check=False
            )

            # Check if the branch appears as checked out in any worktree
            for line in worktree_output.split("\n"):
                if branch in line and "[" in line and "]" in line:
                    # Format is typically: "/path/to/worktree  abcd1234 [branch]"
                    return True

            return False
        except Exception:
            # If we can't determine, assume it's not checked out to be safe
            return False

    def setup_remote_repository(
        self,
        service: str = "github",
        remote_name: str = "origin",
        private: bool = False,
        push_branches: bool = True,
        organization: Optional[str] = None,
        token_command: Optional[str] = None,
        include_branches: Optional[List[str]] = None,
        exclude_branches: Optional[List[str]] = None,
    ) -> bool:
        """
        Create a remote repository and push local branches.

        Args:
            service: Remote service ("github" or "gitlab")
            remote_name: Name to use for the remote (default: origin)
            private: Whether the repository should be private
            push_branches: Whether to push branches after setup
            organization: Organization or group name (optional)
            token_command: Command to retrieve token (optional)
            include_branches: Specific branches to push (overrides strategy defaults)
            exclude_branches: Additional branches to exclude (beyond private)

        Returns:
            True if successful, False otherwise
        """
        repo_name = self.repo_manager.project_name
        description = self.repo_manager.config.get("description", "")

        # Create the remote repository
        if service.lower() == "github":
            success, result = self.create_github_repository(
                repo_name, description, private, organization, token_command
            )
        elif service.lower() == "gitlab":
            success, result = self.create_gitlab_repository(
                repo_name, description, private, organization, token_command
            )
        else:
            success = False
            result = f"Unsupported service: {service}"

        if not success:
            self.logger.error(f"Failed to create remote repository: {result}")
            return False

        # Add the remote
        remote_url = result
        if not self.add_remote(remote_url, remote_name):
            return False

        # Push branches if requested
        if push_branches:
            # Determine which branches to push
            branch_strategy = self.repo_manager.config.get("branch_strategy", "simple")
            strategy_push = strategy_push_branches(branch_strategy)

            if include_branches:
                # User explicitly specified branches to include
                allowed_branches = include_branches
                self.logger.info(f"Using user-specified branches to push: {allowed_branches}")
            else:
                allowed_branches = strategy_push or ["main", "dev"]
                self.logger.info(f"Using {branch_strategy} strategy branches: {allowed_branches}")

            # Build exclude list: the private branch + user-specified exclusions.
            # A strategy whose "private" branch is one of its public branches
            # (minimal: main) still pushes that branch.
            private_branch = self.repo_manager.config.get("private_branch", "private")
            exclude_list = []
            if private_branch and private_branch not in strategy_push:
                exclude_list.append(private_branch)
            if exclude_branches:
                exclude_list.extend(exclude_branches)
                self.logger.info(f"Additional excluded branches: {exclude_branches}")
            
            successful, failed = self.push_allowed_branches(allowed_branches, exclude_list, remote_name)

            if failed:
                self.logger.warning(
                    f"Some branches could not be pushed: {', '.join(failed)}"
                )
                return False

        self.logger.info(f"Successfully set up remote repository at {remote_url}")
        return True

    def store_credentials(
        self,
        service: str,
        token: str,
        organization: Optional[str] = None,
        credentials_file: Optional[str] = None,
    ) -> bool:
        """
        Store credentials for a service.

        Args:
            service: Service name ('github' or 'gitlab')
            token: Authentication token
            organization: Organization or group name (optional)
            credentials_file: Path to credentials file (optional)

        Returns:
            True if stored successfully, False otherwise
        """
        return self.auth_handler.store_credentials(
            service, token, organization, credentials_file
        )
