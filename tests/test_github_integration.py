"""
Test GitHub integration functionality.

These tests specifically test GitHub API interactions.
"""

import unittest
import os
import time
import json
from pathlib import Path

import pytest

from .test_utils import (
    RepoKitTestCase,
    requires_github_token,
    TestConfig,
    MockGitHubAPI
)


@pytest.mark.live
class TestGitHubIntegration(RepoKitTestCase):
    """Test real GitHub API integration."""
    
    @requires_github_token
    def test_github_authentication(self):
        """Test GitHub authentication works."""
        # Store credentials
        stdout, stderr = self.assert_repokit_success([
            "store-credentials",
            "--publish-to", "github",
            "--token", TestConfig.GITHUB_TOKEN
        ])
        
        self.assertIn("stored successfully", stdout.lower())
        
        # Verify credentials file
        creds_file = os.path.expanduser("~/.repokit/credentials.json")
        self.assertTrue(os.path.exists(creds_file))
        
    @requires_github_token
    def test_create_and_deploy_simple(self):
        """Test simple project creation and GitHub deployment."""
        repo_name = self.generate_test_repo_name()
        self.github_cleanup.register_repo(repo_name)
        
        # Create project with deployment
        stdout, stderr = self.assert_repokit_success([
            "create", repo_name,
            "--language", "python",
            "--publish-to", "github",
            "--private-repo"
        ])
        
        # Verify success messages
        self.assertIn("GitHub repository created", stdout)
        self.assertIn(repo_name, stdout)
        
        # Check local project structure
        project_dir = os.path.join(self.test_dir, repo_name)
        self.assert_directory_structure(project_dir, ["docs", "tests", "scripts"])
        
    @requires_github_token
    def test_organization_deployment(self):
        """Test deployment to GitHub organization (if configured)."""
        if not os.environ.get('REPOKIT_TEST_GITHUB_ORG'):
            self.skipTest("No test organization configured")
            
        org_name = os.environ.get('REPOKIT_TEST_GITHUB_ORG')
        repo_name = self.generate_test_repo_name()
        self.github_cleanup.register_repo(repo_name, owner=org_name)
        
        # Deploy to organization
        project_dir = self.create_test_project(repo_name)
        
        stdout, stderr = self.assert_repokit_success([
            "adopt", ".",
            "--publish-to", "github",
            "--organization", org_name,
            "--name", repo_name
        ], cwd=project_dir)
        
        self.assertIn("GitHub repository created", stdout)
        self.assertIn(org_name, stdout)
        
    @requires_github_token
    def test_public_repository_deployment(self):
        """Test public repository deployment."""
        repo_name = self.generate_test_repo_name()
        self.github_cleanup.register_repo(repo_name)
        
        project_dir = self.create_test_project(repo_name)
        
        # Deploy as public repo (no --private-repo flag)
        stdout, stderr = self.assert_repokit_success([
            "adopt", ".",
            "--publish-to", "github",
            "--name", repo_name
        ], cwd=project_dir)
        
        self.assertIn("GitHub repository created", stdout)
        
    @requires_github_token
    def test_deployment_with_description(self):
        """Test deployment with custom description."""
        repo_name = self.generate_test_repo_name()
        self.github_cleanup.register_repo(repo_name)
        
        description = "Test repository for RepoKit integration testing"
        project_dir = self.create_test_project(repo_name)
        
        stdout, stderr = self.assert_repokit_success([
            "adopt", ".",
            "--publish-to", "github",
            "--name", repo_name,
            "--description", description,
            "--private-repo"
        ], cwd=project_dir)
        
        self.assertIn("GitHub repository created", stdout)
        
    @requires_github_token
    def test_multi_branch_deployment(self):
        """Test deployment of repository with multiple branches."""
        repo_name = self.generate_test_repo_name()
        self.github_cleanup.register_repo(repo_name)
        
        # Create project with custom branches
        project_dir = self.create_test_project(repo_name, with_git=False)
        
        stdout, stderr = self.assert_repokit_success([
            "adopt", ".",
            "--publish-to", "github",
            "--name", repo_name,
            "--branches", "main,develop,staging",
            "--private-repo"
        ], cwd=project_dir)
        
        self.assertIn("GitHub repository created", stdout)
        
        # Verify branches locally
        self.assert_git_branch_exists(project_dir, "main")
        self.assert_git_branch_exists(project_dir, "develop")
        self.assert_git_branch_exists(project_dir, "staging")
        
    @requires_github_token
    def test_deployment_error_handling(self):
        """Test error handling during deployment."""
        # Test with invalid token
        bad_token = "ghp_invalid_token_12345"
        
        project_dir = self.create_test_project("error-test")
        
        # Store bad token
        self.assert_repokit_success([
            "store-credentials",
            "--publish-to", "github",
            "--token", bad_token
        ])
        
        # Try to deploy - should fail gracefully
        exit_code, stdout, stderr = self.run_repokit([
            "adopt", ".",
            "--publish-to", "github",
            "--name", "test-error-repo"
        ], cwd=project_dir)
        
        self.assertNotEqual(exit_code, 0)
        self.assertIn("error", stderr.lower())
        
        # Restore good token
        self.assert_repokit_success([
            "store-credentials",
            "--publish-to", "github",
            "--token", TestConfig.GITHUB_TOKEN
        ])
        
    @requires_github_token
    def test_duplicate_repository_handling(self):
        """Test handling when repository already exists."""
        repo_name = self.generate_test_repo_name()
        self.github_cleanup.register_repo(repo_name)
        
        # First deployment
        project1 = self.create_test_project("project1")
        stdout1, _ = self.assert_repokit_success([
            "adopt", ".",
            "--publish-to", "github",
            "--name", repo_name
        ], cwd=project1)
        
        self.assertIn("GitHub repository created", stdout1)
        
        # Second deployment with same name - should fail
        project2 = self.create_test_project("project2")
        exit_code, stdout2, stderr2 = self.run_repokit([
            "adopt", ".",
            "--publish-to", "github",
            "--name", repo_name
        ], cwd=project2)
        
        self.assertNotEqual(exit_code, 0)
        self.assertIn("already exists", stderr2.lower())


