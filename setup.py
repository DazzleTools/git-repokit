# The package's metadata lives in pyproject.toml. This shim stays for tools
# that still call setup.py; it adds nothing of its own (0.9.8: the old copy
# named the package `repokit`, Python 3.6+ and no dependencies, contradicting
# pyproject.toml).
from setuptools import setup

setup()
