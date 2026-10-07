"""
Test isolation for the RepoKit suite.

Every test runs as if on a clean machine, whatever the developer's own
setup is:

- git never signs: tests make throwaway commits, and a global
  ``commit.gpgsign=true`` would otherwise pop a signing prompt for each one.
  Identity and the default branch are pinned too, so results do not depend
  on anyone's ``~/.gitconfig``.
- HOME and USERPROFILE point at a temporary directory, so nothing a test
  runs (``repokit store-credentials`` included) can write to the real
  ``~/.repokit/credentials.json``.
- GitHub tokens are blanked unless ``REPOKIT_LIVE_GITHUB=1`` is set, and
  tests marked ``live`` are skipped without it. Live tests create real
  repositories, so running them is always an explicit choice.

The settings are applied in ``pytest_configure`` -- before any test module
is imported -- because ``tests/test_utils.py`` reads the token at import
time. Child processes (``python -m repokit ...``, ``git ...``) inherit them.
"""

import os
import shutil
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

LIVE_ENV = "REPOKIT_LIVE_GITHUB"

# git's environment-based config: these override every config file.
GIT_OVERRIDES = {
    "commit.gpgsign": "false",
    "tag.gpgsign": "false",
    "user.name": "RepoKit Test",
    "user.email": "repokit-test@example.invalid",
    "init.defaultBranch": "main",
}

TOKEN_VARS = ("REPOKIT_TEST_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN")

_saved_env = {}
_temp_home = None


def live_github_enabled():
    """True only when the person running the suite opted in to live GitHub tests."""
    return os.environ.get(LIVE_ENV) == "1"


def _set(name, value):
    if name not in _saved_env:
        _saved_env[name] = os.environ.get(name)
    os.environ[name] = value


def pytest_configure(config):
    global _temp_home

    config.addinivalue_line(
        "markers",
        f"live: talks to the real GitHub API; skipped unless {LIVE_ENV}=1",
    )

    _set("GIT_CONFIG_COUNT", str(len(GIT_OVERRIDES)))
    for i, (key, value) in enumerate(GIT_OVERRIDES.items()):
        _set(f"GIT_CONFIG_KEY_{i}", key)
        _set(f"GIT_CONFIG_VALUE_{i}", value)

    _temp_home = tempfile.mkdtemp(prefix="repokit-test-home-")
    _set("HOME", _temp_home)
    _set("USERPROFILE", _temp_home)

    # `python -m repokit` runs from temporary working directories; make the
    # package under test importable there without installing it.
    pythonpath = os.environ.get("PYTHONPATH", "")
    _set("PYTHONPATH", os.pathsep.join(p for p in (str(REPO_ROOT), pythonpath) if p))
    _set("PYTHONIOENCODING", "utf-8")

    if not live_github_enabled():
        for name in TOKEN_VARS:
            _set(name, "")


def pytest_unconfigure(config):
    for name, value in _saved_env.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
    if _temp_home and os.path.isdir(_temp_home):
        shutil.rmtree(_temp_home, ignore_errors=True)


def pytest_collection_modifyitems(config, items):
    if live_github_enabled():
        return
    skip_live = pytest.mark.skip(reason=f"live GitHub test; set {LIVE_ENV}=1 to run")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