class TestGitHubAPIMocking(unittest.TestCase):
    """Test GitHub functionality with mocked API."""
    
    def test_mock_repository_creation(self):
        """Test repository creation with mock API."""
        mock_api = MockGitHubAPI()
        
        # Test basic creation
        result = mock_api.create_repository(
            name="test-repo",
            private=True,
            organization="test-org"
        )
        
        self.assertEqual(result['name'], "test-repo")
        self.assertTrue(result['private'])
        self.assertEqual(result['organization'], "test-org")
        self.assertIn("test-repo", result['html_url'])
        
        # Verify tracking
        self.assertEqual(len(mock_api.created_repos), 1)
        self.assertEqual(len(mock_api.api_calls), 1)
        
    def test_mock_repository_deletion(self):
        """Test repository deletion with mock API."""
        mock_api = MockGitHubAPI()
        
        # Create then delete
        mock_api.create_repository("test-repo")
        self.assertEqual(len(mock_api.created_repos), 1)
        
        result = mock_api.delete_repository("test-repo")
        self.assertTrue(result)
        self.assertEqual(len(mock_api.created_repos), 0)
        
    def test_mock_api_call_tracking(self):
        """Test API call tracking functionality."""
        mock_api = MockGitHubAPI()
        
        # Make various calls
        mock_api.create_repository("repo1", private=True)
        mock_api.create_repository("repo2", organization="org1")
        mock_api.delete_repository("repo1")
        
        # Verify call history
        self.assertEqual(len(mock_api.api_calls), 3)
        
        # Check first call
        first_call = mock_api.api_calls[0]
        self.assertEqual(first_call['method'], 'create_repository')
        self.assertEqual(first_call['args']['name'], 'repo1')
        self.assertTrue(first_call['args']['private'])
        
        # Check delete call
        delete_call = mock_api.api_calls[2]
        self.assertEqual(delete_call['method'], 'delete_repository')
        self.assertEqual(delete_call['args']['name'], 'repo1')


class TestCredentialManagement(RepoKitTestCase):
    """Test credential storage and management."""
    
    def test_store_github_credentials(self):
        """Test storing GitHub credentials."""
        test_token = "ghp_test_token_123"
        
        stdout, _ = self.assert_repokit_success([
            "store-credentials",
            "--publish-to", "github",
            "--token", test_token
        ])
        
        self.assertIn("stored successfully", stdout.lower())
        
        # Verify file created
        creds_file = os.path.expanduser("~/.repokit/credentials.json")
        self.assertTrue(os.path.exists(creds_file))
        
        # Verify content
        with open(creds_file, "r") as f:
            creds = json.load(f)
            self.assertEqual(creds['github']['token'], test_token)
            
    def test_store_gitlab_credentials(self):
        """Test storing GitLab credentials."""
        test_token = "glpat-test_token_456"
        
        stdout, _ = self.assert_repokit_success([
            "store-credentials",
            "--publish-to", "gitlab",
            "--token", test_token
        ])
        
        self.assertIn("stored successfully", stdout.lower())
        
        # Verify content
        creds_file = os.path.expanduser("~/.repokit/credentials.json")
        with open(creds_file, "r") as f:
            creds = json.load(f)
            self.assertEqual(creds['gitlab']['token'], test_token)
            
    def test_update_credentials(self):
        """Test updating existing credentials."""
        # Store initial
        self.assert_repokit_success([
            "store-credentials",
            "--publish-to", "github",
            "--token", "old_token"
        ])
        
        # Update
        self.assert_repokit_success([
            "store-credentials",
            "--publish-to", "github",
            "--token", "new_token"
        ])
        
        # Verify updated
        creds_file = os.path.expanduser("~/.repokit/credentials.json")
        with open(creds_file, "r") as f:
            creds = json.load(f)
            self.assertEqual(creds['github']['token'], "new_token")
            
    def test_organization_credentials(self):
        """Test storing organization-specific credentials."""
        stdout, _ = self.assert_repokit_success([
            "store-credentials",
            "--publish-to", "github",
            "--token", "org_token",
            "--organization", "my-org"
        ])
        
        # Verify organization stored
        creds_file = os.path.expanduser("~/.repokit/credentials.json")
        with open(creds_file, "r") as f:
            creds = json.load(f)
            self.assertEqual(creds['github']['organization'], "my-org")


if __name__ == "__main__":
    unittest.main()