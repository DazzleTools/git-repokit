"""The GitHub half of a new project (0.9.3): what `/github-issues-setup` and
`/create-project` did by hand after the repository existed, behind the
`github_setup` setting (a list in the config, or `--github-setup a,b|all`).

The order is the skill's own and it matters: the labels and the two
evergreen issues go in BETWEEN `gh repo create` and the first push. The first
push lets Dependabot (the `dependabot` extra) open a pull request, which would
take issue number 1; the Roadmap and the Quick Notes must be #1 and #2
(djdarcy, 2026-10-22). After the push: discussions, topics, the `pypi`
environment for a preset that publishes there. Every step is idempotent: a
second run creates nothing that exists. ghtraf creates gists and needs a
secret only the person can set, so its commands are printed, not run.

All gh calls name the repository (`--repo OWNER/NAME`), so nothing depends on
the working directory; `run` is injectable so the tests can answer for gh.
Design: 2026-10-22__22-06-57__dev-workflow-process__0-9-x-parity-with-the-old-route.md (row 0.9.3).
"""
import json
import os
import re
import string
import tempfile
from pathlib import Path
from typing import Callable, List, Optional, Tuple

STEPS = ("labels", "issues", "pin", "discussions", "topics", "pypi-environment", "traffic")

# /github-issues-setup, Step 1 (names, colors, descriptions as the skill has them)
LABELS = [
    ("pinned", "d4c5f9", "Permanently open issue"),
    ("evergreen", "2ea44f", "Never close -- living document updated over time"),
    ("roadmap", "0075ca", "Project roadmap"),
    ("scratchpad", "f9d0c4", "Quick notes and scratch space"),
    ("architecture", "bfd4f2", "Structural decisions"),
    ("epic", "5319e7", "Large multi-phase initiative"),
    ("ideas", "c5def5", "Exploratory ideas"),
    ("CurrentTask", "0e8a16", "Currently being worked on"),
    ("NextTask", "e6b800", "Next item to pick up"),
]
# Labels a created project's own files name (its issue templates' `labels:`,
# dependabot.yml's `labels:`), with GitHub's and Dependabot's usual colors.
# A repository created by gh has no default labels, so without these an issue
# filed from the bug template, or a Dependabot pull request, would ask for a
# label that does not exist (0.9.6; the live golden had them from the template).
REFERENCED = {
    "bug": ("d73a4a", "Something isn't working"),
    "enhancement": ("a2eeef", "New feature or request"),
    "documentation": ("0075ca", "Improvements or additions to documentation"),
    "dependencies": ("0366d6", "Pull requests that update a dependency file"),
    "github-actions": ("000000", "Pull requests that update GitHub Actions"),
    "pip": ("2b67c6", "Pull requests that update Python dependencies"),
}


def referenced_labels(repo_root: str) -> List[str]:
    """Every label the project's issue templates and dependabot.yml name, in
    the order first seen."""
    names: List[str] = []
    gh_dir = Path(repo_root, ".github")
    for path in sorted((gh_dir / "ISSUE_TEMPLATE").glob("*.md")) if (gh_dir / "ISSUE_TEMPLATE").is_dir() else []:
        m = re.search(r"^labels:\s*(.+)$", path.read_text(encoding="utf-8"), re.M)
        if m:
            names += [n.strip().strip("'\"") for n in m.group(1).split(",")]
    dependabot = gh_dir / "dependabot.yml"
    if dependabot.is_file():
        names += re.findall(r'^\s*-\s*"?([A-Za-z0-9_.-]+)"?\s*$',
                            "\n".join(_labels_blocks(dependabot.read_text(encoding="utf-8"))), re.M)
    seen: List[str] = []
    for n in names:
        if n and n not in seen:
            seen.append(n)
    return seen


def _labels_blocks(text: str) -> List[str]:
    """The list items under each `labels:` key of a YAML file, as lines."""
    out, lines = [], text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == "labels:":
            indent = len(line) - len(line.lstrip())
            for nxt in lines[i + 1:]:
                if nxt.strip().startswith("-") and len(nxt) - len(nxt.lstrip()) >= indent:
                    out.append(nxt)
                else:
                    break
    return out


ISSUES = [  # title, labels, template
    ("Roadmap", "pinned,roadmap,evergreen", "roadmap.md.template"),
    ("Quick Notes -- Bugs, Features, Ideas", "pinned,scratchpad,evergreen", "notes.md.template"),
]
TEMPLATES = Path(__file__).resolve().parent / "templates" / "github" / "issues"
PUBLISHES_TO_PYPI = ("python/pypi",)

Runner = Callable[[List[str]], Tuple[int, str]]


def setup_names(requested) -> List[str]:
    """The steps to run, in STEPS order; `all` means every one; unknown refused."""
    wanted = list(requested or [])
    if "all" in wanted:
        return list(STEPS)
    unknown = [w for w in wanted if w not in STEPS]
    if unknown:
        raise ValueError(f"unknown github-setup steps {', '.join(unknown)}; known: {', '.join(STEPS)}, all")
    return [s for s in STEPS if s in wanted]


def render_issue(template: str, project_name: str) -> str:
    text = (TEMPLATES / template).read_text(encoding="utf-8")
    return string.Template(text).safe_substitute(project_name=project_name)


