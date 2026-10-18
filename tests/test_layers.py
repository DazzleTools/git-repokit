"""The code-type layer engine (repokit/layers.py) and the byte-preserving
renderer it shares with the structure templates (template_engine.render_bytes).

Design: the Phase 2 v2 analysis of 2026-10-09 (units U2.0-U2.3, U2.6) in the
project's private notes; proof: tests/one-offs/thinking/poc-one-engine/.
Everything here works on fixture trees under tmp_path; the one test that
builds a wheel is marked integration.
"""

import os
import re
import shutil
import string
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from repokit import common_kit, layers
from repokit.template_engine import RK_TOKEN, TemplateEngine, token_context

REPO = Path(__file__).resolve().parents[1]
ENGINE = TemplateEngine(verbose=0)
CTX = token_context({"project_name": "my-tool", "description": "Résumé – a tool",
                     "author": "Dustin", "author_email": "d@example.com",
                     "github": {"username": "acme"}}, archetype="c-cpp/cmake-app")


# --- U2.0: one renderer, two dialects, bytes preserved ------------------------

def test_dollar_dialect_matches_the_old_text_renderer():
    """CONSEQUENCE: 8 (safety) -- Python behaviour kept: every structure template
    renders to the same text through render_bytes as through string.Template."""
    for path in sorted((REPO / "repokit" / "templates").rglob("*.template")):
        data = path.read_bytes()
        old = string.Template(data.decode("utf-8")).safe_substitute(
            {k: str(v) for k, v in CTX.items()})
        assert ENGINE.render_bytes(data, CTX, dollar=True).decode("utf-8") == old, path.name


def test_bytes_outside_placeholders_never_change():
    """CONSEQUENCE: 9 (safety) -- a BOM, CRLF endings and a byte outside UTF-8
    survive; only the token changes, and the value goes in as UTF-8."""
    src = b"\xef\xbb\xbf/* \xe9 */\r\n#define __RK_MACRO___X 1\r\n$notatoken ${CMAKE_VAR} $<GENEX> ${{ gh }} $$\r\n"
    out = ENGINE.render_bytes(src, CTX, dollar=False)
    assert out == src.replace(b"__RK_MACRO__", b"MY_TOOL")
    out2 = ENGINE.render_bytes(b"__RK_DESCRIPTION__", CTX, dollar=False)
    assert out2 == "Résumé – a tool".encode("utf-8")


def test_the_dollar_dialect_is_only_for_template_files():
    """CONSEQUENCE: 7 (safety) -- under the token dialect a Makefile's $$ and a
    script's $1 are untouched; under the $ dialect safe_substitute would turn
    $$ into $ -- which is why layer files never get it."""
    data = b"all:\n\techo $$HOME $1 $description\n"
    assert ENGINE.render_bytes(data, CTX, dollar=False) == data
    assert ENGINE.render_bytes(data, CTX, dollar=True) != data


def test_an_unknown_token_is_left_in_place():
    assert ENGINE.render_bytes(b"__RK_NOPE__ x", CTX, dollar=False) == b"__RK_NOPE__ x"


def test_token_context_derives_every_name_from_the_project_name():
    """CONSEQUENCE: 7 (behaviour) -- the proof's names(): my-tool -> my_tool,
    MY_TOOL, MyTool; author and email join; the GUIDs are upper-case UUIDs."""
    assert (CTX["RK_PROJECT"], CTX["RK_SNAKE"], CTX["RK_MACRO"], CTX["RK_PASCAL"]) == \
        ("my-tool", "my_tool", "MY_TOOL", "MyTool")
    assert CTX["RK_ORG"] == "acme" and CTX["RK_AUTHOR"] == "Dustin" and CTX["RK_EMAIL"] == "d@example.com"
    assert CTX["RK_ARCHETYPE"] == "c-cpp/cmake-app"
    assert re.fullmatch(r"[0-9A-F-]{36}", CTX["RK_GUID_PROJECT"]) and CTX["RK_GUID_PROJECT"] != CTX["RK_GUID_SOLUTION"]


