"""Replace the local temp folder in the 0.10.3 mutation reports with <TEMP> before
they are committed (they record pytest's tmp_path, which names the user)."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TEMP = re.compile(r"C:(?:/|\\\\|\\)+Users(?:/|\\\\|\\)+[^/\\\"]+(?:/|\\\\|\\)+AppData(?:/|\\\\|\\)+Local(?:/|\\\\|\\)+Temp")

for rel in sys.argv[1:]:
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    new, n = TEMP.subn("<TEMP>", text)
    new, m = re.subn(r"pytest-of-[^/\\\"]+", "pytest-of-<USER>", new)
    n += m
    path.write_text(new, encoding="utf-8", newline="\n")
    print(rel, n)
