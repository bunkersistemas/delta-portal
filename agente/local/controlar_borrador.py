"""
controlar_borrador.py <id> -- controles mecanicos antes de publicar un borrador
de la redaccion programada. Los corre redaccion_programada.ps1.

Sale con 0 e imprime  ok|titulo|numero|numero_label  si:
  - el borrador esta una sola vez en data/cola.json y tiene cifra ancla;
  - existe cola/<id>.html y lleva <meta name="robots" content="noindex">;
  - cada URL de la seccion de fuentes responde con HTTP < 400.

Si no, imprime el motivo y sale con:
  1 = falla DEFINITIVA: el borrador esta mal armado o una fuente no existe
      (404 / 410). No se arregla esperando: se rechaza.
  3 = TITULAR: la nota puede estar bien, pero el titular es una pregunta y
      hoy ya se paso el tope (scripts/titulares.py). No se rechaza ni se
      reintenta sola: queda en la cola para que el editor la retitule.
  2 = falla TRANSITORIA: una fuente no respondio a tiempo, o contesto 403, 429
      o 5xx (antibot, sobrecarga). La nota puede estar bien: se reintenta en
      la corrida siguiente.

Por que la diferencia (24/09/2026): el servidor del Tesoro de EE.UU. tarda
~33 s en contestar. Con 15 s + 20 s el control dio "no responde", el borrador
quedo sin commitear y la redaccion quedo trabada 9 corridas seguidas por una
nota que estaba bien.
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from verificar_enlaces import urls_de, check
import titulares

DEFINITIVOS = (404, 410)

def fallar(motivo, codigo=1):
    print(motivo)
    sys.exit(codigo)

def estado(u):
    """('ok'|'rota'|'lenta', detalle). Una fuente que no contesta se prueba
    una segunda vez con mas tiempo antes de darla por lenta."""
    s = check(u)
    if not (isinstance(s, int) and s < 400):
        s = check(u, t_head=20, t_get=60)
    if isinstance(s, int) and s < 400:
        return "ok", s
    m = re.match(r"HTTP Error (\d{3})", str(s))
    if (isinstance(s, int) and s in DEFINITIVOS) or (m and int(m.group(1)) in DEFINITIVOS):
        return "rota", s
    return "lenta", s

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
    p = titulares.problemas(b["titulo"], titulares.del_dia(titulares.publicadas(), b.get("fecha") or titulares.hoy_ar()))
    if p:
        fallar("titular en forma de pregunta: " + "; ".join(p), 3)
    rotas, lentas = [], []
    for u in urls_de(f):
        e, s = estado(u)
        if e == "rota":
            rotas.append(f"{u} ({s})")
        elif e == "lenta":
            lentas.append(f"{u} ({s})")
    if rotas:
        fallar("fuentes que no existen: " + " | ".join(rotas + lentas))
    if lentas:
        fallar("fuentes que no respondieron (se reintenta): " + " | ".join(lentas), 2)
    limpio = lambda t: str(t).replace("|", "/").replace('"', "'")
    print("ok|" + "|".join(limpio(b.get(k, "")) for k in ("titulo", "numero", "numero_label")))

if __name__ == "__main__":
    if len(sys.argv) != 2:
        fallar("uso: python agente/local/controlar_borrador.py <id>")
    main(sys.argv[1])