def test_render_template_to_file_writes_the_templates_own_line_endings(tmp_path):
    """CONSEQUENCE: 7 (behaviour) -- U2.0b: the structure files reach the project
    with the template's bytes (LF, pinned by .gitattributes), not the platform's."""
    out = tmp_path / "README.md"
    assert ENGINE.render_template_to_file("README.md", str(out), CTX, category="common")
    data = out.read_bytes()
    assert b"\r\n" not in data and b"my-tool" in data


# --- U2.1 / U2.2: the walk ---------------------------------------------------

MANIFEST = """\
[languages.alpha]
layers = ["languages/alpha"]
default = "alpha/app"
[languages.beta]
layers = ["languages/beta"]
[languages.ghost]
stub = true
description = "planned"
[archetypes."alpha/app"]
languages = ["alpha"]
layers = ["archetypes/alpha/app"]
[archetypes."alpha/lib"]
stub = true
description = "later"
"""


def _tree(tmp_path, workflow_token=False):
    root = tmp_path / "layers"
    (root / "manifest.toml").parent.mkdir(parents=True)
    (root / "manifest.toml").write_text(MANIFEST, encoding="utf-8")
    w = lambda rel, data: (root.joinpath(rel).parent.mkdir(parents=True, exist_ok=True),
                           root.joinpath(rel).write_bytes(data if isinstance(data, bytes) else data.encode()))
    w("languages/alpha/.gitignore.rkappend", "\n# alpha\n*.alpha\n")
    w("languages/alpha/include/__RK_SNAKE__/version.h", b"\xef\xbb\xbf#define __RK_MACRO___V 1\r\n")
    w("languages/alpha/src/app.rc", b"/* \xe9 */\r\nVALUE __RK_MACRO___V\r\n")
    w("languages/alpha/README.md", "alpha readme\n")
    w("languages/beta/.gitignore.rkappend", "# beta\n*.beta\n")
    w("languages/beta/README.md", "beta readme replaces alpha's\n")
    w("archetypes/alpha/app/.github/workflows/ci.yml", "on: push\nenv: ${{ secrets.X }}\n" + ("# __RK_PROJECT__\n" if workflow_token else ""))
    w("archetypes/alpha/app/__RK_PROJECT__.sln", "Project __RK_GUID_PROJECT__\r\n")
    w("archetypes/alpha/app/settings.toml", "[t]\na = 1\n")
    w("archetypes/alpha/app/settings.toml.rkappend", "b = 2\n")
    w("archetypes/alpha/app/bin/blob.bin", b"\0\1__RK_PROJECT__\2")
    return root


def test_resolve_orders_languages_then_archetype_and_implies_languages(tmp_path):
    """CONSEQUENCE: 8 (behaviour) -- languages in the order given, then the
    archetype; only the FIRST language's default archetype applies (two
    defaults would both claim the settings and build files); an archetype
    implies its language; generic adds nothing."""
    m = layers.load_manifest(_tree(tmp_path))
    r = layers.resolve(m, "alpha,beta")
    assert r.layers == ["languages/alpha", "languages/beta", "archetypes/alpha/app"]
    assert r.languages == ["alpha", "beta"] and r.archetype == "alpha/app"
    r_rev = layers.resolve(m, "beta,alpha")             # beta first: it has no default, so none applies
    assert r_rev.layers == ["languages/beta", "languages/alpha"] and r_rev.archetype is None
    r2 = layers.resolve(m, [], "alpha/app")
    assert r2.languages == ["alpha"] and r2.layers[-1] == "archetypes/alpha/app"
    assert layers.resolve(m, "generic").layers == []
    assert layers.resolve(m, ["generic", "beta"]).layers == ["languages/beta"]


@pytest.mark.parametrize("langs, arch, message", [
    ("cobol", None, "unknown language 'cobol'; known: generic, alpha, beta, ghost"),
    ("ghost", None, "language ghost is not built yet: planned"),
    ("alpha", "alpha/lib", "archetype alpha/lib is not built yet: later"),
    ("alpha", "alpha/nope", "unknown archetype 'alpha/nope'; known: alpha/app, alpha/lib"),
])
def test_unknown_names_and_stubs_are_refused_with_the_known_list(tmp_path, langs, arch, message):
    """CONSEQUENCE: 8 (behaviour) -- U2.4's contract: the message names what is
    known, and nothing is laid down."""
    m = layers.load_manifest(_tree(tmp_path))
    with pytest.raises(layers.LayerError, match=re.escape(message)):
        layers.resolve(m, langs, arch)


