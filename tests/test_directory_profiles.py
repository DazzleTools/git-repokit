#!/usr/bin/env python3
"""
Test cases for directory profile functionality.
"""

import os
import sys
import json
import tempfile
import shutil
import unittest
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from repokit.directory_profiles import DirectoryProfileManager, DEFAULT_DIRECTORY_PROFILES
from repokit.config import ConfigManager


class TestDirectoryProfileManager(unittest.TestCase):
    """Test DirectoryProfileManager functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.manager = DirectoryProfileManager()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_default_profiles_exist(self):
        """Test that default profiles are loaded correctly."""
        self.assertIn("minimal", self.manager.profiles)
        self.assertIn("standard", self.manager.profiles)
        self.assertIn("complete", self.manager.profiles)
        
        # Check minimal profile contents
        minimal = self.manager.profiles["minimal"]
        self.assertEqual(len(minimal), 3)
        self.assertIn("src", minimal)
        self.assertIn("tests", minimal)
        self.assertIn("docs", minimal)

    def test_get_directories_for_profile(self):
        """Test getting directories for a specific profile."""
        minimal_dirs = self.manager.get_directories_for_profile("minimal")
        self.assertEqual(len(minimal_dirs), 3)
        
        standard_dirs = self.manager.get_directories_for_profile("standard")
        self.assertGreater(len(standard_dirs), len(minimal_dirs))
        
        # Test fallback for unknown profile
        unknown_dirs = self.manager.get_directories_for_profile("unknown")
        self.assertEqual(unknown_dirs, self.manager.profiles["standard"])

    def test_get_directories_for_groups(self):
        """Test getting directories for specific groups."""
        dev_dirs = self.manager.get_directories_for_groups(["development"])
        self.assertIn("src", dev_dirs)
        self.assertIn("tests", dev_dirs)
        self.assertIn("scripts", dev_dirs)
        
        # Test multiple groups
        multi_dirs = self.manager.get_directories_for_groups(["development", "documentation"])
        self.assertIn("src", multi_dirs)
        self.assertIn("docs", multi_dirs)
        self.assertIn("examples", multi_dirs)

    def test_get_private_directories(self):
        """Test getting private directories."""
        standard_private = self.manager.get_private_directories("standard")
        self.assertIn("private", standard_private)
        self.assertIn("convos", standard_private)
        self.assertIn("logs", standard_private)
        
        enhanced_private = self.manager.get_private_directories("enhanced")
        self.assertIn("secrets", enhanced_private)
        self.assertIn("local", enhanced_private)

    def test_get_actual_directory_name(self):
        """Test directory name mapping."""
        # Test default mapping
        self.assertEqual(self.manager.get_actual_directory_name("tests"), "tests")
        
        # Test src with package name
        self.assertEqual(
            self.manager.get_actual_directory_name("src", "mypackage"),
            "mypackage"
        )
        
        # Test src without package name
        self.assertEqual(self.manager.get_actual_directory_name("src"), "src")

    def test_get_all_directories(self):
        """Test getting all directories with various configurations."""
        # Test minimal profile
        dirs = self.manager.get_all_directories(
            profile="minimal",
            package_name="testpkg"
        )
        self.assertIn("standard", dirs)
        self.assertIn("private", dirs)
        self.assertEqual(len(dirs["standard"]), 3)  # docs, tests, testpkg (src becomes testpkg)
        self.assertIn("testpkg", dirs["standard"])
        self.assertIn("docs", dirs["standard"])
        self.assertIn("tests", dirs["standard"])
        
        # Test with groups
        dirs = self.manager.get_all_directories(
            profile="minimal",
            groups=["operations"],
            package_name="testpkg"
        )
        self.assertIn("config", dirs["standard"])
        self.assertIn("data", dirs["standard"])

    def test_create_directories(self):
        """Test directory creation."""
        created = self.manager.create_directories(
            self.temp_dir,
            profile="minimal",
            package_name="testapp"
        )
        
        # Check directories were created
        self.assertIn("testapp", created["standard"])
        self.assertIn("docs", created["standard"])
        self.assertIn("tests", created["standard"])
        
        # Check physical directories exist
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "testapp")))
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "docs")))
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "tests")))
        
        # Check .gitkeep files
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "docs", ".gitkeep")))

    def test_config_loading(self):
        """Test loading configuration from file."""
        config_file = os.path.join(self.temp_dir, "test_config.json")
        config_data = {
            "directory_profiles": {
                "custom": ["src", "tests", "docs", "custom_dir"]
            },
            "directory_groups": {
                "custom_group": ["custom1", "custom2"]
            }
        }
        
        with open(config_file, "w") as f:
            json.dump(config_data, f)
        
        manager = DirectoryProfileManager(config_file=config_file)
        
        # Check custom profile loaded
        self.assertIn("custom", manager.profiles)
        self.assertEqual(len(manager.profiles["custom"]), 4)
        self.assertIn("custom_dir", manager.profiles["custom"])
        
        # Check custom group loaded
        self.assertIn("custom_group", manager.groups)
        self.assertEqual(len(manager.groups["custom_group"]), 2)

    def test_save_config(self):
        """Test saving configuration to file."""
        config_file = os.path.join(self.temp_dir, "save_config.json")
        
        # Modify manager
        self.manager.profiles["test_profile"] = ["dir1", "dir2"]
        
        # Save config
        self.assertTrue(self.manager.save_config(config_file))
        
        # Load and verify
        with open(config_file, "r") as f:
            saved_config = json.load(f)
        
        self.assertIn("directory_profiles", saved_config)
        self.assertIn("test_profile", saved_config["directory_profiles"])

    def test_validate_directories(self):
        """Test directory validation."""
        # Create some test directories
        os.makedirs(os.path.join(self.temp_dir, "src"))
        os.makedirs(os.path.join(self.temp_dir, "tests"))
        os.makedirs(os.path.join(self.temp_dir, "unknown_dir"))
        
        result = self.manager.validate_directories(self.temp_dir)
        
        self.assertIn("src", result["existing"])
        self.assertIn("tests", result["existing"])
        self.assertIn("unknown_dir", result["unknown"])
        self.assertIn("docs", result["missing"])

    def test_suggest_profile(self):
        """Test profile suggestion based on existing directories."""
        # Create minimal directories
        os.makedirs(os.path.join(self.temp_dir, "src"))
        os.makedirs(os.path.join(self.temp_dir, "tests"))
        os.makedirs(os.path.join(self.temp_dir, "docs"))
        
        suggestion = self.manager.suggest_profile(self.temp_dir)
        # Should suggest minimal since we have all minimal directories
        self.assertIn(suggestion, ["minimal", "standard"])
        
        # Create more directories
        os.makedirs(os.path.join(self.temp_dir, "scripts"))
        os.makedirs(os.path.join(self.temp_dir, "config"))
        os.makedirs(os.path.join(self.temp_dir, "private"))
        
        suggestion = self.manager.suggest_profile(self.temp_dir)
        # Should now suggest standard
        self.assertEqual(suggestion, "standard")


class TestConfigManagerDirectoryProfiles(unittest.TestCase):
    """Test ConfigManager integration with directory profiles."""

    def setUp(self):
        """Set up test fixtures."""
        self.config_manager = ConfigManager()

    def test_resolve_directory_profiles_minimal(self):
        """Test resolving minimal directory profile."""
        # Set minimal profile
        self.config_manager.cli_config = {
            "directory_profile": "minimal",
            "name": "testproject"
        }
        self.config_manager.config = self.config_manager._merge_configs()
        self.config_manager.resolve_directory_profiles()
        
        # Should have only minimal directories
        dirs = self.config_manager.config.get("directories", [])
        self.assertEqual(len(dirs), 3)
        self.assertIn("testproject", dirs)  # src becomes project name
        self.assertIn("tests", dirs)
        self.assertIn("docs", dirs)

    def test_resolve_directory_profiles_with_groups(self):
        """Test resolving directory profiles with groups."""
        self.config_manager.cli_config = {
            "directory_groups": ["development", "documentation"],
            "name": "testproject"
        }
        self.config_manager.config = self.config_manager._merge_configs()
        self.config_manager.resolve_directory_profiles()
        
        dirs = self.config_manager.config.get("directories", [])
        self.assertIn("testproject", dirs)
        self.assertIn("tests", dirs)
        self.assertIn("docs", dirs)
        self.assertIn("scripts", dirs)
        self.assertIn("examples", dirs)

    def test_resolve_directory_profiles_with_additions(self):
        """Test resolving directory profiles with additional directories."""
        self.config_manager.cli_config = {
            "directory_profile": "minimal",
            "directories": ["data", "models"],
            "name": "mlproject"
        }
        self.config_manager.config = self.config_manager._merge_configs()
        self.config_manager.resolve_directory_profiles()
        
        dirs = self.config_manager.config.get("directories", [])
        # Should have minimal + additional
        self.assertEqual(len(dirs), 5)
        self.assertIn("mlproject", dirs)
        self.assertIn("tests", dirs)
        self.assertIn("docs", dirs)
        self.assertIn("data", dirs)
        self.assertIn("models", dirs)

    def test_private_set_configuration(self):
        """Test private directory set configuration."""
        self.config_manager.cli_config = {
            "directory_profile": "standard",
            "private_set": "enhanced",
            "name": "testproject"
        }
        self.config_manager.config = self.config_manager._merge_configs()
        self.config_manager.resolve_directory_profiles()
        
        private_dirs = self.config_manager.config.get("private_dirs", [])
        self.assertIn("private", private_dirs)
        self.assertIn("convos", private_dirs)
        self.assertIn("logs", private_dirs)
        self.assertIn("secrets", private_dirs)
        self.assertIn("local", private_dirs)

    def test_backward_compatibility(self):
        """No profile: the default directories. Run from an empty folder: the
        config manager reads a .repokit.json in the current directory, and in
        git-repokit's own checkout that record (2025) still lists convos/, logs/
        and revisions/ -- which kept this test green whatever the defaults said.
        Since 0.10.0 those three live in private/, never at the project root."""
        cwd = os.getcwd()
        os.chdir(tempfile.mkdtemp())
        try:
            manager = ConfigManager()
            manager.cli_config = {"name": "testproject"}
            manager.config = manager._merge_configs()
            manager.resolve_directory_profiles()
        finally:
            os.chdir(cwd)
        dirs = manager.config.get("directories", [])
        for d in ("docs", "private", "scripts", "tests"):
            self.assertIn(d, dirs)
        for d in ("convos", "logs", "revisions"):
            self.assertNotIn(d, dirs)
        for profile in ("standard", "complete"):
            listed = DirectoryProfileManager().profiles[profile]
            self.assertFalse({"convos", "logs", "revisions"} & set(listed), profile)
        # still protected: an older project's root folders stay out of public history
        self.assertTrue({"convos", "logs", "revisions"} <= set(manager.config["private_dirs"]))


if __name__ == "__main__":
    unittest.main()