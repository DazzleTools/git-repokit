"""`repokit create --license` at the CLI (0.9.0, U2): a catalogue id renders
with holder and year, file= copies bytes, none writes nothing, nothing named
is refused before a file is written, and a private repository takes the
config's license_private. The suite's own licence is REPOKIT_LICENSE=mit from
tests/conftest.py; the refusal tests remove it.

Design: 2026-10-22__22-06-57__dev-workflow-process__0-9-x-parity-with-the-old-route.md.
"""
import datetime
import json
import os
from pathlib import Path
from unittest import mock

from .test_utils import RepoKitTestCase


class TestLicenseFlag(RepoKitTestCase):

    def _meta(self, name):
        return json.loads((Path(self.test_dir, name) / ".repokit.json").read_text(encoding="utf-8"))

    def test_a_catalogue_id_renders_holder_and_year(self):
        self.assert_repokit_success(["create", "demo", "--language", "python", "--license", "MIT",
                                     "--user-name", "Ada Example", "--no-push"])
        text = (Path(self.test_dir, "demo") / "LICENSE").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("MIT License"))
        self.assertIn(f"Copyright (c) {datetime.date.today().year} Ada Example", text)
        self.assertNotIn("__RK_", text)
        self.assertEqual(self._meta("demo")["license"], "mit")

    def test_an_or_later_variant_carries_its_notice(self):
        self.assert_repokit_success(["create", "demo", "--language", "generic", "--license", "gpl-3.0-or-later", "--no-push"])
        text = (Path(self.test_dir, "demo") / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("SPDX-License-Identifier: GPL-3.0-or-later", text)
        self.assertIn("GNU GENERAL PUBLIC LICENSE", text)

    def test_file_form_copies_the_bytes(self):
        src = Path(self.test_dir, "custom.txt")
        src.write_bytes(b"Custom terms.\r\nNo warranty.\r\n")
        self.assert_repokit_success(["create", "demo", "--language", "generic", "--license", f"file={src}", "--no-push"])
        self.assertEqual((Path(self.test_dir, "demo") / "LICENSE").read_bytes(), src.read_bytes())
        self.assertEqual(self._meta("demo")["license"], "file:custom.txt")

    def test_none_writes_no_file(self):
        self.assert_repokit_success(["create", "demo", "--language", "generic", "--license", "none", "--no-push"])
        self.assertFalse((Path(self.test_dir, "demo") / "LICENSE").exists())
        self.assertEqual(self._meta("demo")["license"], "none")

    def test_nothing_named_is_refused_before_anything_is_written(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("REPOKIT_LICENSE", None)
            code, out, err = self.run_repokit(["create", "demo", "--language", "python", "--no-push"])
        self.assertNotEqual(code, 0)
        self.assertIn("no licence named", out + err)
        self.assertIn("the catalogue has", out + err)
        self.assertFalse(Path(self.test_dir, "demo").exists())

    def test_an_unknown_id_is_refused_naming_the_catalogue(self):
        code, out, err = self.run_repokit(["create", "demo", "--language", "generic", "--license", "wtfpl", "--no-push"])
        self.assertNotEqual(code, 0)
        self.assertIn("unknown licence 'wtfpl'", out + err)
        self.assertFalse(Path(self.test_dir, "demo").exists())

    def test_the_global_config_names_the_default_and_the_private_default(self):
        home = Path(self.test_dir, "home")
        (home / ".repokit").mkdir(parents=True)
        (home / ".repokit" / "config.json").write_text(
            json.dumps({"license": "gpl-3.0", "license_private": "all-rights-reserved"}), encoding="utf-8")
        with mock.patch.dict(os.environ, {"HOME": str(home), "USERPROFILE": str(home)}):
            os.environ.pop("REPOKIT_LICENSE", None)
            self.assert_repokit_success(["create", "pub", "--language", "generic", "--no-push"])
            self.assert_repokit_success(["create", "priv", "--language", "generic", "--private-repo", "--no-push"])
            self.assert_repokit_success(["create", "flag", "--language", "generic", "--private-repo",
                                         "--license", "mit", "--no-push"])
        self.assertIn("GNU GENERAL PUBLIC LICENSE", (Path(self.test_dir, "pub") / "LICENSE").read_text(encoding="utf-8"))
        self.assertIn("All rights reserved", (Path(self.test_dir, "priv") / "LICENSE").read_text(encoding="utf-8"))
        self.assertTrue((Path(self.test_dir, "flag") / "LICENSE").read_text(encoding="utf-8").startswith("MIT License"))
        self.assertEqual(self._meta("priv")["license"], "all-rights-reserved")
