#!/usr/bin/env python3
"""Build asc_viewer.html (standalone drag&drop LTspice .asc viewer).

Injects __SYMLIB__ (standard LTspice .asy geometries) into
tools/asc_viewer_template.html. Project-local symbols (e.g. the custom
pots) are NOT embedded by default — schematics using them show a
missing-symbol placeholder until the .asy files are dropped onto the
page. Pass --with-local-syms to embed them too.
"""
import os, sys, json, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYMDIR = os.path.expanduser("~/Library/Application Support/LTspice/lib/sym")

def read_lt(path):
    b = open(path, "rb").read()
    if b.startswith(b"\xff\xfe"): return b.decode("utf-16-le")
    if b.startswith(b"\xfe\xff"): return b.decode("utf-16-be")
    if b[1:2] == b"\x00": return b.decode("utf-16-le")
    return b.decode("utf-8", "replace")

KEEP = ("LINE ", "RECTANGLE ", "CIRCLE ", "ARC ", "TEXT ", "PIN ",
        "WINDOW ", "SYMATTR Value", "SYMATTR Prefix")

def trim_asy(text):
    return "\n".join(l.rstrip() for l in text.splitlines() if l.startswith(KEEP))

lib = {}
for n in ("res res2 cap polcap ind ind2 diode zener schottky LED npn pnp "
          "npn2 pnp2 nmos pmos nmos4 pmos4 njf pjf voltage current bv bi "
          "e e2 g sw csw varactor").split():
    p = os.path.join(SYMDIR, n + ".asy")
    if os.path.exists(p): lib[n] = trim_asy(read_lt(p))
if "--with-local-syms" in sys.argv:
    for p in glob.glob(os.path.join(ROOT, "guitar_amplifier/ltspice/*.asy")):
        lib[os.path.splitext(os.path.basename(p))[0]] = trim_asy(read_lt(p))

tpl = open(os.path.join(ROOT, "tools/asc_viewer_template.html")).read()
out = tpl.replace("__SYMLIB__", json.dumps(lib).replace("</", "<\\/"))
dst = os.path.join(ROOT, "asc_viewer.html")
open(dst, "w").write(out)
print(f"wrote {dst} ({os.path.getsize(dst)} bytes, {len(lib)} symbols)")
