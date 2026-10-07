"""
Test deployment scenarios from Deployment-Demo.md.

These tests use the real GitHub API to ensure deployment functionality works.
"""

import unittest
import os
import shutil
import time
import subprocess
from pathlib import Path

import pytest

from .test_utils import (
    RepoKitTestCase,
    requires_github_token,
    TestConfig
)


@pytest.mark.live
@pytest.mark.deployment
class TestDeploymentScenarios(RepoKitTestCase):
    """Test all deployment scenarios from documentation."""
    
    @requires_github_token
    def test_demo1_brand_new_project(self):
        """Test Demo 1: Brand New Project deployment."""
        # Create project directory
        project_name = f"demo1-calculator-{int(time.time())}"
        project_dir = self.create_test_project(project_name, with_git=False)
        
        # Add calculator code as in demo
        calculator_code = '''def add(a, b):
    """Add two numbers."""
    return a + b

def subtract(a, b):
    """Subtract two numbers."""
    return a - b

def main():
    print("Awesome Calculator!")
    print("2 + 3 =", add(2, 3))
    print("5 - 2 =", subtract(5, 2))

if __name__ == "__main__":
    main()
'''
        with open(os.path.join(project_dir, "main.py"), "w") as f:
            f.write(calculator_code)
            
        # Add requirements
        with open(os.path.join(project_dir, "requirements.txt"), "w") as f:
            f.write("# No external dependencies yet\n")
            
        # Analyze project
        stdout, stderr = self.assert_repokit_success(
            ["analyze", "."], 
            cwd=project_dir
        )
        
        # Verify analysis results
        self.assertIn("source_no_git", stdout)
        self.assertIn("python", stdout.lower())
        self.assertIn("low", stdout.lower())
        
        # Store credentials for test
        self.assert_repokit_success([
            "store-credentials",
            "--publish-to", "github",
            "--token", TestConfig.GITHUB_TOKEN
        ])
        
        # Generate unique repo name for test
        repo_name = self.generate_test_repo_name()
        self.github_cleanup.register_repo(repo_name)
        
        # Adopt and deploy
        stdout, stderr = self.assert_repokit_success([
            "adopt", ".",
            "--publish-to", "github",
            "--private-repo",
            "--ai", "claude",
            "--name", repo_name
        ], cwd=project_dir)
        
        # Verify results
        self.assertIn("GitHub repository created", stdout)
        self.assertIn(repo_name, stdout)
        
        # Check local structure
        self.assert_directory_structure(project_dir, [
            "docs", "tests", "scripts", "private"
        ])
        
        # Check files were preserved
        self.assert_file_exists(project_dir, "main.py")
        self.assert_file_exists(project_dir, "requirements.txt")
        
        # Check AI files
        self.assert_file_exists(os.path.join(project_dir, "private"), "CLAUDE.md")
        
        # Verify Git branches
        self.assert_git_branch_exists(project_dir, "main")
        self.assert_git_branch_exists(project_dir, "dev")
        self.assert_git_branch_exists(project_dir, "private")
        
    @requires_github_token
    def test_demo2_existing_python_project(self):
        """Test Demo 2: Existing Python Project migration."""
        # Create project with Git history
        project_name = f"demo2-weather-{int(time.time())}"
        project_dir = self.create_test_project(project_name, with_git=True, with_files=False)
        
        # Add weather app code
        weather_code = '''import requests

def get_weather(city):
    """Get weather for a city (mock implementation)."""
    return f"Weather in {city}: Sunny, 25°C"

if __name__ == "__main__":
    city = input("Enter city: ")
    print(get_weather(city))
'''
        with open(os.path.join(project_dir, "weather.py"), "w") as f:
            f.write(weather_code)
            
        with open(os.path.join(project_dir, "requirements.txt"), "w") as f:
            f.write("requests>=2.28.0\n")
            
        # Commit initial code
        subprocess.run(["git", "add", "."], cwd=project_dir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial weather app"], 
                      cwd=project_dir, capture_output=True)
        
        # Add tests
        tests_dir = os.path.join(project_dir, "tests")
        os.makedirs(tests_dir)
        
        test_code = '''import unittest
from weather import get_weather

class TestWeather(unittest.TestCase):
    def test_get_weather(self):
        result = get_weather("London")
        self.assertIn("London", result)
        self.assertIn("°C", result)

if __name__ == "__main__":
    unittest.main()
'''
        with open(os.path.join(tests_dir, "test_weather.py"), "w") as f:
            f.write(test_code)
            
        # Commit tests
        subprocess.run(["git", "add", "tests/"], cwd=project_dir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Add basic tests"], 
                      cwd=project_dir, capture_output=True)
        
        # Analyze project
        stdout, stderr = self.assert_repokit_success(
            ["analyze", "."], 
            cwd=project_dir
        )
        
        # Verify analysis
        self.assertIn("git_with_history", stdout)
        self.assertIn("python", stdout.lower())
        
        # Generate unique repo name
        repo_name = self.generate_test_repo_name()
        self.github_cleanup.register_repo(repo_name)
        
        # Adopt preserving history
        stdout, stderr = self.assert_repokit_success([
            "adopt", ".",
            "--strategy", "safe",
            "--publish-to", "github",
            "--name", repo_name
        ], cwd=project_dir)
        
        # Verify deployment
        self.assertIn("GitHub repository created", stdout)
        
        # Check Git history preserved
        result = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=project_dir,
            capture_output=True,
            text=True
        )
        self.assertIn("Initial weather app", result.stdout)
        self.assertIn("Add basic tests", result.stdout)
        
        # Check structure added
        self.assert_directory_structure(project_dir, ["docs", "scripts"])
        
        # Check original files preserved
        self.assert_file_exists(project_dir, "weather.py")
        self.assert_file_exists(project_dir, "requirements.txt")
        self.assert_file_exists(tests_dir, "test_weather.py")
        
    @requires_github_token
    def test_demo3_complex_multi_branch(self):
        """Test Demo 3: Complex Multi-Branch Project."""
        # Create complex project
        project_name = f"demo3-api-{int(time.time())}"
        project_dir = self.create_test_project(project_name, with_git=True, with_files=False)
        
        # Create Flask API
        api_code = '''from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/api/health')
def health():
    return jsonify({'status': 'healthy'})

@app.route('/api/version')
def version():
    return jsonify({'version': '1.0.0'})

if __name__ == '__main__':
    app.run(debug=True)
'''
        with open(os.path.join(project_dir, "app.py"), "w") as f:
            f.write(api_code)
            
        with open(os.path.join(project_dir, "requirements.txt"), "w") as f:
            f.write("Flask>=2.0.0\ngunicorn>=20.0.0\n")
            
        # Initial commit
        subprocess.run(["git", "add", "."], cwd=project_dir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial API service"], 
                      cwd=project_dir, capture_output=True)
        
        # Create develop branch
        subprocess.run(["git", "checkout", "-b", "develop"], 
                      cwd=project_dir, capture_output=True)
        
        # Add authentication module
        auth_code = '''def authenticate(token):
    """Simple token authentication."""
    return token == "valid-token"

def get_user_info(token):
    """Get user information from token."""
    if authenticate(token):
        return {"user": "demo", "role": "admin"}
    return None
'''
        with open(os.path.join(project_dir, "auth.py"), "w") as f:
            f.write(auth_code)
            
        subprocess.run(["git", "add", "auth.py"], cwd=project_dir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Add authentication module"], 
                      cwd=project_dir, capture_output=True)
        
        # Create feature branch
        subprocess.run(["git", "checkout", "-b", "feature/user-management"], 
                      cwd=project_dir, capture_output=True)
        
        # Add user model
        models_dir = os.path.join(project_dir, "models")
        os.makedirs(models_dir)
        
        user_model = '''class User:
    def __init__(self, username, email):
        self.username = username
        self.email = email
    
    def to_dict(self):
        return {
            'username': self.username,
            'email': self.email
        }
'''
        with open(os.path.join(models_dir, "user.py"), "w") as f:
            f.write(user_model)
            
        subprocess.run(["git", "add", "models/"], cwd=project_dir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Add user model"], 
                      cwd=project_dir, capture_output=True)
        
        # Go back to develop
        subprocess.run(["git", "checkout", "develop"], 
                      cwd=project_dir, capture_output=True)
        
        # Analyze
        stdout, stderr = self.assert_repokit_success(
            ["analyze", "."], 
            cwd=project_dir
        )
        
        # Should detect complex structure
        self.assertIn("git_with_history", stdout)
        
        # Generate unique repo name
        repo_name = self.generate_test_repo_name()
        self.github_cleanup.register_repo(repo_name)
        
        # Adopt with auto branch strategy
        stdout, stderr = self.assert_repokit_success([
            "adopt", ".",
            "--strategy", "safe",
            "--branch-strategy", "auto",
            "--publish-to", "github",
            "--name", repo_name
        ], cwd=project_dir)
        
        # Verify all branches preserved
        result = subprocess.run(
            ["git", "branch", "-a"],
            cwd=project_dir,
            capture_output=True,
            text=True
        )
        self.assertIn("develop", result.stdout)
        self.assertIn("feature/user-management", result.stdout)
        
        # Check files in different branches preserved
        self.assert_file_exists(project_dir, "app.py")
        self.assert_file_exists(project_dir, "auth.py")
        
    @requires_github_token 
    def test_demo4_legacy_migration(self):
        """Test Demo 4: Legacy Project Migration with conflicts."""
        # Create legacy project
        project_name = f"demo4-legacy-{int(time.time())}"
        project_dir = self.create_test_project(project_name, with_git=True, with_files=False)
        
        # Create conflicting setup.py
        legacy_setup = '''# Legacy setup.py with custom configuration
from setuptools import setup, find_packages

setup(
    name="legacy-tool",
    version="0.1.0",
    packages=find_packages(),
    # Custom legacy configuration here
    custom_legacy_setting=True,
)
'''
        with open(os.path.join(project_dir, "setup.py"), "w") as f:
            f.write(legacy_setup)
            
        # Create conflicting GitHub workflow
        github_dir = os.path.join(project_dir, ".github", "workflows")
        os.makedirs(github_dir, exist_ok=True)
        
        old_ci = '''# Legacy CI configuration
name: Old CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run legacy tests
        run: echo "Legacy testing approach"
'''
        with open(os.path.join(github_dir, "old-ci.yml"), "w") as f:
            f.write(old_ci)
            
        # Add legacy source code
        src_dir = os.path.join(project_dir, "src")
        os.makedirs(src_dir)
        
        legacy_app = '''"""Legacy application with old patterns."""

class LegacyProcessor:
    def __init__(self):
        self.data = []
    
    def process(self, item):
        # Old processing logic
        self.data.append(item.upper())
        return self.data

def main():
    processor = LegacyProcessor()
    processor.process("hello")
    processor.process("world")
    print("Processed:", processor.data)

if __name__ == "__main__":
    main()
'''
        with open(os.path.join(src_dir, "legacy_app.py"), "w") as f:
            f.write(legacy_app)
            
        # Commit legacy code
        subprocess.run(["git", "add", "."], cwd=project_dir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Legacy codebase"], 
                      cwd=project_dir, capture_output=True)
        
        # Analyze for conflicts
        stdout, stderr = self.assert_repokit_success(
            ["analyze", "."], 
            cwd=project_dir
        )
        
        # Generate unique repo name
        repo_name = self.generate_test_repo_name()
        self.github_cleanup.register_repo(repo_name)
        
        # Migrate with safe strategy
        stdout, stderr = self.assert_repokit_success([
            "adopt", ".",
            "--strategy", "safe",
            "--publish-to", "github",
            "--name", repo_name
        ], cwd=project_dir)
        
        # Verify backup files created
        self.assertTrue(
            os.path.exists(os.path.join(project_dir, "setup.py.backup")) or
            os.path.exists(os.path.join(project_dir, "setup.py")),
            "Setup.py should be preserved"
        )
        
        # Check legacy functionality preserved
        self.assert_file_exists(src_dir, "legacy_app.py")
        
        # Verify RepoKit structure added
        self.assert_directory_structure(project_dir, ["docs", "tests", "scripts"])


if __name__ == "__main__":
    unittest.main()