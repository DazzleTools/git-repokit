"""
Test utilities and helpers for RepoKit test suite.
"""

import os
import stat
import sys
import shutil
import tempfile
import unittest
import subprocess
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from functools import wraps
from dotenv import load_dotenv

# Load test environment variables -- only when live GitHub tests were asked
# for. .env.test holds a real token, and tests that see a token create real
# repositories (see tests/conftest.py).
test_env_path = Path(__file__).parent.parent / '.env.test'
if os.environ.get('REPOKIT_LIVE_GITHUB') == '1' and test_env_path.exists():
    load_dotenv(test_env_path)


def force_rmtree(path):
    """Remove a directory tree, including git's read-only object files on Windows."""
    def _make_writable_and_retry(func, target, _exc):
        os.chmod(target, stat.S_IWRITE)
        func(target)

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_make_writable_and_retry)
    else:
        shutil.rmtree(path, onerror=_make_writable_and_retry)


class TestConfig:
    """Test configuration and constants."""
    
    # Token from environment
    GITHUB_TOKEN = os.environ.get('REPOKIT_TEST_GITHUB_TOKEN')
    GITHUB_USER = os.environ.get('REPOKIT_TEST_GITHUB_USER', 'test-user')
    
    # Test prefixes and cleanup
    TEST_PREFIX = os.environ.get('REPOKIT_TEST_PREFIX', 'repokit-test-')
    CLEANUP_ENABLED = os.environ.get('REPOKIT_TEST_CLEANUP', 'true').lower() == 'true'
    
    # Test timeouts
    API_TIMEOUT = 30
    CLEANUP_DELAY = 2  # Seconds to wait before cleanup
    