class GhSetup:
    """The steps for one repository. Each method returns report lines."""

    def __init__(self, gh: List[str], repo: str, run: Runner):
        self.gh, self.repo, self.run = gh, repo, run

    def _gh(self, *args: str) -> Tuple[int, str]:
        return self.run(self.gh + list(args))

    # --- before the first push ------------------------------------------------

    def labels(self, referenced: Optional[List[str]] = None) -> List[str]:
        """The nine house labels, then any label the project's own files name
        (referenced_labels) that the repository lacks."""
        rc, out = self._gh("label", "list", "--repo", self.repo, "--limit", "200", "--json", "name")
        if rc != 0:
            return [f"labels: could not list them: {out}"]
        have = {l["name"] for l in json.loads(out or "[]")}
        wanted = list(LABELS) + [(n, *REFERENCED.get(n, ("ededed", ""))) for n in (referenced or [])
                                 if n not in {l[0] for l in LABELS}]
        made = []
        for name, color, desc in wanted:
            if name in have:
                continue
            cmd = ["label", "create", name, "--repo", self.repo, "--color", color]
            if desc:
                cmd += ["--description", desc]
            rc, out = self._gh(*cmd)
            if rc != 0:
                return [f"labels: creating {name} failed: {out}"]
            made.append(name)
            have.add(name)
        return [f"labels: created {', '.join(made)}" if made else "labels: all already there"]

    def _issues(self) -> Optional[list]:
        rc, out = self._gh("issue", "list", "--repo", self.repo, "--state", "all", "--limit", "100", "--json", "number,title")
        return json.loads(out or "[]") if rc == 0 else None

    def issues(self, project_name: str, drafts_dir: Optional[str] = None) -> List[str]:
        existing = self._issues()
        if existing is None:
            return ["issues: could not list them"]
        titles = {i["title"] for i in existing}
        if all(t in titles for t, _, _ in ISSUES):
            return ["issues: Roadmap and Quick Notes already there"]
        if existing:
            # They would not be #1 and #2: refuse rather than take later numbers.
            return [f"issues: the repository already has {len(existing)} issue(s); Roadmap and Quick Notes "
                    "were not created, because they would not be #1 and #2"]
        report = []
        for title, labels, template in ISSUES:
            body = render_issue(template, project_name)
            if drafts_dir and os.path.isdir(drafts_dir):
                Path(drafts_dir, "issue_" + template.replace(".md.template", ".md")).write_text(body, encoding="utf-8")
            with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
                f.write(body)
                body_file = f.name
            try:
                rc, out = self._gh("issue", "create", "--repo", self.repo, "--title", title,
                                   "--label", labels, "--body-file", body_file)
            finally:
                os.unlink(body_file)
            if rc != 0:
                return report + [f"issues: creating {title!r} failed: {out}"]
            m = re.search(r"/issues/(\d+)", out)
            report.append(f"issues: #{m.group(1) if m else '?'} {title}")
        return report

    def pin(self) -> List[str]:
        existing = self._issues() or []
        owner, name = self.repo.split("/", 1)
        q = ('query { repository(owner: "%s", name: "%s") { pinnedIssues(first: 10) '
             '{ nodes { issue { number } } } } }') % (owner, name)
        rc, out = self._gh("api", "graphql", "-f", f"query={q}")
        pinned = set()
        if rc == 0:
            try:
                nodes = json.loads(out)["data"]["repository"]["pinnedIssues"]["nodes"]
                pinned = {n["issue"]["number"] for n in nodes}
            except (ValueError, KeyError, TypeError):
                pinned = set()
        report = []
        for title, _, _ in ISSUES:
            number = next((i["number"] for i in existing if i["title"] == title), None)
            if number is None:
                report.append(f"pin: {title!r} not found")
                continue
            if number in pinned:
                report.append(f"pin: #{number} already pinned")
                continue
            rc, node = self._gh("issue", "view", str(number), "--repo", self.repo, "--json", "id", "-q", ".id")
            if rc != 0 or not node.strip():
                report.append(f"pin: could not read #{number}'s id: {node}")
                continue
            m = 'mutation { pinIssue(input: {issueId: "%s"}) { issue { number } } }' % node.strip()
            rc, out = self._gh("api", "graphql", "-f", f"query={m}")
            report.append(f"pin: #{number} pinned" if rc == 0 else f"pin: #{number} failed: {out}")
        return report

    # --- after the push ---------------------------------------------------------

    def discussions(self) -> List[str]:
        rc, out = self._gh("repo", "edit", self.repo, "--enable-discussions")
        return ["discussions: on" if rc == 0 else f"discussions: failed: {out}"]

    def topics(self, topics: List[str]) -> List[str]:
        if not topics:
            return ["topics: none named (--topics a,b)"]
        args = ["repo", "edit", self.repo]
        for t in topics:
            args += ["--add-topic", t]
        rc, out = self._gh(*args)
        return [f"topics: {', '.join(topics)}" if rc == 0 else f"topics: failed: {out}"]

    def pypi_environment(self, archetype: Optional[str]) -> List[str]:
        if archetype not in PUBLISHES_TO_PYPI:
            return []
        rc, out = self._gh("api", f"repos/{self.repo}/environments/pypi", "-X", "PUT")
        return ["pypi-environment: created (register the trusted publisher on PyPI: workflow release.yml, environment pypi)"
                if rc == 0 else f"pypi-environment: failed: {out}"]

    def traffic(self, project_name: str) -> List[str]:
        return ["traffic: ghtraf creates gists and needs a secret only you can set, so it is not run here.",
                f"  From the project: `ghtraf create --help` (the old route used --configure --ci-workflows "
                f"--non-interactive), then `gh secret set TRAFFIC_GIST_TOKEN --repo {self.repo}`"]


def reminders(repo: str, extras: List[str]) -> List[str]:
    """What has no API: said once, after the setup."""
    out = [f"CI: watch the first run with `gh run list -R {repo} --limit 5`"]
    if "funding" in extras:
        out.append("Sponsorships: Settings > General > Features > Sponsorships (FUNDING.yml is in .github/)")
    out.append("Pages, if the project serves docs/: Settings > Pages > main, /docs")
    return out
