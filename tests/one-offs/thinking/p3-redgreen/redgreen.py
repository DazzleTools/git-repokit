"""Red-green audit of the v0.8.0 tests: would each be red if its behaviour were not there?

    python tests/one-offs/thinking/p3-redgreen/redgreen.py [--arms a,b,...]

Each arm neutralises ONE behaviour by a text substitution that keeps every
signature (the API stays; the behaviour goes), runs only the tests that claim
to pin it, records which failed on an assertion, and restores the file from a
byte copy taken before the arm. Nothing is committed; the tree is compared
before and after (git status --porcelain and the files' bytes).

Design: the test-redgreen skill; the arms map to the eight rules of the Phase 3
design (2026-10-19__22-11-27__dev-workflow-process__family-type-system-facets-and-grammar.md, D2).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
LAYERS = REPO / "repokit" / "layers.py"
MANIFEST = REPO / "repokit" / "templates" / "layers" / "manifest.toml"
REPOMGR = REPO / "repokit" / "repo_manager.py"
CLI = REPO / "repokit" / "cli.py"

UNIT = "tests/test_layers.py"
CLI_TESTS = "tests/test_layers_cli.py::TestWithList"
COMPOSITIONS = "tests/test_layers_compositions.py"

# name -> (file, old, new, test selector, tests expected to go red)
ARMS = {
    "manifest-tables": (MANIFEST, None, None, f"{UNIT} -k every_layer_folder",
                        ["test_every_layer_folder_has_a_manifest_entry_with_a_known_facet"]),
    "exclusivity": (LAYERS, "            if other and other != name:", "            if False and other and other != name:",
                    f"{UNIT} -k 'exclusive_facet'", ["test_two_layers_in_one_exclusive_facet_are_refused_naming_the_pair"]),
    "ambiguity": (LAYERS, "                raise LayerError(f\"{tok!r} is ambiguous: {' or '.join(candidates)}\")",
                  "                candidates = candidates[:1]",
                  f"{UNIT} -k 'two_languages'", ["test_a_bare_name_in_two_languages_is_refused_with_both_forms"]),
    "implies": (LAYERS, '            for imp in layer_table[name].get("implies", []):', "            for imp in []:",
                f"{UNIT} -k 'composed_list or bare_preset or ts_and_vite'",
                ["test_a_composed_list_is_ordered_implied_and_recognised_as_its_preset", "test_a_bare_preset_name_resolves_when_unique",
                 "test_ts_and_vite_are_different_facets"]),
    "ordering": (LAYERS, "key=lambda ic: (facet_rank(manifest, layer_table.get(ic[1][1] or \"\", {}).get(\"facet\")), ic[0])",
                 "key=lambda ic: ic[0]",
                 f"{UNIT} -k 'composed_list or ts_and_vite'",
                 ["test_a_composed_list_is_ordered_implied_and_recognised_as_its_preset", "test_ts_and_vite_are_different_facets"]),
    "recognition": (LAYERS, "            if expansion == res.layers:", "            if False:",
                    f"{UNIT} -k 'composed_list or bare_preset or default_preset'",
                    ["test_a_composed_list_is_ordered_implied_and_recognised_as_its_preset", "test_a_bare_preset_name_resolves_when_unique",
                     "test_the_default_preset_still_applies_when_nothing_is_asked"]),
    "suggestion": (LAYERS, "    return f\"; did you mean {', '.join(close)}?\" if close else \"\"", "    return \"\"",
                   f"{UNIT} -k 'typo'", ["test_a_typo_suggests_the_close_name"]),
    "lower-dedupe": (LAYERS, "        if t.lower() not in tokens:\n            tokens.append(t.lower())", "        tokens.append(t)",
                     f"{UNIT} -k 'lower_cases'", ["test_resolve_lower_cases_and_dedupes_tokens"]),
    "note": (LAYERS, "            res.notes.append(NOT_A_PRESET)", "            pass",
             f"{UNIT} -k 'unrecognised_composition or default_preset'",
             ["test_an_unrecognised_composition_carries_the_note_and_narrows_qt_by_language",
              "test_the_default_preset_still_applies_when_nothing_is_asked"]),
    # CLI-level (slow): the metadata key, the Note print, the list command
    "cli-layers-key": (REPOMGR, '            "layers": self.config.get("layers") or [],\n', "",
                       f"{CLI_TESTS}", ["test_the_common_case_is_unchanged_and_records_its_layers",
                                        "test_a_bare_preset_name_and_a_composition_both_resolve", "test_generic_lays_down_no_code_type_files"]),
    "cli-note-print": (REPOMGR, '            print(f"Note: {note} ({\', \'.join(resolution.tokens)})")', "            pass",
                       f"{CLI_TESTS} -k 'composition_both_resolve'", ["test_a_bare_preset_name_and_a_composition_both_resolve"]),
    "cli-list": (CLI, "            for line in _layers.catalogue_lines(_layers.load_manifest(_root), args.language):",
                 "            for line in []:",
                 f"{CLI_TESTS} -k 'list_fits'", ["test_list_fits_a_screen_and_names_presets_and_facets"]),
}


def run_tests(selector: str) -> tuple[int, str]:
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *selector.split(" ", 1)[0:1],
                        *([] if " -k " not in selector else ["-k", selector.split(" -k ", 1)[1].strip("'")])],
                       cwd=str(REPO), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    return r.returncode, r.stdout + r.stderr


def failed_names(out: str) -> list[str]:
    names = []
    for ln in out.splitlines():
        if ln.startswith("FAILED "):
            names.append(ln.split("::")[-1].split(" ")[0].split("[")[0])
    return names


def main(argv: list[str]) -> int:
    wanted = None
    if "--arms" in argv:
        wanted = set(argv[argv.index("--arms") + 1].split(","))
    status_before = subprocess.run(["git", "status", "--porcelain"], cwd=str(REPO), capture_output=True, text=True).stdout
    originals = {p: p.read_bytes() for p in (LAYERS, MANIFEST, REPOMGR, CLI)}
    head_manifest = subprocess.run(["git", "show", "HEAD:repokit/templates/layers/manifest.toml"], cwd=str(REPO), capture_output=True).stdout
    report = []
    try:
        for name, (path, old, new, selector, expected) in ARMS.items():
            if wanted and name not in wanted:
                continue
            text = originals[path]
            if old is None:
                mutated = head_manifest
            else:
                if old.encode("utf-8") not in text:
                    report.append((name, "ARM-BROKEN: anchor text not found", [], expected))
                    continue
                mutated = text.replace(old.encode("utf-8"), new.encode("utf-8"), 1)
            path.write_bytes(mutated)
            try:
                rc, out = run_tests(selector)
            finally:
                path.write_bytes(originals[path])
            failed = failed_names(out)
            anchors = [t for t in expected if t in failed]
            guards = [t for t in expected if t not in failed]
            wrong = [t for t in failed if t not in expected]
            summary = "ok" if not wrong else f"also red (collateral): {', '.join(wrong)}"
            report.append((name, summary, anchors, guards))
            print(f"[{name}] anchors={len(anchors)} guards={len(guards)} {summary}")
    finally:
        for p, b in originals.items():
            p.write_bytes(b)
    # restore check
    same = all(p.read_bytes() == b for p, b in originals.items())
    status_after = subprocess.run(["git", "status", "--porcelain"], cwd=str(REPO), capture_output=True, text=True).stdout
    rc, out = run_tests(f"{UNIT}")
    print("\n== restore:", "bytes identical" if same else "BYTES DIFFER", "| porcelain identical" if status_before == status_after else "| PORCELAIN DIFFERS",
          "| unit file green" if rc == 0 else "| UNIT FILE RED AFTER RESTORE")
    print("\n== split")
    total_a = total_g = 0
    for name, summary, anchors, guards in report:
        total_a += len(anchors); total_g += len(guards)
        for t in anchors:
            print(f"  anchor  {t}  <- {name}")
        for t in guards:
            print(f"  GUARD   {t}  <- {name} ({summary})")
    print(f"\n{total_a} anchors / {total_g} guards over the arms run; compositions test labelled guard by nature (not run as an arm)")
    return 0 if same and status_before == status_after and rc == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
