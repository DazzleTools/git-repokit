#!/usr/bin/env python3
"""
Utility functions for RepoKit.

Provides general-purpose utility functions for file operations,
pattern matching, and other common tasks.
"""

import os
import fnmatch
import shutil
import logging
from pathlib import Path
from typing import List, Set, Dict, Any, Optional, Union

# Set up logger
logger = logging.getLogger("repokit.utils")


def match_pattern(path: str, pattern: str) -> bool:
    """
    Check if a path matches a pattern.

    Args:
        path: Path to check
        pattern: Pattern to match against (supports * wildcard)

    Returns:
        True if path matches pattern, False otherwise
    """
    # Handle directory patterns (ending with /)
    if pattern.endswith("/"):
        dir_pattern = pattern[:-1]
        path_parts = path.split(os.sep)
        return any(fnmatch.fnmatch(part, dir_pattern) for part in path_parts)

    # Check if the filename matches the pattern
    return fnmatch.fnmatch(os.path.basename(path), pattern)


def glob_to_ere(pattern: str) -> str:
    """A private-content pattern as a POSIX extended regex for `grep -E`.

    Anchored at the start of the path. Regex metacharacters are escaped, so
    `*.log` no longer matches `catalog.py`; `*` matches any run of characters
    (across `/`, as the hooks always read it), `**/` any directory prefix or
    none, a trailing `/` everything inside that directory, and a pattern with
    no `*` the whole path.
    """
    is_dir = pattern.endswith("/")
    body = pattern.rstrip("/") if is_dir else pattern
    out: List[str] = []
    i = 0
    while i < len(body):
        if body.startswith("**/", i):
            out.append("(.*/)?")
            i += 3
            continue
        c = body[i]
        if c == "*":
            out.append(".*")
        elif c in ".+?()[]{}^$|\\":
            out.append("\\" + c)
        else:
            out.append(c)
        i += 1
    core = "".join(out)
    if is_dir:
        return f"^{core}/"
    if "*" in body:
        return f"^{core}"
    return f"^{core}$"


def should_include_file(
    path: str,
    rel_path: str,
    include_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
) -> bool:
    """
    Check if a file should be included based on patterns.

    Args:
        path: Full path to the file
        rel_path: Relative path from source directory
        include_patterns: List of patterns to include (if None, include all)
        exclude_patterns: List of patterns to exclude

    Returns:
        True if the file should be included, False otherwise
    """
    # Always exclude .git directory
    if ".git" in rel_path.split(os.sep):
        return False

    # Check exclude patterns first
    if exclude_patterns:
        for pattern in exclude_patterns:
            if match_pattern(rel_path, pattern):
                return False

    # If no include patterns, include everything not excluded
    if not include_patterns:
        return True

    # Check if path matches any include pattern
    for pattern in include_patterns:
        if match_pattern(rel_path, pattern):
            return True

    # Check if any parent directory matches an include pattern
    path_parts = rel_path.split(os.sep)
    for i in range(len(path_parts)):
        parent_path = os.sep.join(path_parts[: i + 1])
        for pattern in include_patterns:
            if pattern.endswith("/") and match_pattern(parent_path, pattern[:-1]):
                return True

    return False


