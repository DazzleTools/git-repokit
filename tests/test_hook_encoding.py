"""
The guardrails hooks must not crash on a console that is not UTF-8.

Their Python prints emoji; with output piped (a GUI git client, a tool
shell, Windows' default codepage) print() raised UnicodeEncodeError and the
pre-commit hook blocked every commit, including git-repokit's own.
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from repokit.guardrails import GuardrailsManager

from .test_utils import force_rmtree


class TestHookOutputEncoding(unittest.TestCase):

    def setUp(self):
        self.orig_dir = os.getcwd()
        self.repo = tempfile.mkdtemp(prefix="repokit-hook-")
        os.chdir(self.repo)
        subprocess.run(["git", "init", "-q"], check=True)
        Path("README.md").write_text("# test\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], check=True)
        self.assertTrue(GuardrailsManager().setup_guardrails())

    def tearDown(self):
        os.chdir(self.orig_dir)
        force_rmtree(self.repo)

    def commit_with_plain_output(self, filename):
        # Remove what the suite sets (tests/conftest.py) so the hook's Python
        # sees an ordinary piped, non-UTF-8 stdout.
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
        Path(filename).write_text("print('hello')\n", encoding="utf-8")
        subprocess.run(["git", "add", filename], check=True, env=env)
        return subprocess.run(
            ["git", "commit", "-m", f"add {filename}"],
            capture_output=True, env=env,
        )

    def test_pre_commit_hook_passes_with_piped_output(self):
        result = self.commit_with_plain_output("app.py")
        output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
        self.assertNotIn("UnicodeEncodeError", output)
        self.assertEqual(result.returncode, 0, output)


if __name__ == "__main__":
    unittest.main()
