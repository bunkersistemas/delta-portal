#!/usr/bin/env python3
"""
comparar_narrativa.py -- arma una pagina "antes y despues" (lado a lado) de una nota reescrita por el editor de
narrativa, para que el editor la lea antes de publicar.
  python agente/local/comparar_narrativa.py <id>
Lee _privado/narrativa/<id>.original.html (lo que dejo la redaccion) y cola/<id>.html (con narrativa) o
articulos/<id>.html; escribe _privado/narrativa/<id>.antes_despues.html. Archivo en ASCII puro.
"""
import difflib, html, io, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import controlar_narrativa as cn

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def parrafos(t):
    t = t.split("<h1>", 1)[-1]
    t = re.sub(r"(?s)<(script|style|svg|table)[^>]*>.*?</\1>", "", t)
    t = re.sub(r"(?i)</(p|h\d|li)>", "\n", t)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    return [re.sub(r"\s+", " ", x).strip() for x in t.split("\n") if x.strip()]


def main():
    id_ = sys.argv[1]
    p_o = os.path.join(RAIZ, "_privado", "narrativa", id_ + ".original.html")
    p_n = os.path.join(RAIZ, "cola", id_ + ".html")
    if not os.path.exists(p_n):
        p_n = os.path.join(RAIZ, "articulos", id_ + ".html")
    o, n = parrafos(cn.leer(p_o)), parrafos(cn.leer(p_n))
    titulo = cn.h1(cn.leer(p_n))
    e = html.escape
    filas = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, o, n, autojunk=False).get_opcodes():
        if tag == "equal":
            for x in o[i1:i2]:
                filas.append('<div class="r igual"><div class="c">%s</div><div class="c">%s</div></div>' % (e(x), e(x)))
            continue
        izq, der = o[i1:i2], n[j1:j2]
        for k in range(max(len(izq), len(der))):
            l = izq[k] if k < len(izq) else ""
            r = der[k] if k < len(der) else ""
            cls = "cambia" if l and r else ("nuevo" if r else "quitado")
            filas.append('<div class="r %s"><div class="c">%s</div><div class="c">%s</div></div>' % (cls, e(l), e(r)))
    css = (
        "body{font:16px/1.55 Georgia,serif;margin:0;background:#FAF8F4;color:#16130F}"
        "header{position:sticky;top:0;background:#16130F;color:#fff;padding:10px 16px;font:600 13px Arial,sans-serif;z-index:5}"
        ".cab,.r{display:grid;grid-template-columns:1fr 1fr;gap:14px;max-width:1200px;margin:0 auto;padding:0 16px}"
        ".cab{font:700 12px Arial;letter-spacing:.1em;text-transform:uppercase;padding-top:14px;padding-bottom:6px;color:#6B6560}"
        ".r{padding-top:10px;padding-bottom:10px;border-top:1px solid #E7E1D7}.c{font-size:15.5px}"
        ".igual .c{color:#8A847C;font-size:14px}"
        ".cambia .c:last-child{background:#FFF6DC;border-left:4px solid #C4701F;padding-left:10px}"
        ".nuevo .c:last-child{background:#E3F2EC;border-left:4px solid #2E8B6F;padding-left:10px}"
        ".quitado .c:first-child{background:#FBECEA;border-left:4px solid #C0392B;padding-left:10px}"
        ".leyenda{max-width:1200px;margin:0 auto;padding:12px 16px;font:13px Arial;color:#3C3833}"
        ".leyenda b{padding:2px 8px;border-radius:4px}"
        "@media(max-width:760px){.cab{display:none}.cab,.r{grid-template-columns:1fr}"
        ".r .c:first-child:not(:empty):before{content:'ANTES: ';font:700 11px Arial;color:#6B6560}"
        ".r .c:last-child:before{content:'DESPUES: ';font:700 11px Arial;color:#0A5C63}.igual .c:last-child{display:none}}"
    )
    pagina = (
        '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex"><title>Antes y despues</title><style>' + css + "</style>"
        "<header>Antes y despu&eacute;s &middot; " + e(titulo) + " &middot; solo texto (gr&aacute;ficos y tablas no cambian)</header>"
        '<div class="leyenda"><b style="background:#FFF6DC">amarillo</b> reescrito &nbsp; '
        '<b style="background:#E3F2EC">verde</b> nuevo &nbsp; <b style="background:#FBECEA">rojo</b> quitado &nbsp; gris = igual</div>'
        '<div class="cab"><div>Antes (redacci&oacute;n)</div><div>Despu&eacute;s (editor de narrativa)</div></div>'
        + "".join(filas))
    salida = os.path.join(RAIZ, "_privado", "narrativa", id_ + ".antes_despues.html")
    io.open(salida, "w", encoding="utf-8", newline="").write(pagina)
    cuenta = lambda c: sum(1 for f in filas if f.startswith('<div class="r %s"' % c))
    print("%s | reescritos %d, nuevos %d, quitados %d, iguales %d" % (salida, cuenta("cambia"), cuenta("nuevo"), cuenta("quitado"), cuenta("igual")))


if __name__ == "__main__":
    main()
