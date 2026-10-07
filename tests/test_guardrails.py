#!/usr/bin/env python3
"""
Tests for RepoKit guardrails functionality.
"""

import unittest
import tempfile
import os
import subprocess
from pathlib import Path

import pytest

from repokit.branch_utils import BranchContext
from repokit.guardrails import GuardrailsManager

from .test_utils import force_rmtree

# builds real git repositories with hooks
pytestmark = pytest.mark.integration


class TestBranchContext(unittest.TestCase):
    """Test branch detection and validation."""
    
    def setUp(self):
        """Set up test repository."""
        self.test_dir = tempfile.mkdtemp()
        self.orig_dir = os.getcwd()
        os.chdir(self.test_dir)
        
        # Initialize git repo
        subprocess.run(['git', 'init'], check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], check=True, capture_output=True)
        
        # Create initial commit
        Path('README.md').write_text('# Test Repo')
        subprocess.run(['git', 'add', 'README.md'], check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'Initial commit'], check=True, capture_output=True)
    
    def tearDown(self):
        """Clean up test repository."""
        os.chdir(self.orig_dir)
        force_rmtree(self.test_dir)

    def test_branch_detection(self):
        """Test branch type detection."""
        context = BranchContext()
        
        # Test default branch (should be public)
        self.assertEqual(context.branch_type, 'public')
        self.assertTrue(context.is_public_branch())
        self.assertFalse(context.is_private_branch())
        
        # Create and switch to private branch
        subprocess.run(['git', 'checkout', '-b', 'private'], check=True, capture_output=True)
        context = BranchContext()  # New context for new branch
        
        self.assertEqual(context.current_branch, 'private')
        self.assertEqual(context.branch_type, 'private')
        self.assertTrue(context.is_private_branch())
        self.assertFalse(context.is_public_branch())
        
        # Test feature branch (should be private)
        subprocess.run(['git', 'checkout', '-b', 'feature/test'], check=True, capture_output=True)
        context = BranchContext()
        
        self.assertEqual(context.branch_type, 'private')
        self.assertTrue(context.is_private_branch())
    
    def test_private_file_detection(self):
        """Test detection of private files."""
        context = BranchContext()
        
        # Test exact matches
        private_files = context.check_private_files(['CLAUDE.md', 'README.md'])
        self.assertEqual(len(private_files), 1)
        self.assertEqual(private_files[0][0], 'CLAUDE.md')
        
        # Test directory patterns
        private_files = context.check_private_files(['private/notes.md', 'public/index.html'])
        # This might match multiple rules, so just check it's detected
        self.assertTrue(len(private_files) >= 1)
        self.assertTrue(any(f[0] == 'private/notes.md' for f in private_files))
        
        # Test nested directories
        private_files = context.check_private_files(['private/claude/log.md', 'src/main.py'])
        # This might match multiple rules too
        self.assertTrue(len(private_files) >= 1)
        self.assertTrue(any(f[0] == 'private/claude/log.md' for f in private_files))
    
    def test_commit_validation(self):
        """Test commit validation in different branches."""
        # Be on main, whatever git's default branch name is
        subprocess.run(['git', 'checkout', '-B', 'main'], check=True, capture_output=True)
        context = BranchContext()
        
        # Stage a private file
        Path('CLAUDE.md').write_text('# Private content')
        subprocess.run(['git', 'add', 'CLAUDE.md'], check=True, capture_output=True)
        
        # Should fail validation
        is_valid, errors = context.validate_commit()
        self.assertFalse(is_valid)
        self.assertTrue(any('CLAUDE.md' in error for error in errors))
        
        # Reset and try with non-private file
        subprocess.run(['git', 'reset', 'HEAD', 'CLAUDE.md'], check=True, capture_output=True)
        Path('src/app.py').parent.mkdir(exist_ok=True)
        Path('src/app.py').write_text('print("Hello")')
        subprocess.run(['git', 'add', 'src/app.py'], check=True, capture_output=True)
        
        # Should pass validation
        is_valid, errors = context.validate_commit()
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        
        # Switch to private branch - should allow any files
        subprocess.run(['git', 'checkout', '-b', 'private'], check=True, capture_output=True)
        subprocess.run(['git', 'add', 'CLAUDE.md'], check=True, capture_output=True)
        
        context = BranchContext()
        is_valid, errors = context.validate_commit()
        self.assertTrue(is_valid)