def copy_files(
    source_dir: str,
    target_dir: str,
    include_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
    preserve_directory_structure: bool = True,
) -> int:
    """
    Copy files from source to target directory based on patterns.

    Args:
        source_dir: Source directory
        target_dir: Target directory
        include_patterns: List of patterns to include (if None, include all)
        exclude_patterns: List of patterns to exclude
        preserve_directory_structure: Whether to preserve directory structure

    Returns:
        Number of files copied
    """
    copied_files = 0
    source_dir = os.path.abspath(source_dir)
    target_dir = os.path.abspath(target_dir)

    logger.info(f"Copying files from {source_dir} to {target_dir}")

    # Create standard exclude patterns if not provided
    if exclude_patterns is None:
        exclude_patterns = [
            "__pycache__/",
            "*.py[cod]",
            "*$py.class",
            "*.so",
            ".git/",
            "*.egg-info/",
            "*.egg",
            "dist/",
            "build/",
            "credentials.json",
            "*.token",
            ".env",
            "*.bak",
            "*.tmp",
            "*.swp",
            "*~",
            "*.*~",
        ]

    # Walk through the source directory
    for dirpath, dirnames, filenames in os.walk(source_dir):
        # Get relative path
        rel_path = os.path.relpath(dirpath, source_dir)

        # Skip entire directories if they match exclude patterns
        skip_dir = False
        for pattern in exclude_patterns:
            if pattern.endswith("/") and match_pattern(rel_path, pattern[:-1]):
                logger.debug(f"Skipping directory: {rel_path}")
                dirnames[:] = []  # Clear dirnames to skip recursion
                skip_dir = True
                break

        if skip_dir:
            continue

        # Process files in this directory
        for filename in filenames:
            src_file = os.path.join(dirpath, filename)
            rel_file_path = (
                os.path.join(rel_path, filename) if rel_path != "." else filename
            )

            # Check if this file should be copied
            if not should_include_file(
                src_file, rel_file_path, include_patterns, exclude_patterns
            ):
                logger.debug(f"Skipping file: {rel_file_path}")
                continue

            # Determine target path
            if preserve_directory_structure:
                target_file = os.path.join(target_dir, rel_file_path)
                # Create target directory if needed
                os.makedirs(os.path.dirname(target_file), exist_ok=True)
            else:
                target_file = os.path.join(target_dir, filename)

            # Copy the file
            try:
                shutil.copy2(src_file, target_file)
                copied_files += 1
                logger.debug(f"Copied: {rel_file_path}")
            except Exception as e:
                logger.error(f"Error copying {src_file}: {str(e)}")

    logger.info(f"Copied {copied_files} files to {target_dir}")
    return copied_files


def copy_file_with_directory(source_file: str, target_dir: str) -> bool:
    """
    Copy a single file to a target directory, creating directories as needed.

    Args:
        source_file: Path to source file
        target_dir: Target directory

    Returns:
        True if successful, False otherwise
    """
    try:
        source_file = os.path.abspath(source_file)
        target_dir = os.path.abspath(target_dir)

        if not os.path.exists(source_file):
            logger.error(f"Source file does not exist: {source_file}")
            return False

        # Create target directory if it doesn't exist
        os.makedirs(target_dir, exist_ok=True)

        # Copy the file
        target_file = os.path.join(target_dir, os.path.basename(source_file))
        shutil.copy2(source_file, target_file)
        logger.debug(f"Copied: {source_file} to {target_file}")
        return True
    except Exception as e:
        logger.error(f"Error copying {source_file}: {str(e)}")
        return False


def get_essential_file_patterns() -> Dict[str, List[str]]:
    """
    Get patterns for essential files and directories in a project.

    Returns:
        Dictionary with include and exclude patterns for essential files
    """
    return {
        "include": [
            # Standard Python project files
            "setup.py",
            "pyproject.toml",
            "README.md",
            "LICENSE",
            "MANIFEST.in",
            "requirements.txt",
            # Main package and critical directories
            "repokit/",
            "docs/",
            "scripts/",
            "templates/",
        ],
        "exclude": [
            # Python bytecode and cache
            "__pycache__/",
            "*.py[cod]",
            "*$py.class",
            "*.so",
            # Build artifacts
            "dist/",
            "build/",
            "*.egg-info/",
            "*.egg",
            # Version control
            ".git/",
            ".gitignore",
            ".gitattributes",
            # Credentials and secrets
            "credentials.json",
            "*.token",
            ".env",
            # Virtual environments
            "venv/",
            ".venv/",
            "env/",
            ".env/",
            # Temporary files
            "*.bak",
            "*.tmp",
            "*.swp",
            "*~",
            # IDE files
            ".vscode/",
            ".idea/",
            "*.sublime-*",
            # Test directories
            "test*/",
            # Private directories
            "private/",
            "convos/",
            "logs/",
        ],
    }
