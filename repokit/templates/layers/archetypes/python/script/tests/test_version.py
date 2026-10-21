"""The script answers --version with the VERSION file's content, and --help exits 0."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "__RK_PROJECT__.py"


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=str(ROOT),
                          capture_output=True, text=True, encoding="utf-8")


def test_version_matches_the_version_file():
    r = run("--version")
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def test_help_exits_cleanly():
    r = run("--help")
    assert r.returncode == 0, r.stderr
    assert "__RK_PROJECT__" in r.stdout
