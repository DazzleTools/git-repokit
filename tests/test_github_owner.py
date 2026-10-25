"""0.9.6: one owner, known before any file is written.

With --github the files used to say YOUR_GITHUB_USERNAME (seven files in a
real consumer's project), because the owner gh reports was read only after
they were rendered; CODEOWNERS named the git user.name; the record was left
untracked with an empty author; and the closing text told the person to set
up the remote --github was about to make. gh is the stub from
test_github_create.py, so nothing reaches GitHub.
"""
import json
import os
import subprocess

from .test_github_create import GhStubCase

PLACEHOLDER = "YOUR_GITHUB_USERNAME"


def tracked_text(project):
    """{path: text} for every tracked file outside the vendored tooling."""
    out = {}
    files = subprocess.run(["git", "ls-files"], cwd=project, capture_output=True, text=True).stdout.split()
    for rel in files:
        if rel.startswith("scripts/repokit-common/"):
            continue
        try:
            with open(os.path.join(project, rel), encoding="utf-8") as f:
                out[rel] = f.read()
        except (UnicodeDecodeError, OSError):
            pass
    return out


class TestOwner(GhStubCase):

    def create(self, *extra):
        return self.assert_repokit_success(["create", "demo", "--language", "python", "--license", "mit",
                                            "--extras", "all", "--topics", "cli,demo", "--no-common", *extra])

    def test_github_fills_every_file_with_gh_login(self):
        stdout, _ = self.create("--github")
        project = os.path.join(self.test_dir, "demo")
        files = tracked_text(project)
        leftover = sorted(p for p, t in files.items() if PLACEHOLDER in t)
        self.assertEqual(leftover, [], f"{PLACEHOLDER} left in {leftover}")
        self.assertIn("*       @stub-user", files[".github/CODEOWNERS"])
        self.assertIn('Homepage = "https://github.com/stub-user/demo"', files["pyproject.toml"])
        self.assertIn("github/release-date/stub-user/demo", files["README.md"])
        self.assertIn("gist.githubusercontent.com/stub-user/", files["README.md"])
        self.assertIn("github: stub-user", files[".github/FUNDING.yml"])
        self.assertNotIn("username/repo", stdout)
        self.assertIn("is created and pushed next", stdout)

    def test_the_readme_ends_the_way_the_house_projects_do(self):
        # License last, no Acknowledgements crediting the author, the support
        # button with the login FUNDING names (djdarcy, 2026-10-24)
        self.create("--github")
        readme = tracked_text(os.path.join(self.test_dir, "demo"))["README.md"]
        headings = [l for l in readme.splitlines() if l.startswith("## ")]
        self.assertEqual(headings[-1], "## License")
        self.assertNotIn("Acknowledgements", readme)
        self.assertIn("https://www.buymeacoffee.com/stub-user", readme)
        self.assertNotIn("camo.githubusercontent.com", readme)
        self.assertRegex(readme, r"demo, Copyright \(C\) 20\d\d \S+")
        self.assertIn("Licensed under the MIT License (MIT) -- see [LICENSE](LICENSE).", readme)
        self.assertIn("See **[CONTRIBUTING.md](CONTRIBUTING.md)** for:", readme)

    def test_org_owns_the_urls_and_the_login_owns_codeowners_and_funding(self):
        self.create("--github", "--org", "someorg")
        files = tracked_text(os.path.join(self.test_dir, "demo"))
        self.assertIn("https://github.com/someorg/demo/compare/v0.1.0...HEAD", files["CHANGELOG.md"])
        self.assertIn("https://github.com/someorg/demo/issues/1", files["ROADMAP.md"])
        self.assertIn('repo-url = "https://github.com/someorg/demo"', files["pyproject.toml"])
        self.assertIn("@stub-user", files[".github/CODEOWNERS"])
        self.assertIn("github: stub-user", files[".github/FUNDING.yml"])

    def test_the_manifests_say_the_chosen_licence_and_the_topics(self):
        self.create("--no-push")
        files = tracked_text(os.path.join(self.test_dir, "demo"))
        py = files["pyproject.toml"]
        self.assertIn('license = {text = "MIT"}', py)
        self.assertIn('"License :: OSI Approved :: MIT License",', py)
        self.assertNotIn("GPL", py)
        self.assertIn('keywords = ["cli", "demo"]', py)
        readme = files["README.md"]
        self.assertIn("license-MIT-yellow", readme)
        self.assertIn("python-3.10+-blue", readme)
        self.assertNotIn("1.0.0", readme)
        self.assertNotIn("Feature 1", readme)
        self.assertIn("pip install demo", readme)

    def test_the_record_is_committed_with_its_author(self):
        self.create("--no-push")
        project = os.path.join(self.test_dir, "demo")
        status = subprocess.run(["git", "status", "--short"], cwd=project, capture_output=True, text=True).stdout
        self.assertEqual(status.strip(), "", f"tree not clean after create: {status}")
        tracked = subprocess.run(["git", "ls-files", ".repokit.json"], cwd=project,
                                 capture_output=True, text=True).stdout.strip()
        self.assertEqual(tracked, ".repokit.json")
        with open(os.path.join(project, ".repokit.json"), encoding="utf-8") as f:
            record = json.load(f)
        self.assertTrue(record.get("author", {}).get("name"), f"empty author: {record.get('author')}")

    def test_no_login_known_is_said_out_loud(self):
        stdout, stderr = self.create("--no-push")
        self.assertIn("No GitHub login known", stdout + stderr)
