"""Measure: the shape of the Claude Code plugin checkouts on this machine.

Before the js-ts/claude-plugin preset is written (Phase 3 slice 4), read each
plugin-shaped checkout under C:/code/claude-projects: what sits at the
repository root, what sits in the plugin folder, where the manifests are and
what fields they carry, where tests and READMEs live, and how the version is
kept. Read-only; writes results.md beside this script.

    python measure.py [--root C:/code/claude-projects]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKIP = {"node_modules", ".git", "private", "__pycache__", ".pytest_cache", "dist", ".vscode"}


def listing(d: Path, depth: int = 1) -> list[str]:
    out = []
    for p in sorted(d.iterdir()):
        if p.name in SKIP:
            continue
        out.append(p.name + ("/" if p.is_dir() else ""))
    return out


def read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as e:  # noqa: BLE001
        return {"_error": str(e)[:80]}


def describe(repo: Path) -> dict:
    d = {"repo": repo.name, "root": listing(repo)}
    root_cp = repo / ".claude-plugin"
    d["root .claude-plugin"] = listing(root_cp) if root_cp.is_dir() else []
    mk = root_cp / "marketplace.json"
    if mk.exists():
        m = read_json(mk)
        d["marketplace"] = {"name": m.get("name"), "plugins": [(p.get("name"), p.get("source")) for p in m.get("plugins", [])],
                            "version": (m.get("metadata") or {}).get("version")}
    plugins = []
    for cand in sorted(repo.iterdir()):
        if cand.is_dir() and cand.name not in SKIP and (cand / ".claude-plugin" / "plugin.json").exists():
            pj = read_json(cand / ".claude-plugin" / "plugin.json")
            plugins.append({
                "folder": cand.name,
                "plugin.json keys": sorted(pj.keys()) if isinstance(pj, dict) else pj,
                "version": pj.get("version") if isinstance(pj, dict) else None,
                "listing": listing(cand),
                "hooks": listing(cand / "hooks") if (cand / "hooks").is_dir() else [],
                "tsconfig": (cand / "tsconfig.json").exists(),
                "package.json": (cand / "package.json").exists(),
                "tests": listing(cand / "tests")[:6] if (cand / "tests").is_dir() else [],
                "README": (cand / "README.md").exists(),
            })
    if (root_cp / "plugin.json").exists():
        pj = read_json(root_cp / "plugin.json")
        plugins.append({"folder": ".", "plugin.json keys": sorted(pj.keys()) if isinstance(pj, dict) else pj,
                        "version": pj.get("version") if isinstance(pj, dict) else None,
                        "hooks": listing(repo / "hooks") if (repo / "hooks").is_dir() else [],
                        "tsconfig": (repo / "tsconfig.json").exists(), "package.json": (repo / "package.json").exists(),
                        "tests": listing(repo / "tests")[:6] if (repo / "tests").is_dir() else [], "README": (repo / "README.md").exists()})
    d["plugins"] = plugins
    toml = repo / ".repokit-common.toml"
    pyproj = repo / "pyproject.toml"
    settings = toml.read_text(encoding="utf-8") if toml.exists() else (pyproj.read_text(encoding="utf-8") if pyproj.exists() else "")
    d["version-source"] = next((ln.strip() for ln in settings.splitlines() if ln.strip().startswith("version-source")), "")
    d["extra-targets"] = [ln.strip() for ln in settings.splitlines() if ln.strip().startswith("path =")]
    d["tag-format"] = next((ln.strip() for ln in settings.splitlines() if ln.strip().startswith("tag-format")), "")
    d["repokit-common vendored"] = (repo / "scripts" / "repokit-common").exists()
    d["root tests"] = listing(repo / "tests")[:6] if (repo / "tests").is_dir() else []
    d["root README"] = (repo / "README.md").exists()
    return d


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="C:/code/claude-projects")
    ap.add_argument("--repos", default="claude-bookmarks,Claude-Session-Backup,claude-session-logger,dazzle-claude-plugins")
    a = ap.parse_args(argv)
    out = []
    for name in a.repos.split(","):
        repo = Path(a.root) / name
        if not repo.is_dir():
            out.append(f"## {name}\n\n(absent)\n")
            continue
        d = describe(repo)
        out.append(f"## {name}\n\n```json\n{json.dumps(d, indent=1, default=str)}\n```\n")
    text = "# Plugin checkouts, measured\n\n" + "\n".join(out)
    (HERE / "results.md").write_bytes(text.encode("utf-8"))
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
