#!/usr/bin/env python3
"""
RepoKit Test Runner

Choose which part of the suite to run. This is a thin driver around pytest:
the categories are pytest markers assigned in tests/conftest.py, and that
file also isolates every run (no commit signing, a temporary home directory,
no GitHub token unless live tests are asked for).

Usage:
    python tests/run_tests.py                    # Run all tests (live GitHub tests skipped)
    python tests/run_tests.py --unit             # Run only unit tests (fast)
    python tests/run_tests.py --integration      # Run only integration tests (CLI, real git repos)
    python tests/run_tests.py --github           # Run only GitHub API tests (live; requires token)
    python tests/run_tests.py --deployment       # Run only deployment scenario tests (live; requires token)
    python tests/run_tests.py --no-cleanup       # Keep the GitHub repositories live tests create
    python tests/run_tests.py --keep-run         # Keep the test run directory for debugging
    python tests/run_tests.py --verbose          # Verbose output
    python tests/run_tests.py --test-dir DIR     # Use DIR as the (kept) test run directory
    python tests/run_tests.py --check            # Check the test environment; runs nothing
    python tests/run_tests.py --unit -- -k config   # anything after -- goes to pytest
"""

import argparse
import datetime
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_RUNS = REPO_ROOT / "test_runs"  # git-ignored

LIVE_ENV = "REPOKIT_LIVE_GITHUB"

# category flag -> (pytest marker expression, needs live GitHub)
CATEGORIES = {
    "unit": ("unit", False),
    "integration": ("integration", False),
    "github": ("live", True),
    "deployment": ("deployment", True),
}


def build_parser():
    parser = argparse.ArgumentParser(
        description="Run RepoKit test suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--unit", action="store_true", help="Run only unit tests")
    group.add_argument("--integration", action="store_true", help="Run only integration tests")
    group.add_argument("--github", action="store_true",
                       help="Run only GitHub API tests (live: creates real repositories; requires token)")
    group.add_argument("--deployment", action="store_true",
                       help="Run only deployment scenario tests (live; requires token)")

    parser.add_argument("--no-cleanup", action="store_true",
                        help="Skip cleanup of test repositories on GitHub")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose test output")
    parser.add_argument("--keep-run", action="store_true",
                        help=f"Keep the test run directory (under {TEST_RUNS.name}/) for debugging")
    parser.add_argument("--test-dir", help="Use this directory for the test run (kept)")
    parser.add_argument("--check", action="store_true", help="Check test environment setup; runs nothing")
    return parser


def plan_run(argv, now=None):
    """Turn runner arguments into (pytest args, environment additions, run dir).

    Kept separate from running so it can be tested without starting a
    second pytest.
    """
    if "--" in argv:
        split = argv.index("--")
        own, passthrough = argv[:split], argv[split + 1:]
    else:
        own, passthrough = argv, []
    args = build_parser().parse_args(own)

    pytest_args = [str(REPO_ROOT / "tests"), "-p", "no:cacheprovider"]
    env = {}

    chosen = next((name for name in CATEGORIES if getattr(args, name)), None)
    if chosen:
        marker, live = CATEGORIES[chosen]
        pytest_args += ["-m", marker]
        if live:
            env[LIVE_ENV] = "1"

    pytest_args.append("-v" if args.verbose else "-q")

    if args.no_cleanup:
        env["REPOKIT_TEST_CLEANUP"] = "false"

    run_dir = None
    if args.test_dir:
        run_dir = Path(args.test_dir).resolve()
    elif args.keep_run:
        stamp = (now or datetime.datetime.now()).strftime("%Y_%m_%d__%H_%M_%S")
        run_dir = TEST_RUNS / f"test_run_{stamp}"
    if run_dir is not None:
        env["REPOKIT_TEST_RUN_DIR"] = str(run_dir)

    return args, pytest_args + passthrough, env, run_dir


def check_environment():
    """Report what the live tests would need. Never prints a token."""
    print("Checking test environment...")

    env_file = REPO_ROOT / ".env.test"
    if env_file.exists():
        print("[OK] Found .env.test")
        keys = {
            line.split("=", 1)[0].strip()
            for line in env_file.read_text(encoding="utf-8").splitlines()
            if "=" in line and not line.lstrip().startswith("#")
        }
        if "REPOKIT_TEST_GITHUB_TOKEN" in keys:
            print("[OK] REPOKIT_TEST_GITHUB_TOKEN is set in .env.test")
        else:
            print("[--] No REPOKIT_TEST_GITHUB_TOKEN in .env.test; --github/--deployment tests will skip")
    else:
        print("[--] No .env.test; --github/--deployment tests will skip")
    print(f"     .env.test is read only for --github/--deployment ({LIVE_ENV}=1)")

    print(f"[OK] Python {sys.version.split()[0]}")
    try:
        import pytest  # noqa: F401
        print("[OK] pytest available")
    except ImportError:
        print("[X]  pytest not installed: pip install -e \".[dev]\"")
    try:
        import repokit  # noqa: F401
        print("[OK] repokit importable")
    except ImportError:
        print("[--] repokit not installed; the tests add the checkout to PYTHONPATH themselves")
    print()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    args, pytest_args, env, run_dir = plan_run(argv)

    if args.check:
        check_environment()
        return 0

    import pytest

    if run_dir is not None:
        run_dir.mkdir(parents=True, exist_ok=True)
        print(f"Test run directory (kept): {run_dir}")

    os.environ.update(env)
    print("pytest " + " ".join(pytest_args))
    return int(pytest.main(pytest_args))


if __name__ == "__main__":
    sys.exit(main())