class GitHubTestCleanup:
    """Manages cleanup of test repositories on GitHub."""
    
    def __init__(self, token: str = None):
        self.token = token or TestConfig.GITHUB_TOKEN
        self.created_repos = []
        
    def register_repo(self, repo_name: str, owner: str = None):
        """Register a repository for cleanup."""
        self.created_repos.append({
            'name': repo_name,
            'owner': owner or TestConfig.GITHUB_USER
        })
        
    def cleanup_all(self):
        """Delete all registered test repositories."""
        if not TestConfig.CLEANUP_ENABLED:
            return
            
        if not self.token:
            print("Warning: No GitHub token available for cleanup")
            return
            
        for repo in self.created_repos:
            self._delete_repo(repo['name'], repo['owner'])
            
    def _delete_repo(self, repo_name: str, owner: str):
        """Delete a single repository from GitHub."""
        try:
            import requests
            
            url = f"https://api.github.com/repos/{owner}/{repo_name}"
            headers = {
                "Authorization": f"token {self.token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            response = requests.delete(url, headers=headers)
            
            if response.status_code == 204:
                print(f"Cleaned up test repository: {repo_name}")
            elif response.status_code == 404:
                print(f"Repository not found (already deleted?): {repo_name}")
            else:
                print(f"Failed to delete repository {repo_name}: {response.status_code}")
                
        except Exception as e:
            print(f"Error cleaning up repository {repo_name}: {str(e)}")


def requires_github_token(func):
    """Decorator to skip tests that require GitHub token."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not TestConfig.GITHUB_TOKEN:
            raise unittest.SkipTest("GitHub token not available")
        return func(*args, **kwargs)
    return wrapper


class RepoKitTestCase(unittest.TestCase):
    """Base test case for RepoKit tests."""
    
    def setUp(self):
        """Set up test environment."""
        # Use organized test run directory if available
        test_run_dir = os.environ.get('REPOKIT_TEST_RUN_DIR')
        if test_run_dir and os.path.exists(test_run_dir):
            # Create test-specific subdirectory within organized test run
            test_name = self._testMethodName
            self.test_dir = os.path.join(test_run_dir, f"{self.__class__.__name__}_{test_name}")
            os.makedirs(self.test_dir, exist_ok=True)
        else:
            # Fall back to temporary directory
            self.test_dir = tempfile.mkdtemp(prefix="repokit_test_")
            
        self.original_dir = os.getcwd()
        os.chdir(self.test_dir)
        
        # Initialize cleanup handler
        self.github_cleanup = GitHubTestCleanup()
        
    def tearDown(self):
        """Clean up test environment."""
        # Return to original directory
        os.chdir(self.original_dir)
        
        # Clean up temporary directory only if it's not an organized test run
        test_run_dir = os.environ.get('REPOKIT_TEST_RUN_DIR')
        if not test_run_dir or not self.test_dir.startswith(test_run_dir):
            # This is a temporary directory, safe to clean up
            if os.path.exists(self.test_dir):
                shutil.rmtree(self.test_dir, ignore_errors=True)
        # If it's an organized test run directory, leave it for the test run manager
            
        # Clean up GitHub repositories if any
        if hasattr(self, 'github_cleanup'):
            time.sleep(TestConfig.CLEANUP_DELAY)  # Brief delay before cleanup
            self.github_cleanup.cleanup_all()
            
    def create_test_project(self, name: str = "test-project", 
                          with_git: bool = False,
                          with_files: bool = True) -> str:
        """Create a test project directory with optional content."""
        project_dir = os.path.join(self.test_dir, name)
        os.makedirs(project_dir, exist_ok=True)
        
        if with_files:
            # Add Python file
            with open(os.path.join(project_dir, "main.py"), "w") as f:
                f.write('print("Hello from test project")\n')
                
            # Add README
            with open(os.path.join(project_dir, "README.md"), "w") as f:
                f.write(f"# {name}\n\nTest project for RepoKit\n")
                
            # Add requirements.txt
            with open(os.path.join(project_dir, "requirements.txt"), "w") as f:
                f.write("# No dependencies\n")
                
        if with_git:
            # Initialize Git repository
            subprocess.run(["git", "init"], cwd=project_dir, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"], 
                         cwd=project_dir, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], 
                         cwd=project_dir, capture_output=True)
            
            if with_files:
                subprocess.run(["git", "add", "."], cwd=project_dir, capture_output=True)
                subprocess.run(["git", "commit", "-m", "Initial commit"], 
                             cwd=project_dir, capture_output=True)
                
        return project_dir
        
    def run_repokit(self, args: List[str], cwd: str = None) -> Tuple[int, str, str]:
        """Run RepoKit command and return (exit_code, stdout, stderr)."""
        cmd = [sys.executable, "-m", "repokit"] + args
        
        # Add token to environment if available
        env = os.environ.copy()
        if TestConfig.GITHUB_TOKEN:
            env['GITHUB_TOKEN'] = TestConfig.GITHUB_TOKEN
            
        result = subprocess.run(
            cmd,
            cwd=cwd or self.test_dir,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            env=env
        )
        
        return result.returncode, result.stdout, result.stderr
        
    def assert_repokit_success(self, args: List[str], cwd: str = None):
        """Assert that a RepoKit command succeeds."""
        exit_code, stdout, stderr = self.run_repokit(args, cwd)
        
        if exit_code != 0:
            self.fail(f"RepoKit command failed: {' '.join(args)}\n"
                     f"Exit code: {exit_code}\n"
                     f"Stdout: {stdout}\n"
                     f"Stderr: {stderr}")
                     
        return stdout, stderr
        
    def assert_directory_structure(self, path: str, expected_dirs: List[str]):
        """Assert that a directory contains expected subdirectories."""
        for dir_name in expected_dirs:
            dir_path = os.path.join(path, dir_name)
            self.assertTrue(os.path.exists(dir_path), 
                          f"Expected directory not found: {dir_name}")
                          
    def assert_file_exists(self, path: str, filename: str):
        """Assert that a file exists in the given path."""
        file_path = os.path.join(path, filename)
        self.assertTrue(os.path.exists(file_path), 
                       f"Expected file not found: {filename}")
                       
    def assert_git_branch_exists(self, repo_path: str, branch_name: str):
        """Assert that a Git branch exists in the repository."""
        result = subprocess.run(
            ["git", "branch", "--list", branch_name],
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        
        self.assertIn(branch_name, result.stdout, 
                     f"Branch not found: {branch_name}")
                     
    def generate_test_repo_name(self) -> str:
        """Generate a unique test repository name."""
        timestamp = int(time.time())
        return f"{TestConfig.TEST_PREFIX}{timestamp}"


class MockGitHubAPI:
    """Mock GitHub API for unit tests."""
    
    def __init__(self):
        self.created_repos = []
        self.api_calls = []
        
    def create_repository(self, name: str, private: bool = False, 
                         organization: str = None, **kwargs) -> Dict[str, Any]:
        """Mock repository creation."""
        self.api_calls.append({
            'method': 'create_repository',
            'args': locals()
        })
        
        repo_data = {
            'name': name,
            'private': private,
            'organization': organization,
            'html_url': f"https://github.com/{organization or 'test-user'}/{name}",
            'clone_url': f"https://github.com/{organization or 'test-user'}/{name}.git",
            'created': True
        }
        
        self.created_repos.append(repo_data)
        return repo_data
        
    def delete_repository(self, name: str, owner: str = None) -> bool:
        """Mock repository deletion."""
        self.api_calls.append({
            'method': 'delete_repository',
            'args': locals()
        })
        
        # Remove from created repos
        self.created_repos = [r for r in self.created_repos 
                            if r['name'] != name]
        return True


def create_test_config(overrides: Dict[str, Any] = None) -> Dict[str, Any]:
    """Create a test configuration dictionary."""
    config = {
        "name": "test-project",
        "description": "Test project for RepoKit",
        "language": "python",
        "branches": ["main", "dev"],
        "worktrees": ["main", "dev"],
        "directories": ["docs", "tests", "scripts"],
        "private_dirs": ["private", "logs"],
        "private_branch": "private",
        "github": True,
        "user": {
            "name": "Test User",
            "email": "test@example.com"
        }
    }
    
    if overrides:
        config.update(overrides)
        
    return config