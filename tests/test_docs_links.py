"""0.9.11: the README's and the guides' relative links lead somewhere.

The documentation was rewritten in 0.9.11 and its guides link to each other,
so a renamed or missing guide would leave dead links nobody notices until a
reader clicks one.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\]\(([^)\s]+)\)")


def _documents():
    return [REPO / "README.md", REPO / "CONTRIBUTING.md"] + sorted((REPO / "docs").glob("*.md"))


def test_every_relative_link_in_the_docs_names_a_file_that_exists():
    bad = []
    for doc in _documents():
        text = re.sub(r"```.*?```", "", doc.read_text(encoding="utf-8"), flags=re.S)
        for target in LINK.findall(text):
            if re.match(r"[a-z]+:", target) or target.startswith("#"):
                continue  # a URL, or an anchor in the same page
            path = target.split("#", 1)[0]
            if not (doc.parent / path).exists():
                bad.append(f"{doc.relative_to(REPO)} -> {target}")
    assert not bad, "\n".join(bad)


def test_the_readme_links_every_guide_in_docs():
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    guides = [p.name for p in (REPO / "docs").glob("*.md") if p.name != "README.md"]
    missing = [g for g in guides if f"docs/{g}" not in readme]
    assert not missing, f"README.md does not link: {', '.join(missing)}"
