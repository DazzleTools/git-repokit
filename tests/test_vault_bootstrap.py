"""v0.9.4: the vault skeleton and the oracle's first prompt.

The skeleton is what /obsidian-init laid by hand before it read anything:
the vault's CLAUDE.md (its conventions and the three-session note), the map
stub, the oracle's index stubs, the two boards. The map's content needs a
model that has read the project, so the tool writes the oracle's first
prompt through ailib's prompt-file transport and commits nothing a model
would write. Design: 2026-10-22__22-06-57__dev-workflow-process__0-9-x-parity-with-the-old-route.md (row 0.9.4).
"""
import subprocess
from pathlib import Path

import pytest

from repokit import vault
from .test_utils import RepoKitTestCase

SKELETON = ["CLAUDE.md", "claude/_maps/MOC-demo.md", "claude/_oracle/manifest.md", "claude/_oracle/concepts.md",
            "claude/_oracle/backlinks.md", "claude/_todo/OPEN-LOOPS.md", "claude/_todo/ACTIVE-WORK.md"]


def test_write_skeleton_lays_every_file_once_and_keeps_existing_ones(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("mine\n", encoding="utf-8")
    written = vault.write_skeleton(str(tmp_path), "demo")
    assert written == sorted(SKELETON[1:])                    # mutation B5 (0.9.4): what was written is reported
    assert "CLAUDE.md" not in written                         # the existing file is kept
    assert (tmp_path / "CLAUDE.md").read_text(encoding="utf-8") == "mine\n"
    for rel in SKELETON[1:]:
        text = (tmp_path / rel).read_text(encoding="utf-8")
        assert "$project_name" not in text and "$date" not in text, rel
    assert "demo" in (tmp_path / "claude/_todo/ACTIVE-WORK.md").read_text(encoding="utf-8")
    assert vault.write_skeleton(str(tmp_path), "demo") == []  # a second run writes nothing


def test_the_vault_claude_md_carries_the_three_session_convention(tmp_path):
    vault.write_skeleton(str(tmp_path), "demo")
    text = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert "<PROJECT>__<YYYY-MM-DD>__<Role>" in text
    assert "/obsidian-update" in text


def test_bootstrap_writes_the_prompt_through_the_prompt_file_transport(tmp_path):
    (tmp_path / "README.md").write_text("# demo\n", encoding="utf-8")
    (tmp_path / "private" / "claude").mkdir(parents=True)
    vault.write_skeleton(str(tmp_path / "private"), "demo")
    path = vault.bootstrap(str(tmp_path), "demo")
    assert path and Path(path).name == "bootstrap-prompt.md"
    text = Path(path).read_text(encoding="utf-8")
    assert "Bootstrap the vault of demo" in text and "MOC-demo.md" in text and "README.md" in text
    assert "`claude/_todo/OPEN-LOOPS.md`" in text              # the vault's documents are listed
    assert list((tmp_path / "private" / "claude" / "_oracle").glob("prompt_*.md")) == []


def test_vault_init_none_writes_nothing_and_unknown_is_refused(tmp_path):
    assert vault.bootstrap(str(tmp_path), "demo", "none") is None
    with pytest.raises(ValueError, match="unknown vault_init"):
        vault.bootstrap(str(tmp_path), "demo", "cli")


@pytest.mark.integration
class TestCreatedVault(RepoKitTestCase):

    def test_a_created_vault_has_the_skeleton_committed_and_the_prompt_left_for_the_oracle(self):
        self.assert_repokit_success(["create", "demo", "--language", "python", "--no-push"])
        private = Path(self.test_dir, "demo", "private")
        for rel in SKELETON:
            self.assertTrue((private / rel).is_file(), rel)
        tracked = subprocess.run(["git", "-C", str(private), "ls-files"], capture_output=True, text=True).stdout.split()
        for rel in SKELETON:
            self.assertIn(rel, tracked)                           # in the vault's first commit
        self.assertTrue((private / "claude" / "_oracle" / "bootstrap-prompt.md").is_file())
        self.assertNotIn("claude/_oracle/bootstrap-prompt.md", tracked)  # the tool commits no prompt
