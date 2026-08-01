#!/usr/bin/env python3
"""Build poweramp_xview.html: LTspice schematic + PCB cross-net viewer.

Injects into tools/xview_template.html:
  __SYMLIB__  LTspice .asy symbol geometries (std lib + repo-local symbols)
  __ASC__     guitar_amplifier/ltspice/AudioAmpCompl-40W.asc (decoded)
  __NET__     guitar_amplifier/ltspice/AudioAmpCompl-40W.net.txt (decoded)
  __PCB__     tools/pcbdata.json (extracted from "poweramp BOM.html" ibom blob)
  __MAP__     LTspice node -> KiCad net table (from poweramp_net_mapping.md)
"""
import os, json, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYMDIR = os.path.expanduser("~/Library/Application Support/LTspice/lib/sym")

# LTspice node <-> KiCad net, per poweramp_net_mapping.md (+ Q5B, the one
# net the table omitted; verified against the netlist: R13/Q5 base node)
NODE2PCB = {
    "Q6C": "/POW", "N008": "/POW1", "N009": "/POW2",
    "N017": "Net-(PREAMP1-Pin_1)",
    "Q1B": "Net-(Q1-B)", "Q2B": "Net-(Q1-C)", "Q1E": "Net-(Q1-E)",
    "FEEDBACK": "Net-(C4-Pad2)", "Q2C": "Net-(Q2-C)", "N024": "Net-(C7-Pad1)",
    "Q3C": "Net-(Q3-C)", "Q3B": "Net-(Q3-B)",
    "N010": "Net-(R7-Pad2)", "N011": "Net-(R8-Pad1)",
    "BOOTSTRAP": "Net-(C8-Pad1)",
    "Q4B": "Net-(Q4-B)", "Q6B": "Net-(Q4-E)", "Q6E": "Net-(Q6-E)",
    "Q7B": "Net-(Q5-C)", "Q5B": "Net-(Q5-B)",
    "Q5E": "Net-(D10-K)", "Q7C": "Net-(D10-A)",
    "PRE_SPEAKER": "Net-(C10-Pad1)", "SPEAKER": "Net-(SPEAKER1-Pin_1)",
    "N015": "Net-(C9-Pad2)", "0": "0",
}

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

def js(value):  # JSON that is safe inside a <script> block
    return json.dumps(value, separators=(",", ":")).replace("</", "<\\/")

def main():
    lib = {}
    for n in ("res res2 cap polcap ind ind2 diode zener schottky LED npn pnp "
              "npn2 pnp2 nmos pmos nmos4 pmos4 njf pjf voltage current bv bi "
              "e e2 g sw csw varactor").split():
        p = os.path.join(SYMDIR, n + ".asy")
        if os.path.exists(p): lib[n] = trim_asy(read_lt(p))
    for p in glob.glob(os.path.join(ROOT, "guitar_amplifier/ltspice/*.asy")):
        lib[os.path.splitext(os.path.basename(p))[0]] = trim_asy(read_lt(p))

    asc = read_lt(os.path.join(ROOT, "guitar_amplifier/ltspice/AudioAmpCompl-40W.asc"))
    net = read_lt(os.path.join(ROOT, "guitar_amplifier/ltspice/AudioAmpCompl-40W.net.txt"))
    pcb = json.load(open(os.path.join(ROOT, "tools/pcbdata.json")))

    tpl = open(os.path.join(ROOT, "tools/xview_template.html")).read()
    out = (tpl.replace("__SYMLIB__", js(lib))
              .replace("__ASC__", js(asc.lstrip("﻿")))
              .replace("__NET__", js(net.lstrip("﻿")))
              .replace("__PCB__", js(pcb))
              .replace("__MAP__", js(NODE2PCB)))
    dst = os.path.join(ROOT, "poweramp_xview.html")
    open(dst, "w").write(out)
    print(f"wrote {dst} ({os.path.getsize(dst)} bytes, {len(lib)} symbols)")

if __name__ == "__main__":
    main()
