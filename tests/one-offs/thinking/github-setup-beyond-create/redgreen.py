"""Red-green audit for the GitHub setup beyond create (2026-11-17).

Each mutant reverts one behaviour (never the API), runs the tests that should
catch it, and restores the file. Run from the repository root:
    python tests/one-offs/thinking/github-setup-beyond-create/redgreen.py
Every test touches only fakes, stubs and tmp paths (see the test module's
docstring), so a mutant cannot reach GitHub.
"""
import subprocess
import sys
from pathlib import Path

T = "tests/test_github_setup_publish.py"
MUTANTS = [
    ("M1 pull requests not counted", "repokit/github_setup.py",
     "everything = existing + pulls", "everything = existing + []",
     [f"{T}::test_a_pull_request_at_1_stops_the_issues_by_default"]),
    ("M2 window hook never called", "repokit/remote_integration.py",
     "if after_create and not after_create(remote_url):", "if False:",
     [f"{T}::test_an_abort_in_the_window_pushes_nothing", f"{T}::test_the_window_comes_before_the_push_and_after_push_after_it"]),
    ("M3 after-push hook never called", "repokit/remote_integration.py",
     "        if after_push:\n            after_push(remote_url)", "        pass",
     [f"{T}::test_the_window_comes_before_the_push_and_after_push_after_it"]),
    ("M4 update path ignored in the token route", "repokit/remote_integration.py",
     'if update_existing and service.lower() == "github":', "if False:",
     [f"{T}::test_the_update_path_creates_nothing_and_keeps_the_remote"]),
    ("M5 publish never detects the existing repository", "repokit/cli.py",
     "                update_existing=True,\n", "",
     [f"{T}::TestPublishUpdatePath::test_publish_on_an_existing_repository_pushes_and_sets_up_in_order"]),
    ("M6 agents are asked", "repokit/github_setup.py",
     'or os.environ.get("CI") or os.environ.get("CLAUDECODE"):', ":",
     [f"{T}::test_no_question_under_an_agent_ci_or_the_switch"]),
    ("M7 the conflict's answer ignored (always skip)", "repokit/github_setup.py",
     'if choice != "continue":', "if True:",
     [f"{T}::test_continue_at_the_conflict_takes_the_later_numbers"]),
    ("M8 abort ignored", "repokit/github_setup.py",
     'if choice == "abort":\n                raise SetupAborted(message)', 'if False:\n                raise SetupAborted(message)',
     [f"{T}::test_abort_at_the_conflict_stops_the_rest"]),
    ("M9 existing title re-created", "repokit/github_setup.py",
     "            if title in titles:\n                continue\n", "",
     [f"{T}::test_continue_creates_only_the_missing_one"]),
    ("M10 gitlab + --github-setup not refused", "repokit/cli.py",
     'return {}, "--github-setup works with --publish-to github only"', "return {}, None",
     [f"{T}::TestPublishUpdatePath::test_gitlab_with_github_setup_is_refused_before_anything"]),
    ("M11 --no-github-setup ignored", "repokit/cli.py",
     '    if getattr(args, "no_github_setup", False):\n        cli_config["github_setup"] = []\n', "",
     [f"{T}::TestPublishUpdatePath::test_no_github_setup_runs_nothing"]),
    ("M12 gh not ready still runs the setup", "repokit/github_create.py",
     "        if problem:\n            report.append(f\"setup not run:", "        if False:\n            report.append(f\"setup not run:",
     [f"{T}::test_gh_not_ready_skips_the_setup_and_the_publish_goes_on"]),
    ("M14 the landing check ignored (partial state asks or misnumbers)", "repokit/github_setup.py",
     "if [landing[t] for t, _, _ in ISSUES] != [1, 2]:", "if everything:",
     [f"{T}::test_roadmap_at_1_alone_gets_quick_notes_at_2_without_a_question"]),
    ("M15 unreadable pull requests treated as none", "repokit/github_setup.py",
     "        if pulls is None:\n            return", "        if pulls is None:\n            pulls = []\n        if False:\n            return",
     [f"{T}::test_pull_requests_unreadable_creates_nothing"]),
    ("M16 unknown steps refused only after writing", "repokit/cli.py",
     '            setup_names(config.get("github_setup"))\n', "            pass\n",
     [f"{T}::TestCreateRecordsAndRefuses::test_unknown_step_refused_before_anything_is_written"]),
    ("M17 topics not recorded", "repokit/repo_manager.py",
     'repokit_config["topics"] = list(self.config["topics"])', "pass",
     [f"{T}::TestCreateRecordsAndRefuses::test_topics_are_recorded_for_a_later_publish"]),
    ("M18 the update path taken without being asked", "repokit/remote_integration.py",
     'if update_existing and service.lower() == "github":', 'if service.lower() == "github":',
     [f"{T}::test_without_update_existing_an_origin_on_github_still_creates"]),
    ("M13 project's extras not read", "repokit/cli.py",
     'for key in ("project_name", "extras", "archetype"):', "for key in ():",
     [f"{T}::TestPublishUpdatePath::test_publish_on_an_existing_repository_pushes_and_sets_up_in_order"]),
]


def run(tests):
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *tests],
                          capture_output=True, text=True).returncode


def main():
    rows = []
    for name, path, old, new, tests in MUTANTS:
        p = Path(path)
        original = p.read_text(encoding="utf-8")
        if original.count(old) != 1:
            rows.append((name, f"ANCHOR x{original.count(old)}"))
            continue
        try:
            p.write_text(original.replace(old, new, 1), encoding="utf-8")
            red = run(tests) != 0
        finally:
            p.write_text(original, encoding="utf-8")
        green = run(tests) == 0
        rows.append((name, "RED->GREEN" if red and green else f"red={red} green={green}"))
    for name, verdict in rows:
        print(f"{verdict:12}  {name}")
    return 0 if all(v == "RED->GREEN" for _, v in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
