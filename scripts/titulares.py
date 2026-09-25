#!/usr/bin/env python3
"""
titulares.py -- tope de titulares en forma de pregunta por dia.

Por que existe (25/09/2026): el 24/09 el Editor paso a priorizar "la pregunta
de plata que la gente busca en Google" (cuanto cobra, cuanto cuesta). El agente
lo tomo como FORMA del titular y no como criterio de TEMA: el 25/09, 8 de las
11 notas publicadas arrancaban con "Cuanto". La portada parecia un portal de
chimentos. La pregunta que busca la gente va en "titulo_busqueda" (<title> y
redes, lo que lee Google); el titular de la portada arranca con el dato.

Reglas, sobre las notas PUBLICADAS del mismo dia (data/articulos.json):
  R1  como maximo MAX_PREGUNTAS titulares en forma de pregunta por dia;
  R2  nunca dos preguntas seguidas (la ultima publicada del dia y esta).
Es pregunta si arranca con signo de pregunta o con un interrogativo acentuado
(Cuanto, Que, Como, Quien, Cual, Donde, Cuando, Por que): "Cuanto te devuelven
por los cortes de luz: ..." es la misma forma aunque no lleve el signo.

Uso:
  python scripts/titulares.py                  titulares de hoy y cupo que queda
  python scripts/titulares.py "<titulo>"       si ese titulo entraria hoy
  python scripts/titulares.py --borrador <id>  control de un borrador de la cola
                                               (sale 1 si no pasa)
  python scripts/titulares.py --calibrar       las reglas contra la historia
  python scripts/titulares.py --autotest       casos sinteticos, buenos y malos
"""
import datetime, json, os, sys, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_PREGUNTAS = 2
INTERROGATIVOS = ("cuánto", "cuánta", "cuántos", "cuántas", "qué", "cómo",
                  "quién", "quiénes", "cuál", "cuáles", "dónde", "cuándo")


def hoy_ar():
    return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)).date().isoformat()


def es_pregunta(titulo):
    t = str(titulo).strip().lstrip("\"'“«").strip()
    if t.startswith("¿"):
        return True
    p = t.lower().split()
    if not p:
        return False
    if p[0].strip(":,") in INTERROGATIVOS:
        return True
    return len(p) > 1 and p[0] == "por" and p[1].strip(":,?") == "qué"


def publicadas():
    arts = json.load(open(os.path.join(ROOT, "data", "articulos.json"), encoding="utf-8"))["articulos"]
    return arts


def del_dia(arts, fecha):
    """Notas publicadas ese dia, de la mas vieja a la mas nueva."""
    d = [a for a in arts if a.get("fecha") == fecha]
    return sorted(d, key=lambda a: str(a.get("hora", "")))


def problemas(titulo, previas):
    """Lista de motivos por los que `titulo` no entra despues de `previas`
    (publicadas del mismo dia, en orden). Vacia = entra."""
    if not es_pregunta(titulo):
        return []
    out = []
    n = sum(1 for a in previas if es_pregunta(a["titulo"]))
    if n >= MAX_PREGUNTAS:
        out.append(f"ya hay {n} titulares en forma de pregunta hoy (tope {MAX_PREGUNTAS})")
    if previas and es_pregunta(previas[-1]["titulo"]):
        out.append("la ultima nota publicada hoy tambien es una pregunta: "
                   + previas[-1]["titulo"][:70])
    return out


def ayuda_reescribir():
    return ("reescribi el titular arrancando con el dato o el hecho, y deja la pregunta "
            "que busca la gente en \"titulo_busqueda\"")


def listar(fecha):
    d = del_dia(publicadas(), fecha)
    n = sum(1 for a in d if es_pregunta(a["titulo"]))
    print(f"Titulares publicados el {fecha}: {len(d)}, en forma de pregunta: {n} (tope {MAX_PREGUNTAS})")
    for a in d:
        print(("  [?] " if es_pregunta(a["titulo"]) else "      ") + a.get("hora", "") + "  " + a["titulo"])
    quedan = max(0, MAX_PREGUNTAS - n)
    seguida = bool(d) and es_pregunta(d[-1]["titulo"])
    print(f"Quedan {quedan} pregunta(s) para hoy" + (" (pero la ultima ya es pregunta: la proxima no)" if seguida else ""))


