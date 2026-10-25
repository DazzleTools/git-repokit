"""0.9.8: git-repokit as a PyPI package.

The name PyPI's trusted publisher is registered for, the measured Python floor,
the PEP 639 license fields, a publish workflow that runs on a published release
through the `pypi` environment, and the leak check that guards both artifacts.
"""
import importlib.util
import io
import sys
import tarfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

if sys.version_info >= (3, 11):
    import tomllib
else:  # the floor, 3.10
    import tomli as tomllib


def pyproject():
    return tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))


def leak_checker():
    spec = importlib.util.spec_from_file_location("check_dist_no_leak", REPO / "scripts" / "check_dist_no_leak.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_distribution_is_named_for_its_trusted_publisher():
    project = pyproject()["project"]
    assert project["name"] == "git-repokit"
    assert project["scripts"]["repokit"] == "repokit.cli:main"


def test_the_python_floor_is_the_measured_one_and_tomli_covers_it():
    project = pyproject()["project"]
    assert project["requires-python"] == ">=3.10"
    assert any(d.startswith("tomli") and "python_version < '3.11'" in d for d in project["dependencies"])
    assert "Programming Language :: Python :: 3.10" in project["classifiers"]


def test_the_license_is_declared_the_pep_639_way():
    data = pyproject()
    assert data["project"]["license"] == "MIT"
    assert data["project"]["license-files"] == ["LICENSE"]
    assert not [c for c in data["project"]["classifiers"] if c.startswith("License ::")]
    assert any(r.startswith("setuptools>=77") for r in data["build-system"]["requires"])


def test_setup_py_is_only_a_shim():
    text = (REPO / "setup.py").read_text(encoding="utf-8")
    assert "setup()" in text and "name=" not in text


def test_publish_runs_on_a_release_through_the_pypi_environment():
    wf = (REPO / ".github" / "workflows" / "publish.yml").read_text(encoding="utf-8")
    assert "release:" in wf and "types: [published]" in wf
    assert "name: pypi" in wf and "id-token: write" in wf
    assert "pypa/gh-action-pypi-publish@release/v1" in wf and "skip-existing: true" in wf
    assert "check_dist_no_leak.py" in wf and "twine check --strict" in wf


def test_the_alias_publishes_from_its_own_job_beside_git_repokit():
    wf = (REPO / ".github" / "workflows" / "publish.yml").read_text(encoding="utf-8")
    # git-repokit's steps are the ones that first published 0.9.10
    assert "python -m build --outdir dist/\n" in wf and "name: dist\n" in wf
    assert "url: https://pypi.org/p/git-repokit\n" in wf
    # the alias: its own build folder, leak check, metadata check and job
    assert "python -m build packages/dazzle-git-repokit-alias/ --outdir dist-alias/" in wf
    assert "check_dist_no_leak.py dist-alias/" in wf and "twine check --strict dist-alias/*" in wf
    alias_job = wf.split("publish-alias:")[1]
    assert "needs: build" in alias_job and "name: pypi" in alias_job and "id-token: write" in alias_job
    assert "url: https://pypi.org/p/dazzle-git-repokit" in alias_job
    assert "name: dist-alias" in alias_job and "skip-existing: true" in alias_job


def alias_pyproject():
    path = REPO / "packages" / "dazzle-git-repokit-alias" / "pyproject.toml"
    return tomllib.loads(path.read_text(encoding="utf-8"))


def test_the_alias_moves_in_lockstep_with_git_repokit():
    main, alias = pyproject()["project"], alias_pyproject()["project"]
    assert alias["name"] == "dazzle-git-repokit"
    assert alias["version"] == main["version"]
    assert alias["dependencies"] == [f"git-repokit>={main['version']}"]
    # pipx exposes only the named package's commands, so the alias declares repokit too
    assert alias["scripts"] == main["scripts"]
    assert alias["requires-python"] == main["requires-python"]
    assert alias["license"] == main["license"]


def _tar(names):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for n in names:
            data = b"x"
            info = tarfile.TarInfo(n)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def test_the_leak_check_refuses_vault_and_local_only_paths(tmp_path):
    mod = leak_checker()
    for bad in ("pkg-1.0/private/claude/note.md", "pkg-1.0/convos/x.md", "pkg-1.0/tests/old_test_runs/a/b",
                "pkg-1.0/.env", "pkg-1.0/sub/credentials.json"):
        assert mod.is_forbidden(bad), bad
    for good in ("pkg-1.0/repokit/templates/vault/CLAUDE.md.template", "pkg-1.0/repokit/cli.py",
                 "pkg-1.0/tests/test_cli_integration.py"):
        assert not mod.is_forbidden(good), good
    clean, dirty = tmp_path / "clean", tmp_path / "dirty"
    clean.mkdir(); dirty.mkdir()
    (clean / "p-1.0.tar.gz").write_bytes(_tar(["p-1.0/repokit/cli.py"]))
    (dirty / "p-1.0.tar.gz").write_bytes(_tar(["p-1.0/repokit/cli.py", "p-1.0/private/claude/x.md"]))
    with zipfile.ZipFile(clean / "p-1.0-py3-none-any.whl", "w") as z:
        z.writestr("repokit/cli.py", "x")
    assert mod.main(["check", str(clean)]) == 0
    assert mod.main(["check", str(dirty)]) == 1
    assert mod.main(["check", str(tmp_path / "nothing-here")]) == 2