def test_assemble_replaces_appends_resolves_paths_and_keeps_bytes(tmp_path):
    """CONSEQUENCE: 9 (safety) -- the anchor for the walk: a later layer's file
    replaces, .rkappend appends (to a file the structure already wrote too),
    tokens resolve in paths and text, binaries and workflows are byte-copied,
    and a BOM, CRLF and a non-UTF-8 byte survive."""
    root = _tree(tmp_path)
    dest = tmp_path / "proj"
    dest.mkdir()
    (dest / ".gitignore").write_text("# structure\n*.log", encoding="utf-8")   # no trailing newline
    r = layers.resolve(layers.load_manifest(root), "alpha,beta")
    written = layers.assemble(root, r.layers, str(dest), CTX, engine=ENGINE)
    assert (dest / "README.md").read_text() == "beta readme replaces alpha's\n"
    assert (dest / ".gitignore").read_text() == "# structure\n*.log\n\n# alpha\n*.alpha\n# beta\n*.beta\n"
    assert (dest / "include/my_tool/version.h").read_bytes() == b"\xef\xbb\xbf#define MY_TOOL_V 1\r\n"
    assert (dest / "src/app.rc").read_bytes() == b"/* \xe9 */\r\nVALUE MY_TOOL_V\r\n"
    assert (dest / "my-tool.sln").read_bytes() == f"Project {CTX['RK_GUID_PROJECT']}\r\n".encode()
    assert (dest / "settings.toml").read_text() == "[t]\na = 1\nb = 2\n"
    assert (dest / "bin/blob.bin").read_bytes() == b"\0\1__RK_PROJECT__\2"
    assert (dest / ".github/workflows/ci.yml").read_text() == "on: push\nenv: ${{ secrets.X }}\n"
    assert not [p for p in dest.rglob("*") if RK_TOKEN.search(p.name)]
    assert sorted(written) == sorted([".gitignore", "README.md", "include/my_tool/version.h", "src/app.rc",
                                      ".github/workflows/ci.yml", "my-tool.sln", "settings.toml", "bin/blob.bin"])


def test_a_token_in_a_workflow_file_is_an_error(tmp_path):
    root = _tree(tmp_path, workflow_token=True)
    r = layers.resolve(layers.load_manifest(root), "alpha")
    with pytest.raises(layers.LayerError, match="token in workflow file"):
        layers.assemble(root, r.layers, str(tmp_path / "p"), CTX, engine=ENGINE)


def test_bytecode_beside_the_templates_is_not_a_layer_file(tmp_path):
    """CONSEQUENCE: 9 (safety) -- repokit-common's pre-push hook compiles
    repokit/ for its syntax check and leaves __pycache__/*.pyc beside the
    template sources, with the tokens inside; after one push attempt every
    created python project carried seven of them (found 2026-10-17)."""
    root = _tree(tmp_path)
    cache = root / "archetypes/alpha/app/__RK_SNAKE__/__pycache__"
    cache.mkdir(parents=True)
    (cache / "cli.cpython-312.pyc").write_bytes(b"\xa7\r\r\n\0\0__RK_PROJECT__\0")
    (root / "archetypes/alpha/app/stray.pyc").write_bytes(b"\0__RK_PROJECT__")
    dest = tmp_path / "proj"
    dest.mkdir()
    r = layers.resolve(layers.load_manifest(root), "alpha")
    written = layers.assemble(root, r.layers, str(dest), CTX, engine=ENGINE)
    assert not list(dest.rglob("*.pyc")) and not list(dest.rglob("__pycache__"))
    assert not [p for p in dest.rglob("*") if p.is_file() and p.suffix != ".bin"
                and RK_TOKEN.search(p.read_bytes().decode("latin-1"))]
    assert all(not w.endswith(".pyc") for w in written)


def test_preserve_existing_leaves_an_adopted_projects_files_alone(tmp_path):
    """CONSEQUENCE: 8 (safety) -- adopt: an existing file is neither replaced
    nor appended to; missing files are still laid down."""
    root = _tree(tmp_path)
    dest = tmp_path / "proj"
    dest.mkdir()
    (dest / "README.md").write_text("theirs\n")
    (dest / ".gitignore").write_text("theirs\n")
    r = layers.resolve(layers.load_manifest(root), "alpha")
    layers.assemble(root, r.layers, str(dest), CTX, engine=ENGINE, preserve_existing=True)
    assert (dest / "README.md").read_text() == "theirs\n" and (dest / ".gitignore").read_text() == "theirs\n"
    assert (dest / "include/my_tool/version.h").exists()


