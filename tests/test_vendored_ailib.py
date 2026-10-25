"""git-repokit's copy of ailib (0.9.4): purity and honesty, as ccs's copy of
record keeps them (ccs's tests/test_vendored_ailib.py, the model).

Purity: the copy names nothing of its host -- no import of repokit, no
relative import out of _vendor/ailib, no repokit or ccs token, standard
library only -- so it lifts unchanged into a shared dazzle-ailib.
Honesty: every file matches the fingerprint it arrived with from ccs, or is
named in _VENDORED.md's "Changes in git-repokit's copy".
"""
import ast
import hashlib
import importlib.util
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VENDOR = REPO / "repokit" / "_vendor"
AILIB = VENDOR / "ailib"
RECORD = AILIB / "_VENDORED.md"
SECTION = "## git-repokit's copy"

_FORBIDDEN = ("repokit", "dazzle_claude_config", "ccs_", "CCS_")
_REL_IMPORT = re.compile(r"^\s*from\s+(\.+)([\w.]*)\s+import\b")
_IMPORT = re.compile(r"^\s*(?:from|import)\s+([\w.]+)")


def _py():
    return sorted(p for p in AILIB.rglob("*.py") if "__pycache__" not in p.parts)


def _sha(p):
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _section():
    text = RECORD.read_text(encoding="utf-8")
    return text[text.index(SECTION):]


def _received():
    rows = {}
    for line in _section().splitlines():
        m = re.match(r"\|\s*`([^`]+)`\s*\|\s*([0-9a-f]{64})\s*\|", line)
        if m:
            rows[m.group(1)] = m.group(2)
    return rows


def test_the_vendor_tree_is_a_package_with_its_record():
    assert (VENDOR / "__init__.py").is_file() and (AILIB / "__init__.py").is_file()
    assert RECORD.is_file() and SECTION in RECORD.read_text(encoding="utf-8")


def _stdlib_names():
    """The standard library's top-level module names. sys.stdlib_module_names
    is Python 3.10+; on 3.9 (git-repokit's floor) they are read from the
    interpreter's own library folder, plus its built-in modules."""
    if hasattr(sys, "stdlib_module_names"):
        return set(sys.stdlib_module_names)
    import sysconfig
    lib = Path(sysconfig.get_paths()["stdlib"])
    names = {p.stem for p in lib.glob("*.py")} | {p.name for p in lib.iterdir()
                                                  if p.is_dir() and (p / "__init__.py").exists()}
    return names | set(sys.builtin_module_names)


def test_purity_nothing_under_vendor_knows_its_host():
    """Real import statements (read with ast, so examples in docstrings do not
    count) stay inside the copy or the standard library; no host token appears
    anywhere in the text."""
    stdlib = _stdlib_names() | {"__future__"}
    bad = []
    for p in _py():
        rel = p.relative_to(AILIB).as_posix()
        pkg = "repokit._vendor.ailib" + ("" if p.parent == AILIB else "." + p.parent.relative_to(AILIB).as_posix().replace("/", "."))
        text = p.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.ImportFrom) and node.level:
                target = importlib.util.resolve_name("." * node.level + (node.module or ""), pkg)
                if not target.startswith("repokit._vendor.ailib"):
                    bad.append(f"{rel}:{node.lineno}: relative import leaves _vendor/ailib")
            elif isinstance(node, ast.ImportFrom) and node.module.split(".")[0] not in stdlib:
                bad.append(f"{rel}:{node.lineno}: not the standard library: {node.module}")
            elif isinstance(node, ast.Import):
                bad += [f"{rel}:{node.lineno}: not the standard library: {a.name}"
                        for a in node.names if a.name.split(".")[0] not in stdlib]
        for n, line in enumerate(text.splitlines(), 1):
            for tok in _FORBIDDEN:
                if tok in line:
                    bad.append(f"{rel}:{n}: token {tok!r}")
    assert not bad, "\n".join(bad)


def test_every_file_is_as_received_or_named_in_the_changes():
    received = _received()
    files = {p.relative_to(AILIB).as_posix(): p for p in _py()}
    assert set(received) == set(files), "a vendored file has no row, or a row has no file"
    changes = _section().split("### Changes in git-repokit's copy", 1)[1]
    undeclared = [rel for rel, p in files.items() if _sha(p) != received[rel] and f"`{rel}`" not in changes]
    assert undeclared == [], f"changed without a record entry: {undeclared}"


def test_the_copy_imports_and_its_prompt_file_transport_is_there():
    from repokit._vendor.ailib import backend
    from repokit._vendor.ailib.transports import prompt_file  # noqa: F401
    assert hasattr(backend, "register_transport")
