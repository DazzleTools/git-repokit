"""The license catalogue (0.9.0, U1): the record is true, every id renders,
the variants share a body, and the resolver's order and refusal hold."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from repokit import licenses

REPO = Path(__file__).resolve().parents[1]


def test_every_shipped_file_matches_its_record():
    rec = licenses.record()
    files = sorted(p for p in licenses.DIR.glob("*.txt"))
    assert files, "the catalogue is empty"
    for path in files:
        assert path.stem in rec, f"{path.name} has no row in LICENSES.md"
        assert licenses.file_sha256(path) == rec[path.stem][1], f"{path.name} changed without a new record row"
    assert set(rec) == {p.stem for p in files}, "LICENSES.md names a file the catalogue lacks"


def test_the_record_pins_one_source_commit():
    text = licenses.RECORD.read_text(encoding="utf-8")
    assert "github/choosealicense.com" in text
    assert "commit `f66c5dd01866041688edd87f658b6d5ac3304f1b`" in text


def test_every_id_renders_with_holder_and_year_and_no_token_left():
    for lid in licenses.known():
        out = licenses.render(lid, "Ada Example", 2031)
        assert "__RK_" not in out, lid
        assert "[year]" not in out and "[fullname]" not in out, lid
    mit = licenses.render("MIT", "Ada Example", 2031)
    assert "Copyright (c) 2031 Ada Example" in mit


def test_the_or_later_variants_share_the_base_body():
    base = licenses.render("gpl-3.0", "A", 2031)
    later = licenses.render("gpl-3.0-or-later", "A", 2031)
    assert later.endswith(base)
    assert "SPDX-License-Identifier: GPL-3.0-or-later" in later
    assert "Copyright (c) 2031 A" in later


def test_the_catalogue_is_the_github_and_gitlab_set():
    for lid in ("mit", "apache-2.0", "gpl-3.0", "agpl-3.0", "lgpl-3.0", "bsd-3-clause", "mpl-2.0",
                "unlicense", "cc0-1.0", "cc-by-4.0", "all-rights-reserved"):
        assert lid in licenses.known(), lid


def test_resolve_order_flag_then_config_then_refusal(tmp_path):
    assert licenses.resolve("MIT", "gpl-3.0", False, None) == ("catalogue", "mit")
    assert licenses.resolve(None, "gpl-3.0", False, None) == ("catalogue", "gpl-3.0")
    assert licenses.resolve(None, "gpl-3.0", True, "all-rights-reserved") == ("catalogue", "all-rights-reserved")
    assert licenses.resolve(None, "gpl-3.0", True, None) == ("catalogue", "gpl-3.0")
    assert licenses.resolve("none", "gpl-3.0", False, None) == ("none", None)
    f = tmp_path / "LICENSE.custom"
    f.write_text("custom\n")
    assert licenses.resolve(f"file={f}", None, False, None) == ("file", str(f))
    with pytest.raises(licenses.LicenseError, match="no license named"):
        licenses.resolve(None, None, False, None)
    with pytest.raises(licenses.LicenseError, match="unknown license"):
        licenses.resolve("wtfpl", None, False, None)
    with pytest.raises(licenses.LicenseError, match="not found"):
        licenses.resolve("file=" + str(tmp_path / "missing"), None, False, None)
