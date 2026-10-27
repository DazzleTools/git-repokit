"""Print probe.py's report as tables."""
import json
from pathlib import Path

r = json.loads((Path(__file__).resolve().parent / "out" / "report.json").read_text(encoding="utf-8"))
print("scratch", r["scratch"], "| patched calls", r["patch_counts"])
print("\nA. known-answer repo (branch `private` + folder `private/`):")
for row in r["part_a"]:
    print(f'  exit {row["exit"]:>3}  ambiguous={str(row["ambiguous"]):5}  {row["cmd"]}')
for k, v in r["creates"].items():
    print(f'\n{k}: exit={v["exit"]} ambiguous-lines={v["ambiguous_lines"]} ERROR-lines={v["error_lines"]}')
    print(f'   folders={v["folders"]}  github/={v["github_folder"]}')
    for b, d in v["branches"].items():
        more = " ..." if len(d["private"]) > 6 else ""
        print(f'   {b:10} files={d["files"]:4} private({len(d["private"])})={d["private"][:6]}{more}')
