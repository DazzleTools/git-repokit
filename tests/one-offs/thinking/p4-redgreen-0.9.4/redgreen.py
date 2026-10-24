"""Red-green audit for v0.9.4 (the vault skeleton and the bootstrap prompt):
revert each behaviour, run its tests, restore the file byte for byte, report.

    python tests/one-offs/thinking/p4-redgreen-0.9.4/redgreen.py
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
VAULT = "repokit/vault.py"
TESTS = "tests/test_vault_bootstrap.py"
REVERSIONS = [
    ("A: no skeleton in the vault's first commit", VAULT,
     "        write_skeleton(private_path, project_name)\n", "        pass\n", "created_vault"),
    ("B: no bootstrap prompt", VAULT,
     '    final = os.path.join(oracle, "bootstrap-prompt.md")\n    os.replace(response.artifact, final)\n    return final',
     "    return None", "bootstrap_writes or created_vault"),
    ("C: an existing vault file overwritten", VAULT,
     "            if os.path.exists(dest):\n                continue", "            if False:\n                continue",
     "write_skeleton"),
]


def main() -> int:
    bad = 0
    for label, rel, old, new, k in REVERSIONS:
        path = REPO / rel
        original = path.read_bytes()
        text = original.decode("utf-8")
        assert text.count(old) == 1, f"{label}: anchor not unique"
        path.write_bytes(text.replace(old, new).encode("utf-8"))
        try:
            r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", TESTS, "-k", k],
                               cwd=REPO, capture_output=True, text=True, timeout=600)
        finally:
            path.write_bytes(original)
        restored = path.read_bytes() == original
        last = (r.stdout.strip().splitlines() or ["?"])[-1]
        print(f"{label:46} {'RED' if r.returncode else 'green (!)'} -- {last} -- restored={restored}")
        bad += (not r.returncode) or (not restored)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
