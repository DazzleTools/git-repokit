"""Command-line entry point for __RK_PROJECT__ (the `__RK_PROJECT__` command)."""

import argparse

from ._version import __app_name__, get_display_version


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=__app_name__, description="__RK_DESCRIPTION__")
    parser.add_argument("--version", action="version", version=f"{__app_name__} {get_display_version()}")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    del args  # nothing to do yet: replace this with the tool's work
    print(f"{__app_name__} {get_display_version()}")
    return 0
