"""Measure: what do the Node/TypeScript checkouts on this machine look like?

Before the js-ts language layer and its first presets are written (Phase 3
slice 3), read every package.json under C:/code at depth 1-3 (node_modules
excluded) and the files beside it that decide a layer's shape: tsconfig, the
test runner and bundler named in scripts/devDependencies, where the version
lives, engines/.nvmrc, "type": "module", a manifest.json (Obsidian or a
browser extension), a .claude-plugin folder. Read-only; prints a table and a
tally; nothing is written outside this folder's results file.

    python measure.py [--root C:/code] [--depth 3]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUNDLERS = ("vite", "esbuild", "webpack", "rollup", "parcel", "tsup")
RUNNERS = ("vitest", "jest", "mocha", "ava", "node --test", "tap", "uvu")


def find_package_jsons(root: Path, depth: int):
    for p in root.rglob("package.json"):
        rel = p.relative_to(root)
        if "node_modules" in rel.parts or len(rel.parts) > depth:
            continue
        yield p


def describe(pkg_path: Path) -> dict:
    d = pkg_path.parent
    try:
        pkg = json.loads(pkg_path.read_text(encoding="utf-8-sig"))
    except Exception as e:  # noqa: BLE001
        return {"dir": str(d), "error": str(e)[:60]}
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    scripts = pkg.get("scripts", {})
    test_cmd = scripts.get("test", "")
    runner = next((r for r in RUNNERS if r in test_cmd or r.split()[0] in deps), "")
    bundler = next((b for b in BUNDLERS if b in deps or any(b in v for v in scripts.values())), "")
    return {
        "dir": str(d.relative_to(d.anchor)),
        "name": pkg.get("name", ""),
        "version": pkg.get("version", ""),
        "type": pkg.get("type", "commonjs"),
        "ts": (d / "tsconfig.json").exists(),
        "typescript_dep": "typescript" in deps,
        "runner": runner,
        "bundler": bundler,
        "engines": json.dumps(pkg.get("engines", {})) if pkg.get("engines") else "",
        "nvmrc": (d / ".nvmrc").exists(),
        "exports": "exports" in pkg or "main" in pkg or "bin" in pkg,
        "manifest_json": (d / "manifest.json").exists(),
        "claude_plugin": (d / ".claude-plugin").exists() or (d / "plugin" / ".claude-plugin").exists(),
        "lock": next((n for n in ("package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb") if (d / n).exists()), ""),
        "repokit_common": (d / "scripts" / "repokit-common").exists(),
        "version_file": next((n for n in ("VERSION", "version.py", "version.txt") if (d / n).exists()), ""),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="C:/code")
    ap.add_argument("--depth", type=int, default=3)
    a = ap.parse_args(argv)
    rows = [describe(p) for p in sorted(find_package_jsons(Path(a.root), a.depth))]
    cols = ["dir", "name", "version", "type", "ts", "typescript_dep", "runner", "bundler", "engines", "nvmrc",
            "exports", "manifest_json", "claude_plugin", "lock", "repokit_common", "version_file"]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        lines.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
    tally = {
        "projects": len(rows),
        "tsconfig": sum(1 for r in rows if r.get("ts")),
        "type module": sum(1 for r in rows if r.get("type") == "module"),
        "runner": {k: sum(1 for r in rows if r.get("runner") == k) for k in set(r.get("runner", "") for r in rows)},
        "bundler": {k: sum(1 for r in rows if r.get("bundler") == k) for k in set(r.get("bundler", "") for r in rows)},
        "engines set": sum(1 for r in rows if r.get("engines")),
        ".nvmrc": sum(1 for r in rows if r.get("nvmrc")),
        "manifest.json": sum(1 for r in rows if r.get("manifest_json")),
        ".claude-plugin": sum(1 for r in rows if r.get("claude_plugin")),
        "lock": {k: sum(1 for r in rows if r.get("lock") == k) for k in set(r.get("lock", "") for r in rows)},
        "repokit-common vendored": sum(1 for r in rows if r.get("repokit_common")),
        "a VERSION-style file": sum(1 for r in rows if r.get("version_file")),
    }
    out = "\n".join(lines) + "\n\nTally: " + json.dumps(tally, indent=1) + "\n"
    (HERE / "results.md").write_text(f"# Node checkouts under {a.root} (depth <= {a.depth}), measured\n\n{out}", encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
