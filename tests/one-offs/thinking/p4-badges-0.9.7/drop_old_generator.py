"""Remove 0.9.6's reference-style badge generator, renamed _generate_badges_v096,
from repokit/repo_manager.py: the block from its def up to the next method,
_license_spdx. Asserts both anchors appear exactly once; writes nothing otherwise.

    python tests/one-offs/thinking/p4-badges-0.9.7/drop_old_generator.py
"""
from pathlib import Path

PATH = Path(__file__).resolve().parents[4] / "repokit" / "repo_manager.py"
START = "    def _generate_badges_v096(self, language: str) -> str:\n"
END = "    def _license_spdx(self) -> Optional[str]:\n"

text = PATH.read_text(encoding="utf-8")
assert text.count(START) == 1 and text.count(END) == 1, "anchors not unique"
a, b = text.index(START), text.index(END)
assert a < b
removed = text[a:b]
assert "[workflow-badge]" in removed and "def " not in removed[len(START):], "unexpected block"
PATH.write_text(text[:a] + text[b:], encoding="utf-8")
print(f"removed {removed.count(chr(10))} lines")
