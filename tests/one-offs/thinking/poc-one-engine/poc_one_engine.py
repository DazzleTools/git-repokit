"""POC (g): one byte-preserving substitution for both of git-repokit's template kinds.

Written before running (2026-10-09), so a miss is a finding:

Arms and predictions
  A  proof layer files (23), RK dialect:   output == assemble.py's own resolve() byte for byte;
                                            CRLF count and non-ASCII byte count unchanged; 0 __RK_ left.
  B  git-repokit templates (15), $ dialect: output decoded as UTF-8 == today's
                                            TemplateEngine.render_template(content, ctx), same ctx,
                                            including a non-ASCII value.
  H  hazard: proof files through the $ dialect: predicted to change at least one file outside token
     spans ($$ in a Makefile, $word in a script) -- the reason the dialect is chosen per file kind.
  C  control (designed to fail): today's text path over the 23 proof files -- predicted
     UnicodeDecodeError on app.rc (cp1252) and LF->CRLF on at least one LF-only file.

Pass: A and B hold, C fails on >= 1 file. H is informative. If C passes, the method is broken.
Fallback if A or B fails: two engines (candidate a) as designed on 2026-10-09 06:03.
"""
import os
import re
import string
import sys
import tempfile
from pathlib import Path

PROOF = Path(r"C:\code\git-repokit-common\tests\one-offs\thinking\poc-templates-c-cpp")
REPOKIT = Path(r"C:\code\git-repokit")
sys.path.insert(0, str(PROOF))
sys.path.insert(0, str(REPOKIT))
import assemble  # noqa: E402  the proof's resolve() is arm A's oracle
from repokit.template_engine import TemplateEngine  # noqa: E402

RK = re.compile(r"__RK_([A-Z_]+?)__")


def render_bytes(data: bytes, ctx: dict, dollar: bool) -> bytes:
    """One function, two dialects. latin-1 is a lossless byte<->str map; values go in as UTF-8."""
    text = data.decode("latin-1")
    lat = {k: v.encode("utf-8").decode("latin-1") for k, v in ctx.items()}
    if dollar:
        text = string.Template(text).safe_substitute(lat)
    text = RK.sub(lambda m: lat.get("RK_" + m.group(1), m.group(0)), text)
    return text.encode("latin-1")


def main():
    names = assemble.names("my-tool", "DazzleTools", "Résumé – a tool", "c-cpp/cmake-app")
    ctx = {"RK_" + k.strip("_")[3:]: v for k, v in names.items()}  # __RK_PROJECT__ -> RK_PROJECT
    ctx.update(project_name="my-tool", description="Résumé – a tool", language="python",
               author_name="Dustin", author_email="d@example.com", badges="[b]")
    subs = {k.encode(): v.encode() for k, v in names.items()}

    def oracle(blob):  # assemble.py:92-95, verbatim semantics
        for k, v in subs.items():
            blob = blob.replace(k, v)
        return blob

    results = []
    # ---- A
    proof_files = sorted(p for p in (PROOF / "templates").rglob("*") if p.is_file() and p.name != "manifest.toml")
    bad = []
    for p in proof_files:
        src = p.read_bytes()
        out = render_bytes(src, ctx, dollar=False)
        same = out == oracle(src)
        crlf = src.count(b"\r\n") == out.count(b"\r\n")
        hi = sum(b > 127 for b in src) <= sum(b > 127 for b in out)  # source bytes kept; values may add some
        left = RK.search(out.decode("latin-1")) is None
        if not (same and crlf and hi and left):
            bad.append((p.relative_to(PROOF).as_posix(), same, crlf, hi, left))
    results.append(("A", not bad, f"{len(proof_files)} files; mismatches: {bad}"))

    # ---- B
    eng = TemplateEngine(verbose=0)
    tpls = sorted(p for p in (REPOKIT / "repokit/templates").rglob("*") if p.is_file())
    badb = []
    for p in tpls:
        src = p.read_bytes()
        today = eng.render_template(src.decode("utf-8"), ctx)
        ours = render_bytes(src, ctx, dollar=True).decode("utf-8")
        if today != ours:
            badb.append(p.relative_to(REPOKIT).as_posix())
    results.append(("B", not badb, f"{len(tpls)} templates; differ: {badb}"))

    # ---- H
    changed = []
    for p in proof_files:
        src = p.read_bytes()
        if render_bytes(src, ctx, dollar=True) != oracle(src):
            changed.append(p.relative_to(PROOF / "templates").as_posix())
    results.append(("H", bool(changed), f"$ dialect alters {len(changed)} proof files beyond tokens: {changed}"))

    # ---- C (control; predicted to fail)
    decode_err, newline_changed = [], []
    with tempfile.TemporaryDirectory() as td:
        for p in proof_files:
            try:
                with open(p, "r", encoding="utf-8") as f:
                    text = f.read()
            except UnicodeDecodeError:
                decode_err.append(p.name)
                continue
            outp = os.path.join(td, p.name)
            with open(outp, "w", encoding="utf-8") as f:
                f.write(text)
            if Path(outp).read_bytes().count(b"\r\n") != p.read_bytes().count(b"\r\n"):
                newline_changed.append(p.name)
    control_failed = bool(decode_err or newline_changed)
    results.append(("C", control_failed, f"decode errors: {decode_err}; newline changes on {len(newline_changed)} files: {newline_changed[:6]}"))

    for arm, ok, detail in results:
        print(f"{arm}: {'as predicted' if ok else 'NOT as predicted'} -- {detail}")
    a, b, h, c = (r[1] for r in results)
    if not c:
        print("VERDICT: method-broken (control passed)")
        return 4
    print("VERDICT:", "survived" if (a and b) else "refuted")
    return 0 if (a and b) else 1


if __name__ == "__main__":
    sys.exit(main())