def controlar_borrador(i):
    cola = json.load(open(os.path.join(ROOT, "data", "cola.json"), encoding="utf-8"))["borradores"]
    c = [b for b in cola if b["id"] == i]
    if len(c) != 1:
        print("no esta una sola vez en cola.json")
        return 1
    b = c[0]
    fecha = b.get("fecha") or hoy_ar()
    p = problemas(b["titulo"], del_dia(publicadas(), fecha))
    if p:
        print("titular en forma de pregunta: " + "; ".join(p) + ". " + ayuda_reescribir())
        return 1
    return 0


def calibrar():
    """Rehace cada dia en el orden en que se publico y cuenta que habria frenado."""
    arts = publicadas()
    dias = sorted({a.get("fecha") for a in arts if a.get("fecha")})
    total = frenadas = 0
    for f in dias:
        d = del_dia(arts, f)
        fr = [a for k, a in enumerate(d) if problemas(a["titulo"], d[:k])]
        total += len(d)
        frenadas += len(fr)
        if fr:
            print(f"{f}: {len(fr)} de {len(d)} frenadas")
            for a in fr:
                print("    " + a["titulo"][:100])
    print(f"Universo: {len(dias)} dias, {total} notas. Habria frenado {frenadas}.")
    if total == 0:
        print("FALLA: calibracion sobre cero notas")
        return 1
    return 0


def autotest():
    P = lambda t: {"titulo": t, "hora": "10:00"}
    casos = [
        # (titulo, previas, debe_pasar, que prueba)
        ("La inflacion bajo a 1,7%", [P("¿Cuánto?"), P("¿Cuánto más?")], True, "afirmacion con el cupo lleno"),
        ("¿Cuánto cobra X?", [], True, "primera pregunta del dia"),
        ("¿Cuánto cobra X?", [P("¿Cuánto cuesta Y?")], False, "dos preguntas seguidas"),
        ("¿Cuánto cobra X?", [P("¿A?"), P("B"), P("¿C?"), P("D")], False, "tercera pregunta del dia"),
        ("¿Cuánto cobra X?", [P("¿A?"), P("B")], True, "segunda pregunta, no seguida"),
        ("Cuánto te devuelven por los cortes", [P("¿A?")], False, "pregunta sin signo, seguida"),
        ("Por qué sube el dólar", [P("¿A?")], False, "'por que' con tilde es pregunta"),
        ("Por cada año trabajado, una pyme junta", [P("¿A?")], True, "'por' sin 'que' no es pregunta"),
        ("Cuanto antes, mejor: el BCRA", [P("¿A?")], True, "'cuanto' sin tilde no es interrogativo"),
        ("Qué", [P("¿A?")], False, "interrogativo solo, seguido"),
        ("Qué", [P("¿A?"), P("B")], True, "interrogativo solo, con cupo y no seguido"),
    ]
    mal = 0
    for t, prev, ok, que in casos:
        paso = not problemas(t, prev)
        if paso != ok:
            mal += 1
            print(f"FALLA: {que}: esperaba {'pasa' if ok else 'frena'}, dio {'pasa' if paso else 'frena'}")
    frenan = sum(1 for c in casos if not c[2])
    print(f"autotest: {len(casos)} casos ({frenan} que deben frenar, {len(casos) - frenan} que deben pasar), {mal} fallas")
    return 1 if mal else 0


if __name__ == "__main__":
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    a = sys.argv[1:]
    if not a:
        listar(hoy_ar())
    elif a[0] == "--borrador" and len(a) == 2:
        sys.exit(controlar_borrador(a[1]))
    elif a[0] == "--calibrar":
        sys.exit(calibrar())
    elif a[0] == "--autotest":
        sys.exit(autotest())
    else:
        t = " ".join(a)
        p = problemas(t, del_dia(publicadas(), hoy_ar()))
        print("ENTRA" if not p else "NO ENTRA: " + "; ".join(p) + ". " + ayuda_reescribir())
        sys.exit(1 if p else 0)
