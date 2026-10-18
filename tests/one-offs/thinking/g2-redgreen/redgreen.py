"""Red-green audit of slice G2's new tests (2026-10-09): the layer engine.

Same shape as git-repokit-common's g1-redgreen: each arm reverts ONE behaviour
(never an API), runs only the tests that should notice, restores the file byte
for byte (SHA-256 checked), and the full output is archived beside this script.
Runs only inside this checkout; the tests work under tmp_path / the test dir.
"""
import datetime
import hashlib
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
assert (ROOT / "repokit" / "layers.py").is_file(), ROOT
ENGINE = "tests/test_layers.py -m 'not integration'"
CLI = "tests/test_layers_cli.py"

M = [  # (name, file, old, new, selector, tests expected RED)
    ("M1 latin-1 round trip replaced by utf-8", "repokit/template_engine.py",
     '        text = data.decode("latin-1")\n        if dollar:',
     '        text = data.decode("utf-8", "replace")\n        if dollar:',
     f"{ENGINE} -k 'bytes_outside or keeps_bytes'", ["bytes_outside", "keeps_bytes"]),
    ("M2 $ dialect applied to layer files too", "repokit/template_engine.py",
     "        if dollar:\n            text = string.Template(text).safe_substitute(values)",
     "        if True:\n            text = string.Template(text).safe_substitute(values)",
     f"{ENGINE} -k 'only_for_template_files'", ["only_for_template_files"]),
    ("M3 stubs resolve like built layers", "repokit/layers.py",
     '        if entry.get("stub"):\n            raise LayerError(f"language {name} is not built yet',
     '        if False:\n            raise LayerError(f"language {name} is not built yet',
     f"{ENGINE} -k 'refused_with_the_known_list'", ["ghost"]),
    ("M4 an earlier layer wins (replace order inverted)", "repokit/layers.py",
     "            else:\n                files[rel] = data   # a later layer's file replaces an earlier one",
     "            else:\n                files.setdefault(rel, data)",
     f"{ENGINE} -k 'replaces_appends'", ["replaces_appends"]),
    ("M5 .rkappend replaces instead of appending", "repokit/layers.py",
     "                if target in files:\n                    files[target] = _joined(files[target], data)",
     "                if target in files:\n                    files[target] = data",
     f"{ENGINE} -k 'replaces_appends'", ["replaces_appends"]),
    ("M6 path tokens unresolved", "repokit/layers.py",
     '        resolved = engine.render_bytes(rel.encode("utf-8"), context, dollar=False).decode("utf-8")',
     '        resolved = rel',
     f"tests/test_layers.py {CLI} -m 'not integration' -k 'replaces_appends or stack_in_the_order'", ["replaces_appends", "stack_in_the_order"]),
    ("M7 token-in-workflow check off", "repokit/layers.py",
     '        if is_workflow and RK_TOKEN.search(data.decode("latin-1")):',
     '        if False:',
     f"{ENGINE} -k 'workflow_file_is_an_error'", ["workflow_file_is_an_error"]),
    ("M8 preserve_existing ignored", "repokit/layers.py",
     '        if preserve_existing and os.path.exists(full):\n            if logger:\n                logger.info(f"Preserving existing file: {target}")\n            continue',
     '        if False:\n            continue',
     f"{ENGINE} -k 'preserve_existing'", ["preserve_existing"]),
    ("M9 settings never merged (0.6.0 behaviour)", "repokit/common_kit.py",
     "        if _TABLE_HEADER.search(text):\n            merged = _merge_into_table(text, settings)\n            if merged is None:\n                return None",
     "        if _TABLE_HEADER.search(text):\n            merged = None\n            if merged is None:\n                return None",
     f"{ENGINE} -k 'merges_missing_keys'", ["merges_missing_keys"]),
    ("M10 CLI validation removed", "repokit/cli.py",
     "        except _layers.LayerError as e:\n            logger.error(str(e))\n            return 1",
     "        except _layers.LayerError as e:\n            logger.error(str(e))\n            pass",
     f"{CLI} -k 'fail_before_anything'", ["fail_before_anything"]),
    ("M11 layers not applied by create", "repokit/repo_manager.py",
     "        self._write_gitignore_and_launch(context)\n        self._apply_layers(context)",
     "        self._write_gitignore_and_launch(context)",
     f"{CLI} -k 'keeps_todays_output'", ["keeps_todays_output"]),
]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    stamp = datetime.datetime.now().strftime("%Y-%m-%d__%H-%M-%S")
    log = Path(__file__).with_name(f"run-{stamp}.txt")
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    before = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout
    out = [f"redgreen G2 at {head} (tree dirty: slice uncommitted) -- {stamp}", f"python {sys.version.split()[0]}", ""]
    rows = []
    only = sys.argv[1:]
    for name, rel, old, new, selector, expect_red in M:
        if only and not any(name.startswith(o + " ") for o in only):
            continue
        f = ROOT / rel
        orig = f.read_bytes()
        digest = sha(f)
        nl = "\r\n" if b"\r\n" in orig else "\n"
        text = orig.decode("utf-8").replace("\r\n", "\n")
        assert text.count(old) == 1, f"{name}: anchor not unique/found in {rel} ({text.count(old)})"
        f.write_bytes(text.replace(old, new).replace("\n", nl).encode("utf-8"))
        try:
            r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *shlex.split(selector)],
                               cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        finally:
            f.write_bytes(orig)
        assert sha(f) == digest, f"{name}: restore failed for {rel}"
        failed = [line.split("::")[-1].split(" ")[0] for line in r.stdout.splitlines() if line.startswith("FAILED")]
        summary = next((l for l in r.stdout.splitlines()[::-1] if "passed" in l or "failed" in l), r.stdout[-200:])
        red_ok = all(any(e in fl for fl in failed) for e in expect_red)
        rows.append((name, rel, summary.strip("= "), "RED as expected" if red_ok else "NOT RED -> check", failed))
        out += [f"=== {name} ({rel}) :: {selector}", r.stdout, r.stderr, ""]
    after = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout
    out += ["=== tree check", "porcelain unchanged" if before == after else "PORCELAIN CHANGED\n" + before + "\n---\n" + after]
    log.write_text("\n".join(out), encoding="utf-8")
    for name, rel, summary, verdict, failed in rows:
        print(f"{name:48} {rel:28} {summary:42} {verdict}")
        for fl in failed:
            print(f"{'':48} red: {fl}")
    print("tree:", "unchanged" if before == after else "CHANGED")
    print("log:", log)


if __name__ == "__main__":
    main()
