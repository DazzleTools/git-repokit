"""0.9.11: every `repokit <command> ...` line the CLI shows uses flags that exist.

The help epilogs and `repokit analyze`'s printed recommendation named
`adopt --strategy` (adopt's flag is --migration-strategy) and
`--language javascript` (the language is js-ts), and the 2025 docs copied
them. This reads every such line in repokit/cli.py, the help examples and the
printed commands alike, and checks each flag against that command's own
--help, and each --language value against the known languages.
"""
import re
import sys
from pathlib import Path

import pytest

from repokit import cli

REPO = Path(__file__).resolve().parents[1]
SOURCE = (REPO / "repokit" / "cli.py").read_text(encoding="utf-8")


def _help(capsys, monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["repokit", *argv, "--help"])
    with pytest.raises(SystemExit):
        cli.parse_arguments()
    return capsys.readouterr().out


def _commands(capsys, monkeypatch):
    top = _help(capsys, monkeypatch)
    m = re.search(r"\{([a-z,-]+)\}", top)
    return m.group(1).split(",")


DOCS = [REPO / "README.md"] + sorted((REPO / "docs").glob("*.md"))


def _lines_in(text, continuation):
    joined = re.sub(continuation + r"\n\s*", " ", text)
    return [(m.group(1), m.group(2))
            for m in re.finditer(r"repokit ([a-z][a-z-]+)((?: [^\n\"'`|#]*)?)", joined)]


def _example_lines():
    """`repokit <command> ...` lines in the source (recipe continuations, a
    `\\` at the end of a line, written `\\\\` in the source, joined), and in the
    README and the guides (a `\\` at the end of a line joined)."""
    lines = _lines_in(SOURCE, r"\\\\")
    for doc in DOCS:
        lines += _lines_in(doc.read_text(encoding="utf-8"), r"\\")
    return lines


def test_every_flag_in_a_shown_command_exists_on_that_command(capsys, monkeypatch):
    commands = _commands(capsys, monkeypatch)
    options = {}
    bad = []
    lines = [(c, rest) for c, rest in _example_lines() if c in commands]
    assert len(lines) > 20  # the help examples and the analyze recommendations
    for command, rest in lines:
        if command not in options:
            options[command] = set(re.findall(r"--[a-z][a-z-]*", _help(capsys, monkeypatch, command)))
        for flag in re.findall(r"(?<![\w-])--[a-z][a-z-]*", rest):
            if flag not in options[command]:
                bad.append(f"repokit {command}{rest.rstrip()}  ->  {flag}")
    assert not bad, "\n".join(bad)


def test_list_ends_with_the_license_catalogue_its_help_points_to(capsys, monkeypatch):
    """create's --license help and the guides say `repokit list` shows the
    license ids; until 0.9.11 it listed only the languages."""
    from repokit import licenses
    monkeypatch.setattr(sys, "argv", ["repokit", "list"])
    assert cli.main() == 0
    out = capsys.readouterr().out
    tail = out.split("licenses (--license", 1)[1]
    assert all(lid in tail for lid in licenses.known())
    monkeypatch.setattr(sys, "argv", ["repokit", "list", "python"])
    assert cli.main() == 0
    assert "licenses (--license" not in capsys.readouterr().out  # one language: its layers only


def test_every_language_in_a_shown_command_is_a_known_language():
    known = set(cli._known_language_names()) | {"generic"}
    bad = []
    for command, rest in _example_lines():
        for value in re.findall(r"--language[ =]([A-Za-z0-9_,.{}\[\]'-]+)", rest):
            if "{" in value:  # filled at run time, e.g. the detected language
                continue
            bad += [f"repokit {command}{rest.rstrip()}  ->  {v}" for v in value.split(",") if v not in known]
    assert not bad, "\n".join(bad)