class TestGuardrailsManager(unittest.TestCase):
    """Test guardrails installation and management."""
    
    def setUp(self):
        """Set up test repository."""
        self.test_dir = tempfile.mkdtemp()
        self.orig_dir = os.getcwd()
        os.chdir(self.test_dir)
        
        # Initialize git repo
        subprocess.run(['git', 'init'], check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], check=True, capture_output=True)
        
        # Create initial commit
        Path('README.md').write_text('# Test Repo')
        subprocess.run(['git', 'add', 'README.md'], check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'Initial commit'], check=True, capture_output=True)
    
    def tearDown(self):
        """Clean up test repository."""
        os.chdir(self.orig_dir)
        force_rmtree(self.test_dir)

    def test_guardrails_setup(self):
        """Test guardrails installation."""
        manager = GuardrailsManager()
        
        # Check initial state
        self.assertFalse((Path('.git/hooks/pre-commit')).exists())
        self.assertFalse((Path('.git/hooks/post-checkout')).exists())
        
        # Install guardrails
        success = manager.setup_guardrails()
        self.assertTrue(success)
        
        # Check hooks were installed
        self.assertTrue((Path('.git/hooks/pre-commit')).exists())
        self.assertTrue((Path('.git/hooks/post-checkout')).exists())
        
        # Check hooks are executable
        pre_commit = Path('.git/hooks/pre-commit')
        self.assertTrue(os.access(pre_commit, os.X_OK))
    
    def test_status_check(self):
        """Test guardrails status checking."""
        manager = GuardrailsManager()
        
        # Check status before setup
        status = manager.check_status()
        self.assertFalse(status['pre_commit_hook'])
        self.assertFalse(status['post_checkout_hook'])
        
        # Setup and check again
        manager.setup_guardrails()
        status = manager.check_status()
        self.assertTrue(status['pre_commit_hook'])
        self.assertTrue(status['post_checkout_hook'])
        self.assertTrue(status['excludes_configured'])
    
    def test_merge_validation(self):
        """Test merge validation."""
        manager = GuardrailsManager()
        
        # Test merging from private to public branch
        excludes = manager.context.get_merge_excludes('private', 'main')
        self.assertIn('CLAUDE.md', excludes)
        self.assertIn('private/claude/', excludes)
        
        # Test merging between public branches
        excludes = manager.context.get_merge_excludes('dev', 'main')
        self.assertEqual(len(excludes), 0)
    
    def test_branch_excludes_setup(self):
        """Test branch-specific exclude configuration."""
        # Start in main branch, whatever git's default branch name is
        subprocess.run(['git', 'checkout', '-B', 'main'], check=True, capture_output=True)
        
        context = BranchContext()
        context.setup_branch_excludes()
        
        # Check exclude file contains private patterns
        exclude_file = Path('.git/info/exclude')
        content = exclude_file.read_text()
        self.assertIn('CLAUDE.md', content)
        self.assertIn('private/claude/', content)
        
        # Switch to private branch
        subprocess.run(['git', 'checkout', '-b', 'private'], check=True, capture_output=True)
        
        context = BranchContext()
        context.setup_branch_excludes()
        
        # Check exclude file has minimal excludes
        content = exclude_file.read_text()
        self.assertIn('test-runs/', content)
        self.assertNotIn('CLAUDE.md', content)  # Should not exclude in private branch


if __name__ == '__main__':
    unittest.main()