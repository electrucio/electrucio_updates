#!/usr/bin/env python3
"""Ejecutar LTspice en batch desde la CLI de macOS, sin GUI.

Se encarga de las tres cosas que hacen fallar el CLI silenciosamente:

1. El netlist tiene que ser el ULTIMO argumento (`LTspice -ascii -b f.net`);
   `-b -ascii f.net` falla con `Can't find input deck "-ascii"`.
2. El CLI NO busca en la carpeta de librerias de LTspice como hace la GUI:
   los `.lib` relativos hay que pasarlos a ruta absoluta.
3. Los netlists exportados por la GUI vienen en UTF-16LE y con caracteres
   no-ASCII (`µ`, `R§F1`) que rompen cualquier herramienta de texto.

Ademas: `-b` solo funciona con netlists, no con `.asc` (este build trata
cualquier fichero como netlist y muere con `Multiple instances of "Flag"`).
Para obtener el .net de un .asc: abrir la GUI una vez, o `LTspice -netlist f.asc`.

Uso tipico:
    from ltrun import Netlist, run_batch
    n = Netlist.from_file("powersupply/psu.net")     # detecta UTF-16 solo
    n.patch(".tran 0 7 0 2m startup", ".tran 0 0.8 0 20u startup")
    n.save_vars("V(vload) I(RLOAD)")
    raw = run_batch(n.write(workdir / "prueba.net"))

O directamente:
    python3 ltrun.py powersupply/psu.net            # prepara y simula
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

LTSPICE = os.environ.get(
    "LTSPICE", "/Applications/LTspice.app/Contents/MacOS/LTspice")
LIBDIR = Path(os.path.expanduser(
    "~/Library/Application Support/LTspice/lib"))


def _to_ascii(s: str) -> str:
    """Transliterar a ASCII: µ->u en valores, y quitar acentos de comentarios."""
    s = s.replace("µ", "u").replace("μ", "u").replace("Ω", "ohm")
    s = re.sub(r"R§F(\d)", r"RF\1", s)            # R§F1 -> RF1
    s = re.sub(r"([A-Za-z])§", r"\1", s)          # cualquier otro § en nombres
    return (unicodedata.normalize("NFKD", s)
            .encode("ascii", "replace").decode("ascii"))


class Netlist:
    """Netlist en memoria, con parcheo que falla a gritos si no encuentra el texto."""

    def __init__(self, text: str, origin: Path | None = None):
        self.text = text
        self.origin = origin

    # ---------------------------------------------------------------- carga
    @classmethod
    def from_file(cls, path) -> "Netlist":
        path = Path(path)
        blob = path.read_bytes()
        if blob[:2] in (b"\xff\xfe", b"*\x00") or blob.count(b"\x00") > len(blob) // 4:
            text = blob.decode("utf-16-le", "replace").lstrip("﻿")
        else:
            text = blob.decode("utf-8", "replace")
        return cls(_to_ascii(text), origin=path)

    # -------------------------------------------------------------- parcheo
    def patch(self, old: str, new: str, count: int = 1) -> "Netlist":
        """Reemplaza `old` por `new`. Revienta si no aparece exactamente `count` veces."""
        n = self.text.count(old)
        if n != count:
            raise AssertionError(
                f"patch: {old!r} aparece {n} veces, esperaba {count}"
                + (f" en {self.origin}" if self.origin else ""))
        self.text = self.text.replace(old, new)
        return self

    def drop_re(self, pattern: str, min_count: int = 1) -> "Netlist":
        """Borra las lineas que casan `pattern`. Revienta si casan menos de `min_count`.

        Para tirar bloques enteros de directivas (`.meas tran`, `.four`) cuando se
        cambia el tipo de analisis. Como `patch()`, falla a gritos: si el
        esquematico deja de tener esas lineas, se nota aqui.
        """
        rx = re.compile(pattern, re.I)
        kept = [l for l in self.text.splitlines(True) if not rx.match(l)]
        n = len(self.text.splitlines(True)) - len(kept)
        if n < min_count:
            raise AssertionError(
                f"drop_re: {pattern!r} casa {n} lineas, esperaba >= {min_count}"
                + (f" en {self.origin}" if self.origin else ""))
        self.text = "".join(kept)
        return self

    def absolutize_libs(self, extra_dirs=()) -> "Netlist":
        """Convierte `.lib foo.sub` / `.include` relativos en rutas absolutas."""
        # absolutas siempre: el .net se simula con cwd en su propio directorio,
        # asi que una ruta relativa que exista aqui no existira alli
        dirs = [Path(d).resolve() for d in extra_dirs]
        if self.origin:
            dirs.insert(0, self.origin.resolve().parent)
        dirs += [LIBDIR / "sub", LIBDIR / "cmp"]

        def repl(m):
            kw, name = m.group(1), m.group(2).strip().strip('"')
            if Path(name).is_absolute():
                return m.group(0)
            for d in dirs:
                if (d / name).exists():
                    return f"{kw} {d / name}"
            print(f"  aviso: no encuentro la libreria {name!r}", file=sys.stderr)
            return m.group(0)

        self.text = re.sub(r"(?im)^(\.lib|\.inc(?:lude)?)\s+(.+?)\s*$",
                           repl, self.text)
        return self

    def save_vars(self, *specs: str) -> "Netlist":
        """Añade `.save` (raw pequeño y rapido de parsear) + plotwinsize=0."""
        lines = "".join(f".save {s}\n" for s in specs)
        return self._prepend_to_end(lines + ".options plotwinsize=0\n")

    def add(self, *lines: str) -> "Netlist":
        return self._prepend_to_end("".join(l.rstrip() + "\n" for l in lines))

    def _prepend_to_end(self, block: str) -> "Netlist":
        for anchor in (".backanno", ".end"):
            if anchor in self.text:
                i = self.text.index(anchor)
                self.text = self.text[:i] + block + self.text[i:]
                return self
        self.text += block
        return self

    # -------------------------------------------------------------- escritura
    def write(self, path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_to_ascii(self.text), encoding="ascii")
        return path


def run_batch(net: Path, ascii_raw: bool = False, timeout: int = 900) -> Path:
    """Simula `net` y devuelve la ruta del .raw. Lanza RuntimeError si falla.

    Nota: si tu shell corre en sandbox hay que desactivarlo; sandboxeado el
    proceso muere con exit 144 sin escribir ni el .log.
    """
    net = Path(net)
    if not Path(LTSPICE).exists():
        raise RuntimeError(f"no encuentro LTspice en {LTSPICE} "
                           "(exporta LTSPICE=/ruta/al/binario)")
    cmd = [LTSPICE] + (["-ascii"] if ascii_raw else []) + ["-b", net.name]
    r = subprocess.run(cmd, cwd=net.parent, capture_output=True,
                       text=True, timeout=timeout)
    log, raw = net.with_suffix(".log"), net.with_suffix(".raw")
    if r.returncode != 0 or not raw.exists():
        tail = ""
        if log.exists():
            from rawread import read_log
            tail = "\n".join(read_log(log).splitlines()[-12:])
        raise RuntimeError(
            f"LTspice fallo en {net.name} (exit {r.returncode})\n"
            f"{r.stdout}{r.stderr}\n--- cola del .log ---\n{tail}")
    return raw


def netlist_from_asc(asc: Path) -> Path:
    """Genera el .net de un .asc. OJO: sobrescribe <asc>.net si ya existe."""
    asc = Path(asc)
    r = subprocess.run([LTSPICE, "-netlist", asc.name],
                       cwd=asc.parent, capture_output=True, text=True)
    net = asc.with_suffix(".net")
    if not net.exists():
        raise RuntimeError(f"-netlist no genero {net}: {r.stdout}{r.stderr}")
    return net


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    src = Path(argv[1])
    workdir = Path(argv[2]) if len(argv) > 2 else Path(
        os.environ.get("TMPDIR", "/tmp")) / "ltspice_sim"
    n = Netlist.from_file(src).absolutize_libs()
    net = n.write(workdir / src.name)
    print(f"preparado {net}")
    raw = run_batch(net)
    print(f"simulado  {raw}  ({raw.stat().st_size/1e6:.1f} MB)")
    subprocess.run([sys.executable,
                    str(Path(__file__).parent / "rawread.py"), str(raw)])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
