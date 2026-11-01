"""`repokit list-templates` runs.

It crashed on every run with "AttributeError: 'Namespace' object has no
attribute 'templates_dir'" from the 2025 tool until 0.10.2: its parser has no
--templates-dir, and its handler read args.templates_dir. Found by hand
(djdarcy, 2026-11-01); nothing ran the command before this test.
"""
import subprocess
import sys

import pytest


@pytest.mark.integration
def test_list_templates_runs_and_lists_the_structure_templates(tmp_path):
    result = subprocess.run([sys.executable, "-m", "repokit", "list-templates"], cwd=tmp_path,
                            capture_output=True, text=True, stdin=subprocess.DEVNULL,
                            encoding="utf-8", errors="replace")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Available templates:" in result.stdout
    assert "gitignore.template" in result.stdout
