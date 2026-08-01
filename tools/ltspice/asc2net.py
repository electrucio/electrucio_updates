#!/usr/bin/env python3
"""Convertir un .asc de LTspice en netlist, sin abrir la GUI.

Existe porque en este equipo `LTspice -netlist fichero.asc` NO funciona en
batch: abre ventana y se queda ahi, incluso con un .asc que la GUI abre sin
problema.  Asi que para comprobar que un esquematico conecta lo que uno cree,
hay que netlistarlo por otro lado.

    python3 tools/ltspice/asc2net.py esquema.asc              # imprime el netlist
    python3 tools/ltspice/asc2net.py esquema.asc -o salida.net
    python3 tools/ltspice/asc2net.py esquema.asc --diff referencia.net

`--diff` compara componente a componente (nombre, nodos, valor) contra un
netlist de referencia, ignorando el orden de las lineas y las mayusculas.  Es
la forma de verificar que un esquematico dibujado a mano equivale a un netlist
escrito a mano.

Los pines salen de los .asy: primero del directorio del .asc, luego de
~/Library/Application Support/LTspice/lib/sym.  Soporta las ocho orientaciones
(R0/R90/R180/R270 y M0/M90/M180/M270).

Limitaciones: no interpreta .param al construir nodos (no hace falta), ni
buses, ni jerarquia.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

LIBSYM = Path.home() / "Library/Application Support/LTspice/lib/sym"

# como se transforma un offset de pin segun la orientacion del simbolo
ROT = {
    "R0":   lambda x, y: (x, y),
    "R90":  lambda x, y: (-y, x),
    "R180": lambda x, y: (-x, -y),
    "R270": lambda x, y: (y, -x),
    "M0":   lambda x, y: (-x, y),
    "M90":  lambda x, y: (-y, -x),
    "M180": lambda x, y: (x, -y),
    "M270": lambda x, y: (y, x),
}

# cuantos nodos lleva cada tipo y en que orden se escriben.  El orden es
# siempre el de SpiceOrder del .asy, asi que basta con saber el prefijo.
PREFIX_FALLBACK = {"res": "R", "cap": "C", "ind": "L", "diode": "D",
                   "voltage": "V", "current": "I", "bv": "B", "bi": "B",
                   "npn": "Q", "pnp": "Q", "sw": "S", "csw": "W"}


class Symbol:
    """Definicion de un .asy: pines ordenados por SpiceOrder y prefijo."""

    _cache: dict[str, "Symbol"] = {}

    def __init__(self, name, pins, prefix, default_value=None):
        self.name, self.pins, self.prefix = name, pins, prefix
        self.default_value = default_value

    @classmethod
    def load(cls, name, local: Path) -> "Symbol":
        key = name.lower()
        if key in cls._cache:
            return cls._cache[key]
        rel = name.replace("\\", "/") + ".asy"
        for d in (local, LIBSYM):
            p = d / rel
            if p.exists():
                sym = cls._parse(name, p)
                break
        else:
            raise FileNotFoundError(
                f"no encuentro el simbolo {name!r} ni en {local} ni en {LIBSYM}")
        cls._cache[key] = sym
        return sym

    @staticmethod
    def _parse(name, path: Path) -> "Symbol":
        pins, prefix, cur, dval = [], None, None, None
        for line in path.read_text(errors="replace").splitlines():
            t = line.split()
            if not t:
                continue
            if t[0] == "PIN":
                cur = [int(t[1]), int(t[2]), None]
                pins.append(cur)
            elif t[0] == "PINATTR" and t[1] == "SpiceOrder" and cur:
                cur[2] = int(t[2])
            elif t[0] == "SYMATTR" and len(t) > 2 and t[1] == "Prefix":
                prefix = t[2]
            elif t[0] == "SYMATTR" and len(t) > 2 and t[1] == "Value":
                dval = line.split(None, 2)[2]
        pins.sort(key=lambda p: (p[2] if p[2] is not None else 0))
        if prefix is None:
            prefix = PREFIX_FALLBACK.get(name.lower(), "X")
        return Symbol(name, [(p[0], p[1]) for p in pins], prefix, dval)


class Union:
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def join(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def parse_asc(path: Path):
    """Devuelve (wires, flags, instancias, directivas)."""
    blob = path.read_bytes()
    if blob[:2] in (b"\xff\xfe", b"V\x00") or blob.count(b"\x00") > len(blob) // 4:
        txt = blob.decode("utf-16-le", "replace").lstrip("\ufeff")
    else:
        txt = blob.decode("utf-8", "replace")
    wires, flags, insts, directives = [], [], [], []
    cur = None
    for raw in txt.splitlines():
        line = raw.strip()
        t = line.split()
        if not t:
            continue
        if t[0] == "WIRE":
            wires.append(tuple(int(v) for v in t[1:5]))
        elif t[0] == "FLAG":
            flags.append((int(t[1]), int(t[2]), " ".join(t[3:])))
        elif t[0] == "SYMBOL":
            cur = {"sym": t[1], "x": int(t[2]), "y": int(t[3]),
                   "rot": t[4] if len(t) > 4 else "R0",
                   "name": None, "value": None, "value2": None}
            insts.append(cur)
        elif t[0] == "SYMATTR" and cur is not None and len(t) > 1:
            what = t[1]
            val = line.split(None, 2)[2] if len(t) > 2 else ""
            if what == "InstName":
                cur["name"] = val
            elif what == "Value":
                cur["value"] = val
            elif what == "Value2":
                cur["value2"] = val
        elif t[0] == "TEXT":
            m = re.match(r"TEXT\s+-?\d+\s+-?\d+\s+\S+\s+\d+\s+(.*)", line)
            if m and m.group(1).startswith("!"):
                # una directiva puede llevar varias lineas separadas por \n literal
                directives += m.group(1)[1:].split("\\n")
            cur = None
    return wires, flags, insts, directives


def build_netlist(path: Path):
    local = path.parent
    wires, flags, insts, directives = parse_asc(path)

    u = Union()
    for x1, y1, x2, y2 in wires:
        u.join((x1, y1), (x2, y2))

    # nombre de red por punto etiquetado
    named = {}
    for x, y, name in flags:
        named[u.find((x, y))] = name

    # posicion de cada pin de cada instancia
    for it in insts:
        sym = Symbol.load(it["sym"], local)
        it["_sym"] = sym
        it["_pins"] = []
        for dx, dy in sym.pins:
            rx, ry = ROT[it["rot"]](dx, dy)
            it["_pins"].append((it["x"] + rx, it["y"] + ry))

    # asignar nombre de red a cada pin
    counter = [0]
    auto = {}

    def netname(pt):
        r = u.find(pt)
        if r in named:
            return named[r]
        if r not in auto:
            counter[0] += 1
            auto[r] = f"N{counter[0]:03d}"
        return auto[r]

    lines, problems = [], []
    for it in insts:
        sym, name = it["_sym"], it["name"]
        if name is None:
            problems.append(f"simbolo {sym.name} en ({it['x']},{it['y']}) sin InstName")
            continue
        if not name.upper().startswith(sym.prefix.upper()[:1]):
            name = sym.prefix[:1] + name
        nets = [netname(p) for p in it["_pins"]]
        for pt, n in zip(it["_pins"], nets):
            if u.find(pt) not in named:
                problems.append(f"{name}: pin en {pt} sin etiqueta (red {n})")
        val = it["value"] or sym.default_value or ""
        if it["value2"]:
            val += " " + it["value2"]
        lines.append(f"{name} {' '.join(nets)} {val}".rstrip())

    return lines, directives, problems


# ------------------------------------------------------------------ comparar
TOKEN = re.compile(r"\s+")


def norm_value(v: str) -> str:
    v = v.lower().replace(" ", "")
    v = v.replace("meg", "M").replace("k", "k")
    return v


def parse_net(path: Path):
    # LTspice escribe los netlists en UTF-16LE y no siempre con BOM
    blob = path.read_bytes()
    if blob[:2] in (b"\xff\xfe", b"*\x00") or blob.count(b"\x00") > len(blob) // 4:
        txt = blob.decode("utf-16-le", "replace").lstrip("\ufeff")
    else:
        txt = blob.decode("utf-8", "replace")
    out = {}
    for raw in txt.splitlines()[1:]:
        line = raw.split(";")[0].strip()
        if not line or line[0] in "*.+":
            continue
        t = TOKEN.split(line)
        out[t[0].lower()] = t[1:]
    return out


NPINS = {"r": 2, "c": 2, "l": 2, "d": 2, "v": 2, "i": 2, "b": 2,
         "q": 3, "s": 4, "w": 4}


def compare(gen_lines, ref_path: Path):
    gen = {}
    for l in gen_lines:
        t = TOKEN.split(l)
        gen[t[0].lower()] = t[1:]
    ref = parse_net(ref_path)

    only_gen = sorted(set(gen) - set(ref))
    only_ref = sorted(set(ref) - set(gen))
    diff = []
    for k in sorted(set(gen) & set(ref)):
        n = NPINS.get(k[0], None)
        g, r = gen[k], ref[k]
        if k[0] == "x":                      # subckt: el ultimo token es el modelo
            gn, gv = g[:-1], g[-1:]
            rn, rv = r[:-1], r[-1:]
        elif n:
            gn, gv = g[:n], g[n:]
            rn, rv = r[:n], r[n:]
            if k[0] == "q" and len(r) == 5:   # 4 terminales: ignorar el sustrato
                rn, rv = r[:3], r[4:]
        else:
            gn, gv, rn, rv = g, [], r, []
        if [x.lower() for x in gn] != [x.lower() for x in rn]:
            diff.append(f"  {k}: nodos {gn} vs {rn}")
        elif norm_value(" ".join(gv)) != norm_value(" ".join(rv)):
            diff.append(f"  {k}: valor {' '.join(gv)!r} vs {' '.join(rv)!r}")

    print(f"componentes: {len(gen)} en el .asc, {len(ref)} en {ref_path.name}")
    if only_gen:
        print(f"  solo en el .asc: {only_gen}")
    if only_ref:
        print(f"  solo en el .net: {only_ref}")
    if diff:
        print("  diferencias:")
        print("\n".join(diff))
    ok = not (only_gen or only_ref or diff)
    print("  => EQUIVALENTES" if ok else "  => NO equivalentes")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("asc")
    ap.add_argument("-o", "--output")
    ap.add_argument("--diff", metavar="NET")
    a = ap.parse_args()

    lines, directives, problems = build_netlist(Path(a.asc))
    if problems:
        print("AVISOS:", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)

    if a.diff:
        extra = [d for d in directives if d and not d.startswith(".")]
        return 0 if compare(lines + extra, Path(a.diff)) else 1

    text = f"* {a.asc}\n" + "\n".join(lines + directives) + "\n.end\n"
    if a.output:
        Path(a.output).write_text(text, encoding="ascii")
        print(f"escrito {a.output}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
