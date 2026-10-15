#!/usr/bin/env python3
"""
controlar_narrativa.py -- control del paso "editor de narrativa" (15/10/2026).
Compara una nota original con su version reescrita y verifica que SOLO cambio la forma:
  - ningun numero del texto visible nuevo que no estuviera en el original (incluidos los de un digito
    cuando llevan % o $, que es donde un error cuesta);
  - las citas textuales entre comillas del original siguen identicas;
  - mismos hrefs, misma cantidad de <figure>, <script>, <table>, y mismos graficos/tablas (contenido);
  - capa 4, pie y <head> identicos, bloques b1..b6 y botones data-go intactos;
  - titulo <= 110 y, si la nota no es pedida, sin forma de pregunta; si es pedida, sigue siendo pregunta;
  - etiquetas balanceadas;
  - con --informe: toda frase NUEVA que afirme orden, causa, comparacion o generalizacion (primero, unico,
    todos, por eso, mismo sentido...) tiene que venir declarada en "afirmaciones_nuevas" con la frase
    textual del original que la respalda.
Uso:  python controlar_narrativa.py <original.html> <nueva.html> [--informe <narrativa.json>]
        (exit 0 = OK, 1 = FALLA)
      python controlar_narrativa.py --autotest <original.html>      (prueba que el control PUEDE fallar)
Archivo en ASCII puro: las comillas curvas y las tildes se arman con chr().
"""
import html, io, json, re, sys, unicodedata

CA, CC = chr(0x201C), chr(0x201D)   # comillas curvas


def leer(p):
    return io.open(p, encoding="utf-8").read()


def visible(t):
    t = re.sub(r"(?s)<(script|style)[^>]*>.*?</\1>", " ", t)
    t = re.sub(r"(?s)<!--.*?-->", " ", t)
    return html.unescape(re.sub(r"<[^>]+>", " ", t))


def numeros(t):
    """Numeros normalizados (sin separadores). Un digito solo cuenta si lleva % o va tras $ / US$."""
    out = set()
    for m in re.finditer(r"(?<![\w])(US\$|\$)?\s?(\d[\d.,]*\d|\d)(\s?%)?", t):
        crudo = re.sub(r"[.,]", "", m.group(2))
        if len(crudo) == 1 and not (m.group(1) or m.group(3)):
            continue
        out.add(m.group(2).strip(".,"))
        out.add(crudo)
    return out


def citas(t):
    pat = "[" + CA + '"]([^' + CC + '"]{12,300})[' + CC + '"]'
    return [re.sub(r"\s+", " ", c).strip() for c in re.findall(pat, visible(t))]


def bloque(t, i):
    m = re.search(r'(?s)<div class="block[^"]*" id="b%d">.*?(?=<div class="block[^"]*" id="b%d">|</article>)' % (i, i + 1), t)
    return m.group(0) if m else ""


def h1(t):
    m = re.search(r"(?s)<h1>(.*?)</h1>", t)
    return html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""


# ---- afirmaciones nuevas: lo que el control de numeros no ve ----
BANDERAS = re.compile(
    r"\b(primer[oa]s?|ultim[oa]s?|unic[oa]s?|todos|todas|ninguno|ninguna|nadie|siempre|nunca|mayor(?:es)?|"
    r"menor(?:es)?|mejor(?:es)?|peor(?:es)?|record|por eso|porque|debido|a pesar|gracias a|causa|"
    r"mismo sentido|mismas?|mas que|menos que|el doble|la mitad)\b", re.I)


def norm(t):
    t = unicodedata.normalize("NFD", html.unescape(t).lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9%$]+", " ", t).strip()


def oraciones(t):
    cuerpo = t.split("<h1>", 1)[-1]
    return [re.sub(r"\s+", " ", x).strip() for x in re.split(r"(?<=[.?!])\s+|\n+", visible(cuerpo)) if x.strip()]


def afirmaciones(o, n, informe):
    """Errores: frases nuevas con bandera sin declarar, y respaldos declarados que no estan en el original."""
    errs = []
    decl = (informe or {}).get("afirmaciones_nuevas") or []
    texto_o = norm(" ".join(oraciones(o)))
    for d in decl:
        r = norm(str(d.get("respaldo_en_el_original", "")))
        if len(r) < 25 or r not in texto_o:
            errs.append("respaldo declarado que no esta (textual) en el original: " + str(d.get("frase", ""))[:70])
    declaradas = [norm(str(d.get("frase", ""))) for d in decl if d.get("frase")]
    viejas = set(norm(x) for x in oraciones(o))
    for x in oraciones(n):
        nx = norm(x)
        if nx in viejas or not BANDERAS.search(norm(x)):
            continue
        if not any(d and (d in nx or nx in d) for d in declaradas):
            errs.append("frase nueva con afirmacion no declarada: " + x[:110])
    return errs


