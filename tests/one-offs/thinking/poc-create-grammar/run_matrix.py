"""Run the six requests through the four grammars and print the matrix.

    python run_matrix.py          # the table, the typo row, the listing sizes
    python run_matrix.py --list D # one grammar's full `repokit list` output

Per cell: the command the person types, how many tokens after `create <name>`
(a comma-separated item counts as one token), the characters typed, and what
the grammar hands the engine (or the error). The kill condition is in the
README: the common case must cost no more than `create demo --language python`,
and no cell may be ambiguous.
"""

from __future__ import annotations

import shlex
import sys

from grammars import GRAMMARS, LISTINGS

# request -> grammar -> argv after `create <name>`
REQUESTS = {
    "common case: Python package (the floor to beat)": {
        "A": "--language python", "B": "--language python", "C": "--language python --kind pypi", "D": "--language python",
    },
    "Claude Code plugin": {
        "A": "--archetype js-ts/claude-plugin", "B": "--type claude-plugin",
        "C": "--kind js-ts,node,claude-plugin", "D": "--archetype js-ts/claude-plugin",
    },
    "Vite + React + TypeScript site": {
        "A": "--archetype js-ts/web-vite-react", "B": "--type web-vite-react",
        "C": "--kind js-ts,browser,ts,vite,react", "D": "--archetype ts,react,vite",
    },
    "Python local script (simple project)": {
        "A": "--archetype python/script", "B": "--type script",
        "C": "--kind python,python/script", "D": "--archetype python/script",
    },
    "C/C++ library with Qt": {
        "A": "--archetype c-cpp/cmake-lib-qt", "B": "--type cmake-lib-qt",
        "C": "--kind c-cpp,cmake-lib,c-cpp/qt", "D": "--archetype cmake-lib,qt",
    },
    "Python + C/C++ mixed": {
        "A": "--language python,c-cpp", "B": "--language python,c-cpp",
        "C": "--language python,c-cpp", "D": "--language python,c-cpp",
    },
    "bare `create demo`": {"A": "", "B": "", "C": "", "D": ""},
}

TYPOS = {
    "A": "--archetype js-ts/claude-plugn", "B": "--type claude-plugn",
    "C": "--kind js-ts,node,claude-plugn", "D": "--archetype claude-plugn",
}

AMBIGUOUS = {
    "A": "--archetype c-cpp/qt", "B": "--type qt-cpp", "C": "--kind qt", "D": "--archetype qt",
}

COLLISION = {"D": "--archetype pypi,setuppy", "C": "--kind python,pypi,setuppy"}


def tokens(cmd: str) -> int:
    return len(shlex.split(cmd))


def main(argv):
    if len(argv) == 2 and argv[0] == "--list":
        print("\n".join(LISTINGS[argv[1]]()))
        return 0
    for req, cells in REQUESTS.items():
        print(f"\n== {req}")
        for g in "ABCD":
            cmd = cells[g]
            layers, err, notes = GRAMMARS[g](shlex.split(cmd))
            shown = f"create x {cmd}".strip()
            cost = f"{tokens(cmd)} tok / {len(cmd):2d} ch"
            if err:
                print(f"  {g}  {shown:46} {cost}  ERROR {err}")
            else:
                extra = f"  [{'; '.join(f'{k}: {v}' for k, v in notes.items())}]" if notes else ""
                print(f"  {g}  {shown:46} {cost}  -> {', '.join(layers) or '(structure only)'}{extra}")
    print("\n== typo: claude-plugn")
    for g in "ABCD":
        _, err, _ = GRAMMARS[g](shlex.split(TYPOS[g]))
        print(f"  {g}  {TYPOS[g]:40} {err}")
    print("\n== the two qt layers: how each grammar asks for the C++ one, and what bare 'qt' does")
    for g in "ABCD":
        layers, err, notes = GRAMMARS[g](shlex.split(AMBIGUOUS[g]))
        print(f"  {g}  {AMBIGUOUS[g]:40} {err or ', '.join(layers)}")
    print("\n== two package shapes at once")
    for g, cmd in COLLISION.items():
        layers, err, notes = GRAMMARS[g](shlex.split(cmd))
        print(f"  {g}  {cmd:40} {err or (', '.join(layers) + ' ' + str(notes))}")
    print("\n== listing size (lines of `repokit list`)")
    for g in "ABCD":
        rows = LISTINGS[g]()
        print(f"  {g}  {len(rows):3d} lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
