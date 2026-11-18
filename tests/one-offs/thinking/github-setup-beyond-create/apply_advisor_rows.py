"""Apply the refactor-advisor's rows 1-3, 5-10 (2026-11-17) to the uncommitted
GitHub-setup diff, plus its note on the partial-state message. Every
replacement asserts its anchor occurs exactly once."""
from pathlib import Path


def sub(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, s.count(old), old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8")


# ---- github_setup.py: rows 6, 7, the partial-state message ----
G = "repokit/github_setup.py"
sub(G, 'BEFORE_PUSH = ("labels", "issues", "pin")  # the window between the repository\'s creation and its first push\n', "")
sub(G, '''    def _issues(self) -> Optional[list]:
        rc, out = self._gh("issue", "list", "--repo", self.repo, "--state", "all", "--limit", "100", "--json", "number,title")
        return json.loads(out or "[]") if rc == 0 else None
''', '''    def _numbered(self, kind: str) -> Optional[list]:
        """Every issue (kind 'issue') or pull request ('pr'), open or closed, as
        number and title; None when gh cannot list them."""
        rc, out = self._gh(kind, "list", "--repo", self.repo, "--state", "all", "--limit", "100", "--json", "number,title")
        return json.loads(out or "[]") if rc == 0 else None

    def _issues(self) -> Optional[list]:
        return self._numbered("issue")
''')
sub(G, '''        rc, out = self._gh("pr", "list", "--repo", self.repo, "--state", "all", "--limit", "100", "--json", "number,title")
        pulls = json.loads(out or "[]") if rc == 0 else []
        taken = sorted(existing + pulls, key=lambda i: i["number"])
        if taken:
            first = taken[0]
            kind = "pull request" if first in pulls else "issue"
            message = (f"issues: #{first['number']} is already {kind} {first['title']!r}, so Roadmap and "
                       "Quick Notes would not be #1 and #2")
''', '''        pulls = self._numbered("pr")
        if pulls is None:
            return ["issues: could not list the pull requests, so #1 and #2 cannot be checked; not created"]
        # Where each would land: the ones present keep their numbers, the
        # missing ones take the next numbers in order.
        everything = existing + pulls
        next_number = max([i["number"] for i in everything] or [0]) + 1
        landing = {}
        for title, _, _ in ISSUES:
            found = next((i["number"] for i in existing if i["title"] == title), None)
            landing[title] = found if found is not None else next_number
            next_number += found is None
        if [landing[t] for t, _, _ in ISSUES] != [1, 2]:
            ours = {t for t, _, _ in ISSUES}
            foreign = sorted((i for i in everything if i["title"] not in ours), key=lambda i: i["number"])
            if foreign:
                first = foreign[0]
                kind = "pull request" if first in pulls else "issue"
                held = f"#{first['number']} is already {kind} {first['title']!r}"
            else:
                held = ", ".join(f"{t} would be #{n}" for t, n in landing.items())
            message = f"issues: {held}, so Roadmap and Quick Notes would not be #1 and #2"
''')

# ---- github_create.py: rows 4 (the reader moves to config), 8 ----
C = "repokit/github_create.py"
sub(C, '''    gh = gh_command()
    if gh is None:
        return None
    rc, out = _run(gh + ["api", "user", "-q", ".login"], cwd)
    login = out.splitlines()[-1].strip() if rc == 0 and out else ""
    return login or None
''', '''    gh = gh_command()
    if gh is None:
        return None
    return _read_login(gh, cwd)[0]


def _read_login(gh: List[str], cwd: str) -> Tuple[Optional[str], str]:
    """(the account gh is logged into or None, gh's raw answer)."""
    rc, out = _run(gh + ["api", "user", "-q", ".login"], cwd)
    login = out.splitlines()[-1].strip() if rc == 0 and out else ""
    return login or None, out
''')
sub(C, '''    rc, out = _run(gh + ["api", "user", "-q", ".login"], repo_root)
    login = out.splitlines()[-1].strip() if rc == 0 and out else None
    if not organization and not login:''', '''    login, out = _read_login(gh, repo_root)
    if not organization and not login:''')
sub(C, '''def project_settings(repo_root: str) -> dict:
    """The project's own .repokit.json (name, extras, archetype, topics), or {}."""
    import json
    try:
        with open(os.path.join(repo_root, ".repokit.json"), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


''', "")

# ---- config.py + branch_utils.py: row 4, one record reader ----
sub("repokit/config.py", "from .directory_profiles import DirectoryProfileManager\n", '''from .directory_profiles import DirectoryProfileManager


def read_project_record(repo_root: str) -> Dict[str, Any]:
    """A project's own .repokit.json, read from its root (not the current
    directory, which is what ConfigManager reads), or {} when absent or
    unreadable."""
    try:
        with open(os.path.join(repo_root, ".repokit.json"), encoding="utf-8") as f:
            record = json.load(f)
    except (OSError, ValueError):
        return {}
    return record if isinstance(record, dict) else {}
''')
sub("repokit/branch_utils.py", '''    import json
    from .defaults import BRANCH_MODES
    try:
        with open(os.path.join(repo_path, ".repokit.json"), encoding="utf-8") as f:
            record = json.load(f)
    except (OSError, ValueError):
        return []
    mode = record.get("private_mode")''', '''    from .config import read_project_record
    from .defaults import BRANCH_MODES
    record = read_project_record(repo_path)
    mode = record.get("private_mode")''')

# ---- repo_manager.py: row 5, record the topics ----
sub("repokit/repo_manager.py", '''            "extras": list(self.config.get("extras") or []),
        }
''', '''            "extras": list(self.config.get("extras") or []),
        }
        if self.config.get("topics"):
            # read back by a later publish's GitHub setup (the topics step)
            repokit_config["topics"] = list(self.config["topics"])
''')

# ---- remote_integration.py: row 2, the update path decided here ----
R = "repokit/remote_integration.py"
sub(R, '''        existing_url: Optional[str] = None,
        after_create''', '''        update_existing: bool = False,
        after_create''')
sub(R, '''            existing_url: The remote already exists there (publish's update
                path): nothing is created and the remote is left as it is''', '''            update_existing: When the remote already names a GitHub
                repository, update it (publish's path): nothing is created,
                the remote is left as it is, the push and the hooks still run''')
sub(R, '''        if existing_url:
            self.logger.info(f"{existing_url} already exists: pushing and updating, nothing created")
            return self._finish(existing_url, remote_name, push_branches, include_branches,
                                exclude_branches, after_create, after_push)
''', '''        if update_existing and service.lower() == "github":
            from .github_create import github_repo_of
            existing_url = (self.repo_manager.run_git(["remote", "get-url", remote_name], check=False) or "").strip()
            if github_repo_of(existing_url):
                self.logger.info(f"{existing_url} already exists: pushing and updating, nothing created")
                return self._finish(existing_url, remote_name, push_branches, include_branches,
                                    exclude_branches, after_create, after_push)
''')

# ---- cli.py: rows 1, 3, 9, 10 ----
L = "repokit/cli.py"
sub(L, '''    create_parser.add_argument(
        "--github-setup",
        dest="github_setup",
        action="append",
        metavar="STEP[,STEP...]",
        help="With --github or --publish-to github, what to set up on the new repository: labels, issues (the Roadmap and "
             "Quick Notes as #1 and #2, before the first push), pin, discussions, topics, "
             "pypi-environment, traffic (prints ghtraf's commands), or all. Off unless named here "
             "or in the global config's `github_setup` list."
    )
    create_parser.add_argument(
        "--topics",
        metavar="TOPIC[,TOPIC...]",
        help="Repository topics for --github-setup topics"
    )
    _add_github_setup_args(create_parser, named=False)
''', '''    _add_github_setup_args(create_parser)
''')
sub(L, '''def _add_github_setup_args(parser, named: bool = True) -> None:
    """--github-setup / --topics (when ``named``) and --no-github-setup."""
    if named:
        parser.add_argument(
            "--github-setup", dest="github_setup", action="append", metavar="STEP[,STEP...]",
            help="With --publish-to github, what to set up on the repository: labels, issues (the Roadmap "
                 "and Quick Notes as #1 and #2), pin, discussions, topics, pypi-environment, traffic, or "
                 "all. Default: the global config's `github_setup` list."
        )
        parser.add_argument("--topics", metavar="TOPIC[,TOPIC...]", help="Repository topics for --github-setup topics")
    parser.add_argument(''', '''def _add_github_setup_args(parser) -> None:
    """--github-setup, --topics and --no-github-setup (create, adopt, publish)."""
    parser.add_argument(
        "--github-setup", dest="github_setup", action="append", metavar="STEP[,STEP...]",
        help="With --github or --publish-to github, what to set up on the repository: labels, issues "
             "(the Roadmap and Quick Notes as #1 and #2, before the first push), pin, discussions, "
             "topics, pypi-environment, traffic (prints ghtraf's commands), or all. Default: the "
             "global config's `github_setup` list; none when it names none."
    )
    parser.add_argument("--topics", metavar="TOPIC[,TOPIC...]", help="Repository topics for --github-setup topics")
    parser.add_argument(''')
sub(L, '''    from . import github_setup
    from .github_create import project_settings, publish_hooks
    try:''', '''    from . import github_setup
    from .config import read_project_record
    from .github_create import publish_hooks
    try:''')
sub(L, '''    facts = project_settings(repo_root)''', '''    facts = read_project_record(repo_root)''')
sub(L, '''def _print_setup(report: List[str]) -> None:
    for line in report:
        print(f"GitHub: {line}")
''', '''def _publish_with_setup(args, config: Dict[str, Any], repo_root: str, service: str,
                        remote_integration, **remote) -> bool:
    """setup_remote_repository with the GitHub setup's hooks, the setup's
    report printed afterwards. False on a refused setup or a failed publish."""
    report: List[str] = []
    hooks, problem = _publish_setup(args, config, repo_root, service, report)
    if problem:
        logger.error(problem)
        return False
    ok = remote_integration.setup_remote_repository(service=service, **remote, **hooks)
    for line in report:
        print(f"GitHub: {line}")
    return ok
''')
# create handler
sub(L, '''                setup_report: list = []
                hooks, problem = _publish_setup(args, repo_manager.config, repo_manager.repo_root,
                                                args.publish_to, setup_report)
                if problem:
                    logger.error(problem)
                    return 1
                publish_success = remote_integration.setup_remote_repository(
                    service=args.publish_to,
                    remote_name=args.remote_name,
                    private=args.private_repo,
                    push_branches=not args.no_push,
                    organization=args.organization,
                    token_command=args.token_command,
                    **hooks,
                )
                _print_setup(setup_report)
''', '''                publish_success = _publish_with_setup(
                    args, repo_manager.config, repo_manager.repo_root, args.publish_to, remote_integration,
                    remote_name=args.remote_name,
                    private=args.private_repo,
                    push_branches=not args.no_push,
                    organization=args.organization,
                    token_command=args.token_command,
                )
''')
# adopt handler
sub(L, '''                setup_report: list = []
                hooks, problem = _publish_setup(args, adopt_config, dir_path, publish_to, setup_report)
                if problem:
                    logger.error(problem)
                    return 1
                publish_success = remote_integration.setup_remote_repository(
                    service=publish_to,
                    remote_name=getattr(args, 'remote_name', None) or adopt_config.get('remote_name', 'origin'),
                    private=getattr(args, 'private_repo', None) or adopt_config.get('private_repo', False),
                    push_branches=not getattr(args, 'no_push', False),
                    organization=organization,
                    token_command=token_cmd,
                    **hooks,
                )
                _print_setup(setup_report)
''', '''                publish_success = _publish_with_setup(
                    args, adopt_config, dir_path, publish_to, remote_integration,
                    remote_name=getattr(args, 'remote_name', None) or adopt_config.get('remote_name', 'origin'),
                    private=getattr(args, 'private_repo', None) or adopt_config.get('private_repo', False),
                    push_branches=not getattr(args, 'no_push', False),
                    organization=organization,
                    token_command=token_cmd,
                )
''')
# publish handler
sub(L, '''            setup_report: list = []
            hooks, problem = _publish_setup(args, config, repo_path, args.publish_to, setup_report)
            if problem:
                logger.error(problem)
                return 1
            # Already on GitHub (origin names an existing repository): the
            # update path -- nothing created, the push and the setup still run.
            existing_url = None
            if args.publish_to == "github":
                from .github_create import _run, github_repo_of
                rc, url = _run(["git", "remote", "get-url", args.remote_name], repo_path)
                if rc == 0 and github_repo_of(url):
                    existing_url = url.strip()

            publish_success = remote_integration.setup_remote_repository(
                service=args.publish_to,
                remote_name=args.remote_name,''', '''            # update_existing: a project already on GitHub is pushed and set
            # up, nothing created (publish only; adopt still creates)
            publish_success = _publish_with_setup(
                args, config, repo_path, args.publish_to, remote_integration,
                update_existing=True,
                remote_name=args.remote_name,''')
sub(L, '''                exclude_branches=getattr(args, 'exclude_branches', None),
                existing_url=existing_url,
                **hooks,
            )
            _print_setup(setup_report)
''', '''                exclude_branches=getattr(args, 'exclude_branches', None),
            )
''')
# row 9: unknown steps refused before anything is written (create)
sub(L, '''        from .repo_manager import private_mode_for
        _mode, problem = private_mode_for(config)
        if problem:
            logger.error(problem)
            return 1
''', '''        from .repo_manager import private_mode_for
        _mode, problem = private_mode_for(config)
        if problem:
            logger.error(problem)
            return 1
        # Unknown --github-setup steps, likewise
        from .github_setup import setup_names
        try:
            setup_names(config.get("github_setup"))
        except ValueError as e:
            logger.error(str(e))
            return 1
''')
# row 10
sub(L, '''        cli_config["topics"] = [t.strip() for t in args.topics.split(",") if t.strip()]''', '''        from .layers import parse_languages as _split_topics
        cli_config["topics"] = _split_topics(args.topics)''')
print("applied")