def revisar(o, n, informe=None):
    errs = []
    nuevos = sorted(numeros(visible(n)) - numeros(visible(o)))
    if nuevos:
        errs.append("numeros que no estan en el original: " + ", ".join(nuevos[:15]))
    todas_n = " ".join(citas(n))
    perdidas = [c for c in citas(o) if c not in todas_n]
    if perdidas:
        errs.append("citas textuales que cambiaron o faltan: " + " | ".join(p[:60] for p in perdidas[:4]))
    for i in range(1, 7):
        if 'id="b%d"' % i not in n:
            errs.append("falta el bloque b%d" % i)
    if re.findall(r'data-go="(b\d)"', o) != re.findall(r'data-go="(b\d)"', n):
        errs.append("cambiaron los botones data-go")
    for etq in ("<figure", "<script", "<table"):
        if o.count(etq) != n.count(etq):
            errs.append("cambio la cantidad de %s: %d -> %d" % (etq, o.count(etq), n.count(etq)))
    if sorted(re.findall(r'href="([^"]+)"', o)) != sorted(re.findall(r'href="([^"]+)"', n)):
        errs.append("cambiaron los links (href)")
    g = lambda t: sorted(re.findall(r"(?s)<svg.*?</svg>|<table.*?</table>", t))
    if g(o) != g(n):
        errs.append("se toco el contenido de un grafico o una tabla")
    if bloque(o, 4) != bloque(n, 4):
        errs.append("se toco la capa 4 'Como lo sabemos'")
    if o.split("<footer>")[-1] != n.split("<footer>")[-1]:
        errs.append("se toco el pie")
    head = lambda t: re.sub(r"(?s)<title>.*?</title>", "", t.split("</head>")[0])
    if head(o) != head(n):
        errs.append("se toco el <head> (salvo el <title>)")
    to, tn = h1(o), h1(n)
    pedido = 'class="pedido"' in o
    if len(tn) > 110 and tn != to:
        errs.append("titulo de %d caracteres (max 110)" % len(tn))
    if pedido and "?" not in tn:
        errs.append("la nota es pedida: el titulo tiene que seguir siendo la pregunta del lector")
    if not pedido and "?" in tn and "?" not in to:
        errs.append("titulo en forma de pregunta en una nota que no es pedida")
    for etq in ("div", "details", "p", "h2", "h3", "h4", "li", "ul"):
        a, b = len(re.findall(r"<%s[\s>]" % etq, n)), len(re.findall(r"</%s>" % etq, n))
        if a != b:
            errs.append("etiquetas <%s> desbalanceadas (%d abren, %d cierran)" % (etq, a, b))
    if informe is not None:
        errs += afirmaciones(o, n, informe)
    return errs


def autotest(o):
    """Tiene que dar FALLA con un numero inventado, un porcentaje de un digito, una cita alterada, un link
    cambiado y una afirmacion nueva sin declarar; y OK sin tocar nada."""
    digito = next((d for d in "9876543" if d + "%" not in visible(o)), "9")
    casos = {
        "numero inventado": o.replace("</p>", " La cifra inventada es 7654321.</p>", 1),
        "porcentaje de un digito inventado": o.replace("</p>", " Subio %s%%.</p>" % digito, 1),
        "link cambiado": o.replace('href="http', 'href="httpx', 1),
        "afirmacion nueva sin declarar": o.replace("</p>", " Fue el primero en moverse y por eso nadie lo siguio.</p>", 1),
    }
    cit = citas(o)
    if cit:
        casos["cita alterada"] = o.replace(cit[0][:20], cit[0][:20] + " (alterada)", 1)
    ok_idem = not revisar(o, o, {})
    detecta = {k: bool(revisar(o, v, {})) for k, v in casos.items()}
    # y si la declara con respaldo textual, pasa (el control no es un "no" a todo)
    frase = "Fue el primero en moverse y por eso nadie lo siguio."
    soporte = oraciones(o)[3]
    declarada = o.replace("</p>", " " + frase + "</p>", 1)
    inf = {"afirmaciones_nuevas": [{"frase": frase, "respaldo_en_el_original": soporte}]}
    admite = not [e for e in revisar(o, declarada, inf) if "afirmacion" in e or "respaldo" in e]
    return ok_idem, detecta, admite


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    if "--autotest" in sys.argv:
        ok_idem, det, admite = autotest(leer(a[0]))
        print("sin cambios -> OK:", ok_idem)
        for k, v in det.items():
            print("detecta %-34s %s" % (k, "SI" if v else "NO  <- control invalido"))
        print("admite una afirmacion declarada con respaldo textual:", admite)
        sys.exit(0 if ok_idem and all(det.values()) and admite else 1)
    informe = None
    if "--informe" in sys.argv:
        ruta = sys.argv[sys.argv.index("--informe") + 1]
        a = [x for x in a if x != ruta]
        informe = json.load(io.open(ruta, encoding="utf-8"))
    errs = revisar(leer(a[0]), leer(a[1]), informe)
    print("FALLA" if errs else "OK")
    for e in errs:
        print("   x " + e)
    sys.exit(1 if errs else 0)
