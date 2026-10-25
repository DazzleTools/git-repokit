"""0.9.11: `repokit adopt` and the license.

adopt fills in what a project lacks, so it does not ask for a license the
project already has, or one the person has not chosen: a license file of
its own (LICENSE, LICENSE.md, COPYING, ... in any case) is kept with no
flag; with no file, the config's license is written as create would; with no
file and nothing named, the project is adopted without one and the run says
so. Only `create` refuses when no license is named. An explicit --license
still replaces the file.
"""
import json
import os
import subprocess
from pathlib import Path
from unittest import mock

from .test_utils import RepoKitTestCase


class TestAdoptLicense(RepoKitTestCase):

    def _project(self, name, license_file=None, text="Custom terms.\n"):
        project = Path(self.create_test_project(name, with_git=True))
        if license_file:
            (project / license_file).write_text(text, encoding="utf-8")
        # adopt asks before touching a tree with uncommitted changes
        subprocess.run(["git", "add", "-A"], cwd=project, capture_output=True)
        subprocess.run(["git", "commit", "-qm", "the project as it was"], cwd=project, capture_output=True)
        return project

    def _adopt(self, project, *extra, house_license=False):
        with mock.patch.dict(os.environ):
            if not house_license:
                os.environ.pop("REPOKIT_LICENSE", None)
            return self.run_repokit(["adopt", ".", "--no-push", *extra], cwd=str(project))

    def _record(self, project):
        return json.loads((project / ".repokit.json").read_text(encoding="utf-8")).get("license")

    def test_a_license_file_of_its_own_is_kept_with_no_flag(self):
        project = self._project("own-md", "LICENSE.md")
        code, out, err = self._adopt(project)
        self.assertEqual(code, 0, out + err)
        self.assertEqual((project / "LICENSE.md").read_text(encoding="utf-8"), "Custom terms.\n")
        self.assertFalse((project / "LICENSE").exists())
        self.assertEqual(self._record(project), "existing:LICENSE.md")

    def test_copying_counts_as_a_license_file(self):
        project = self._project("own-copying", "COPYING")
        code, out, err = self._adopt(project)
        self.assertEqual(code, 0, out + err)
        self.assertFalse((project / "LICENSE").exists())
        self.assertEqual(self._record(project), "existing:COPYING")

    def test_no_file_and_nothing_named_adopts_without_one_and_says_so(self):
        project = self._project("no-license")
        code, out, err = self._adopt(project)
        self.assertEqual(code, 0, out + err)
        self.assertFalse((project / "LICENSE").exists())
        self.assertIn("no license", (out + err).lower())
        self.assertIn("--license", out + err)
        self.assertEqual(self._record(project), "none")

    def test_no_file_takes_the_config_license_as_create_would(self):
        project = self._project("house-license")
        code, out, err = self._adopt(project, house_license=True)  # conftest sets REPOKIT_LICENSE=mit
        self.assertEqual(code, 0, out + err)
        self.assertTrue((project / "LICENSE").read_text(encoding="utf-8").startswith("MIT License"))
        self.assertEqual(self._record(project), "mit")

    def test_an_explicit_license_replaces_the_projects_own(self):
        project = self._project("replace", "LICENSE")
        code, out, err = self._adopt(project, "--license", "mit")
        self.assertEqual(code, 0, out + err)
        self.assertTrue((project / "LICENSE").read_text(encoding="utf-8").startswith("MIT License"))

    def test_create_still_refuses_when_nothing_is_named(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("REPOKIT_LICENSE", None)
            code, out, err = self.run_repokit(["create", "demo", "--no-push"])
        self.assertNotEqual(code, 0)
        self.assertFalse(Path(self.test_dir, "demo").exists())


def test_find_existing_names_the_projects_own_license_file(tmp_path):
    from repokit import licenses
    assert licenses.find_existing(str(tmp_path)) is None
    (tmp_path / "readme.md").write_text("x")
    assert licenses.find_existing(str(tmp_path)) is None
    (tmp_path / "license.txt").write_text("x")
    assert licenses.find_existing(str(tmp_path)) == "license.txt"
    (tmp_path / "LICENSE").write_text("x")
    assert licenses.find_existing(str(tmp_path)) == "LICENSE"  # the plain name first
    (tmp_path / "LICENSES").mkdir()
    assert licenses.find_existing(str(tmp_path)) == "LICENSE"
