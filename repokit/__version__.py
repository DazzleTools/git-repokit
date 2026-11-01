"""Version information for RepoKit.

Set by hand beside pyproject.toml's version (repokit-common's version sync is
off for this project); tests/test_packaging.py fails when the two differ, as
they did at 0.10.0 and 0.10.1, whose `repokit --version` printed 0.9.12.
"""

__version__ = "0.10.2"
__version_info__ = tuple(int(part) for part in __version__.split("."))