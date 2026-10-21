#!/usr/bin/env python3
"""__RK_DESCRIPTION__

A plain script: one file, run directly, no packaging. The version lives in
the VERSION file beside this module (git-repokit-common's version tool keeps
it, the CHANGELOG and the tags in step).
"""

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read_version() -> str:
    """The content of VERSION beside this file, or a marker when it is missing."""
    try:
        return (HERE / "VERSION").read_text(encoding="utf-8").strip() or "0.0.0+unknown"
    except OSError:
        return "0.0.0+unknown"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="__RK_PROJECT__", description=__doc__.strip().splitlines()[0])
    parser.add_argument("--version", action="version", version=read_version())
    parser.add_argument("-v", "--verbose", action="store_true", help="say more while working")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.verbose:
        print(f"__RK_PROJECT__ {read_version()} starting")
    print("Hello from __RK_PROJECT__. Replace this with the script's work.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
