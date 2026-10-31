#!/usr/bin/env python3
"""
The nested private repository: private/ as its own git repository.

A project's private notes live in private/, which the project's .gitignore
excludes, and private/ is itself a git repository with its own history. Nothing
private can reach the project's branches, so no hook has to guard them.

Ported from dazzlecmd's `dz private-init` (dazzletools/private-init/
private_init.py, cmd_init and its constants) so that git-repokit creates the
vault itself; dazzlecmd may later call this module instead of keeping its own.

(Named vault.py, not private_repo.py: the private-branch model's guards treat
any path containing "private" as private content and would refuse or cut it.)
"""

import os
import subprocess
import sys
from typing import List, Optional, Tuple

# The vault's standard folders (private_init.PRIVATE_STRUCTURE)
PRIVATE_STRUCTURE = [
    "claude",
    "claude/commits",
    "claude/issues",
    "convos",
    "docs",
    "logs",
    "notes",
    "revisions",
]
# convos/, revisions/ and logs/ were project-root folders until 0.10.0, held
# out of public history only by ignore rules and the pre-commit guard; inside
# the vault they cannot reach a public remote at all (djdarcy, 2026-10-31).
# logs/ is run output, so the vault ignores it (PRIVATE_GITIGNORE_SECTIONS).

# What the vault ignores (private_init.PRIVATE_GITIGNORE_SECTIONS)
PRIVATE_GITIGNORE_SECTIONS = [
    ("Python", ["__pycache__/", "*.py[cod]", "*.so"]),
    ("Editors", ["*.swp", "*~", "*.*~", ".*.swp", ".vscode/"]),
    ("OS", [".DS_Store", "Thumbs.db", "desktop.ini"]),
    ("Temp files", ["*.tmp", "*.bak"]),
    ("Agent working state -- written by tools, never versioned", [".gauntlet/"]),
    ("Run logs -- program output, kept on disk and never versioned", ["logs/"]),
]

# What the parent project ignores besides private/ itself
# (private_init.PARENT_GITIGNORE_SECTIONS)
PARENT_GITIGNORE_SECTIONS = [
    ("Private repository -- its own git repository, never part of this one", ["/private/"]),
    ("Agent working state -- written by tools, never versioned", ["CLAUDE.local.md"]),
]


def render_gitignore(sections) -> str:
    """Render (title, patterns) pairs as .gitignore text."""
    return "\n".join("# " + title + "\n" + "\n".join(patterns) + "\n" for title, patterns in sections)


def _git(args: List[str], cwd: str) -> Tuple[int, str, str]:
    result = subprocess.run(
        ["git"] + args, cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def ensure_parent_ignores(repo_root: str) -> List[str]:
    """Append the parent .gitignore lines that are missing; return what was added."""
    path = os.path.join(repo_root, ".gitignore")
    existing = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            existing = f.read()
    present = {line.strip() for line in existing.splitlines()}

    missing = [(title, [p for p in patterns if p not in present])
               for title, patterns in PARENT_GITIGNORE_SECTIONS]
    missing = [(title, patterns) for title, patterns in missing if patterns]
    if not missing:
        return []

    with open(path, "a", encoding="utf-8") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        f.write("\n" + render_gitignore(missing))
    return [p for _title, patterns in missing for p in patterns]


SKELETON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "vault")
VAULT_INIT_MODES = ("prompt-file", "none")