def test_the_shipped_manifest_names_only_layers_that_exist():
    """CONSEQUENCE: 7 (safety) -- every non-stub language and archetype in the
    package's manifest points at a folder in the package; every stub has a
    description to announce itself with."""
    root = layers.layers_root(ENGINE)
    assert root is not None
    m = layers.load_manifest(root)
    for table in (m["languages"], m["archetypes"]):
        for name, entry in table.items():
            if entry.get("stub"):
                assert entry.get("description"), name
                continue
            for layer in entry["layers"]:
                assert (root / layer).is_dir(), f"{name}: {layer}"
    for name, entry in m["languages"].items():
        if entry.get("default"):
            assert not m["archetypes"][entry["default"]].get("stub"), name


# --- U2.6: settings merge -----------------------------------------------------

def test_write_settings_merges_missing_keys_and_never_overwrites(tmp_path):
    """CONSEQUENCE: 9 (safety) -- a layer-supplied .repokit-common.toml keeps its
    version-source and gains private-patterns; a pyproject table the same; an
    existing key is untouched; CRLF survives."""
    f = tmp_path / ".repokit-common.toml"
    f.write_bytes(b'[tool.repokit-common]\r\nversion-source = "include/x/version.h"\r\nlanguages = ["c-cpp"]\r\n')
    assert common_kit.write_settings(str(tmp_path), {"private-patterns": ["CLAUDE.md"], "languages": ["NOT-THIS"]}) == ".repokit-common.toml"
    assert f.read_bytes() == (b'[tool.repokit-common]\r\nprivate-patterns = ["CLAUDE.md"]\r\n'
                              b'version-source = "include/x/version.h"\r\nlanguages = ["c-cpp"]\r\n')
    assert common_kit.write_settings(str(tmp_path), {"private-patterns": ["other"]}) is None   # present: untouched
    py = tmp_path / "pyproject.toml"
    py.write_text('[project]\nname = "p"\n\n[tool.repokit-common]\nversion-source = "p/_version.py"\n\n[tool.other]\nx = 1\n')
    assert common_kit.write_settings(str(tmp_path), {"private-branches": ["private", "scratch"]}) == "pyproject.toml"
    assert py.read_text() == ('[project]\nname = "p"\n\n[tool.repokit-common]\nprivate-branches = ["private", "scratch"]\n'
                              'version-source = "p/_version.py"\n\n[tool.other]\nx = 1\n')


# --- U2.3: packaging ----------------------------------------------------------

@pytest.mark.integration
def test_the_wheel_ships_every_layer_file_including_dotfiles(tmp_path):
    """CONSEQUENCE: 8 (safety) -- measured 2026-10-09: "templates/**/*" alone
    dropped every dotfile and dot-directory; the built wheel must hold the
    whole layer tree, .gitignore.rkappend and .github/ included."""
    pytest.importorskip("build")
    # The suite points HOME at a temp dir, which sends pip's cache to a `pip/`
    # folder under the working directory (seen once, 2026-10-09); keep it here.
    env = dict(os.environ, PIP_CACHE_DIR=str(tmp_path / "pip-cache"))
    r = subprocess.run([sys.executable, "-m", "build", "--wheel", "--outdir", str(tmp_path), str(REPO)],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    whl = next(tmp_path.glob("*.whl"))
    in_wheel = {n.split("repokit/templates/layers/", 1)[1] for n in zipfile.ZipFile(whl).namelist()
                if "repokit/templates/layers/" in n}
    on_disk = {p.relative_to(REPO / "repokit/templates/layers").as_posix()
               for p in (REPO / "repokit/templates/layers").rglob("*") if p.is_file()}
    assert on_disk <= in_wheel, sorted(on_disk - in_wheel)
    assert "languages/python/.gitignore.rkappend" in in_wheel
    assert "archetypes/c-cpp/cmake-app/.github/workflows/ci.yml" in in_wheel
