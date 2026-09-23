"""
controlar_borrador.py <id> -- controles mecanicos antes de publicar un borrador
de la redaccion programada. Los corre redaccion_programada.ps1.

Sale con 0 e imprime  ok|titulo|numero|numero_label  si:
  - el borrador esta una sola vez en data/cola.json y tiene cifra ancla;
  - existe cola/<id>.html y lleva <meta name="robots" content="noindex">;
  - cada URL de la seccion de fuentes responde con HTTP < 400.
Si no, sale con 1 e imprime el motivo.
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from verificar_enlaces import urls_de, check

def fallar(motivo):
    print(motivo)
    sys.exit(1)

def main(i):
    cola = json.load(open(os.path.join(ROOT, "data", "cola.json"), encoding="utf-8"))["borradores"]
    c = [b for b in cola if b["id"] == i]
    if len(c) != 1:
        fallar("no esta una sola vez en cola.json")
    b = c[0]
    if not str(b.get("numero", "")).strip():
        fallar("sin cifra ancla")
    f = os.path.join(ROOT, "cola", i + ".html")
    if not os.path.exists(f):
        fallar("falta cola/" + i + ".html")
    if 'name="robots" content="noindex"' not in open(f, encoding="utf-8").read():
        fallar("sin noindex")
    malas = []
    for u in urls_de(f):
        s = check(u)
        if not isinstance(s, int) or s >= 400:
            malas.append(f"{u} ({s})")
    if malas:
        fallar("fuentes que no responden: " + " | ".join(malas))
    limpio = lambda t: str(t).replace("|", "/").replace('"', "'")
    print("ok|" + "|".join(limpio(b.get(k, "")) for k in ("titulo", "numero", "numero_label")))

if __name__ == "__main__":
    if len(sys.argv) != 2:
        fallar("uso: python agente/local/controlar_borrador.py <id>")
    main(sys.argv[1])