def write_skeleton(private_path: str, project_name: str) -> List[str]:
    """Lay the vault skeleton (0.9.4): the vault's CLAUDE.md with its
    conventions and the three-session note, the map stub, the oracle's index
    stubs, the two boards. Files that exist are kept. Returns what was written."""
    import datetime
    import string
    values = {"project_name": project_name, "date": datetime.date.today().isoformat()}
    written = []
    for root, _dirs, files in os.walk(SKELETON):
        for name in files:
            src = os.path.join(root, name)
            rel = os.path.relpath(src, SKELETON).replace("\\", "/")
            if rel == "claude/_maps/MOC-project.md":
                rel = f"claude/_maps/MOC-{project_name}.md"
            dest = os.path.join(private_path, rel)
            if os.path.exists(dest):
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(src, encoding="utf-8") as f:
                text = string.Template(f.read()).safe_substitute(values)
            with open(dest, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            written.append(rel)
    return sorted(written)


def bootstrap_prompt_text(repo_root: str, project_name: str) -> str:
    """What the oracle session is asked to do first: build the map and the
    index from the project and the vault (the half of /obsidian-init a model
    has to do, because it reads the project)."""
    top = sorted(n for n in os.listdir(repo_root) if not n.startswith(".git") and n != "private")
    docs = sorted(os.path.relpath(os.path.join(r, n), os.path.join(repo_root, "private")).replace("\\", "/")
                  for r, _d, fs in os.walk(os.path.join(repo_root, "private", "claude")) for n in fs
                  if n.endswith(".md") and ".git" not in r)
    return "\n".join([
        f"# Bootstrap the vault of {project_name}",
        "",
        f"You are the oracle session for `{project_name}`. git-repokit laid the vault's skeleton; "
        "fill the parts that need someone who has read the project:",
        "",
        f"1. Read the project's README, CHANGELOG and top-level layout ({', '.join(top)}).",
        f"2. Fill `claude/_maps/MOC-{project_name}.md` with the project's arcs (one so far: its creation) "
        "and link every document under `claude/`.",
        "3. Fill `claude/_oracle/manifest.md` with one row per document, and `concepts.md` with any term "
        "the project uses in its own sense.",
        "4. Run `python scripts/repokit-common/generate-backlinks.py private/claude --validate` from the project root.",
        "5. Commit the vault by named path; never push it.",
        "",
        "Then run `/obsidian-update` and `/obsidian-loop` as usual.",
        "",
        "## The vault today",
        "",
        *[f"- `{d}`" for d in docs],
        "",
    ])


def bootstrap(repo_root: str, project_name: str, mode: str = "prompt-file") -> Optional[str]:
    """The vault's AI door (0.9.4). `prompt-file` (the default) writes the
    oracle's first prompt through ailib's prompt-file transport to
    private/claude/_oracle/ and returns its path; `none` writes nothing. The
    tool never commits what it writes here: the oracle session reviews it."""
    if mode not in VAULT_INIT_MODES:
        raise ValueError(f"unknown vault_init {mode!r}; known: {', '.join(VAULT_INIT_MODES)}")
    if mode == "none":
        return None
    from ._vendor.ailib.types import Request, Spec
    from ._vendor.ailib.backend import build
    oracle = os.path.join(repo_root, "private", "claude", "_oracle")
    backend = build(Spec(transport="prompt-file", name="vault-bootstrap", endpoint=oracle))
    response = backend.invoke(Request(prompt=bootstrap_prompt_text(repo_root, project_name)))
    if response.status != "deferred" or not response.artifact:
        return None
    final = os.path.join(oracle, "bootstrap-prompt.md")
    os.replace(response.artifact, final)
    return final


def init_private_repo(repo_root: str, project_name: str, logger=None) -> bool:
    """Create private/ as its own git repository with a first commit.

    Refuses an existing private repository (never re-initialises). Signing is
    turned off inside the vault, as dz private-init does: it is local-only.
    Returns True when the vault exists afterwards.
    """
    log = logger.info if logger else (lambda msg: None)
    private_path = os.path.join(repo_root, "private")

    added = ensure_parent_ignores(repo_root)
    if added:
        log(f"Parent .gitignore now ignores: {', '.join(added)}")

    if os.path.exists(os.path.join(private_path, ".git")):
        log("private/ is already a git repository; left as it is")
        return True

    existing_content = os.path.isdir(private_path) and os.listdir(private_path)
    os.makedirs(private_path, exist_ok=True)

    rc, _, err = _git(["init", "-q"], private_path)
    if rc != 0:
        if logger:
            logger.error(f"git init failed in private/: {err}")
        return False
    _git(["config", "commit.gpgsign", "false"], private_path)
    _git(["config", "tag.gpgsign", "false"], private_path)

    gitignore = os.path.join(private_path, ".gitignore")
    if not os.path.exists(gitignore):
        with open(gitignore, "w", encoding="utf-8") as f:
            f.write(render_gitignore(PRIVATE_GITIGNORE_SECTIONS))

    if not existing_content:
        # The skeleton /obsidian-init laid by hand (0.9.4), before the
        # folders' gitkeeps so a folder with a file needs none.
        write_skeleton(private_path, project_name)
        for sub in PRIVATE_STRUCTURE:
            folder = os.path.join(private_path, sub)
            os.makedirs(folder, exist_ok=True)
            if not os.listdir(folder):
                open(os.path.join(folder, ".gitkeep"), "w").close()

    _git(["add", "-A"], private_path)
    message = (f"init: adopt existing private content for {project_name}" if existing_content
               else f"init: private workspace for {project_name}")
    rc, _, err = _git(["commit", "-q", "-m", message], private_path)
    if rc != 0 and logger:
        logger.warning(f"private/: first commit failed: {err}")
    log("private/ is its own git repository")
    return True


def link_private(worktree_path: str, private_path: str) -> Optional[str]:
    """Give a worktree a link to the real vault: <worktree>/private -> private_path.

    A directory junction on Windows (no administrator rights needed, no shell),
    a symlink elsewhere. Returns None on success, or the reason it failed.
    Never replaces something that is already there.
    """
    link = os.path.join(worktree_path, "private")
    if os.path.lexists(link):
        return f"{link} already exists"
    target = os.path.abspath(private_path)
    try:
        if sys.platform == "win32":
            try:
                import _winapi
                _winapi.CreateJunction(target, link)
            except (ImportError, AttributeError, OSError):
                # Fallback: PowerShell, never `cmd /c mklink` (it fails silently from bash)
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     f"New-Item -ItemType Junction -Path '{link}' -Target '{target}' | Out-Null"],
                    capture_output=True, text=True,
                )
                if result.returncode != 0:
                    return result.stderr.strip() or "PowerShell could not create the junction"
        else:
            os.symlink(target, link, target_is_directory=True)
    except OSError as e:
        return str(e)
    return None
