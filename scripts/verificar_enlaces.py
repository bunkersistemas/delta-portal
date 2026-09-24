#!/usr/bin/env python3
"""
verificar_enlaces.py — Barrida de TODOS los enlaces de fuentes de las notas.

Recorre articulos/*.html, extrae las URLs de la sección "Fuentes y
transparencia" (footer) y verifica que cada una devuelva HTTP < 400.
Imprime un informe con las que fallan. Lo usa el auditor semanal
(agente/AUDITORIA.md) y puede correrse a mano.

Uso:  python3 scripts/verificar_enlaces.py [--todas]
      (--todas incluye también los enlaces del cuerpo de la nota)
"""
import glob, os, re, sys, urllib.request
from html import unescape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {"User-Agent": "Mozilla/5.0 (ConInteres verificador de fuentes; +https://coninteres.com/como-trabajamos.html)"}

def urls_de(path, todas=False):
    html = open(path, encoding="utf-8").read()
    zona = html
    if not todas:
        i = html.find("Fuentes y transparencia")
        if i == -1:
            i = html.find("<footer")
        zona = html[i:] if i != -1 else html
    # el href viene escapado (&amp;): se pide la URL real, la que abre el lector
    return sorted(set(unescape(u) for u in re.findall(r'href="(https?://[^"]+)"', zona)))

def check(url, t_head=15, t_get=20):
    try:
        req = urllib.request.Request(url, headers=UA, method="HEAD")
        with urllib.request.urlopen(req, timeout=t_head) as r:
            return r.status
    except Exception:
        # algunos servidores rechazan HEAD: reintentar con GET
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=t_get) as r:
                return r.status
        except Exception as e:
            return str(e)[:80]

def main():
    todas = "--todas" in sys.argv
    fallas, total = [], 0
    for f in sorted(glob.glob(os.path.join(ROOT, "articulos", "*.html"))):
        for u in urls_de(f, todas):
            if "coninteres.com" in u:
                continue
            total += 1
            st = check(u)
            ok = isinstance(st, int) and st < 400
            print(("OK " if ok else "FALLA ") + os.path.basename(f) + "  " + u + ("" if ok else f"  [{st}]"))
            if not ok:
                fallas.append((os.path.basename(f), u, st))
    print(f"\n== {total} enlaces verificados · {len(fallas)} con falla ==")
    for n, u, st in fallas:
        print(f"  {n}: {u}  [{st}]")
    sys.exit(1 if fallas else 0)

if __name__ == "__main__":
    main()
