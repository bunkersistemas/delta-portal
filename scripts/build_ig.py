#!/usr/bin/env python3
"""
build_ig.py -- imagen para Instagram de cada nota: 1080x1350 (4:5, el formato que mas
pantalla ocupa en el feed), en JPG (la API de Instagram no acepta PNG).

Editor, 13/10/2026: Con Interes publica en Instagram (@coninteres.ar). La tarjeta para
compartir (build_tarjetas.py, 1200x630) queda chica en el feed: esta va vertical, con el
DATO enorme arriba, el titulo debajo y la etiqueta "Pregunta de un lector" si la nota la
pidio un lector. Misma identidad que el sitio.

Uso:
  python scripts/build_ig.py                 genera las que faltan (assets/ig/<id>.jpg)
  python scripts/build_ig.py <id> [<id>...]  (re)genera esas
"""
import json, os, sys
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_tarjetas import fuente, envolver   # mismas tipografias del sitio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(ROOT, "assets", "ig")
W, H = 1080, 1350
PAPEL, TINTA, SUAVE, GRIS = "#FAF8F4", "#16130F", "#3C3833", "#8A847C"
VERDE, NARANJA, REGLA = "#2E8B6F", "#C4701F", "#DCD6CC"
M = 80   # margen


def etiqueta_corta(t, n=150):
    """El numero_label trae las fuentes entre parentesis: en el feed va la idea, sin ellas."""
    import re
    t = re.sub(r"\s*\([^()]*\)", "", str(t or "")).strip()
    i = t.find("; ")
    if i > 40:
        t = t[:i]
    t = t.rstrip(" ,;:")
    return t if len(t) <= n else t[:n - 1].rsplit(" ", 1)[0].rstrip(" ,;:") + "..."


SECCIONES = {"EMPRESAS": "Empresas", "MERCADOS": "Los mercados", "ECONOMÍA PROVINCIAL": "Tu provincia",
             "MUNDO": "El mundo", "DEPORTES": "Economía del deporte", "IA": "La economía de la IA"}


def seccion_de(a):
    return SECCIONES.get(a.get("seccion", ""), "Economía")


def gancho(a, n=100):
    """La frase del posteo (editor, 13/10/2026: el titulo completo es largo para el feed):
    la pregunta como la buscaria la gente; si trae varias, la primera."""
    t = " ".join(str(a.get("titulo_busqueda") or a.get("titulo") or "").split())
    if len(t) > n and "?" in t:
        t = t[:t.index("?") + 1]
    if len(t) > n:
        t = t[:n - 1].rsplit(" ", 1)[0].rstrip(" ,;:") + "..."
    return t


def tam_numero(d, texto, ancho_max):
    for tam in (230, 200, 170, 145, 120, 100, 84, 70):
        if d.textlength(texto, font=fuente("mono_bold", tam)) <= ancho_max:
            return tam
    return 60


def dibujar(a):
    im = Image.new("RGB", (W, H), PAPEL)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 14, H], fill=VERDE)
    # marca
    f_marca = fuente("serif_bold", 50)
    d.text((M, 62), "%", font=f_marca, fill=VERDE)
    d.text((M + d.textlength("% ", font=f_marca), 62), "Con Interés", font=f_marca, fill=TINTA)
    d.line([M, 140, W - M, 140], fill=TINTA, width=4)
    y = 172
    if a.get("pedido"):
        f_tag = fuente("mono_bold", 26)
        txt = "PREGUNTA DE UN LECTOR"
        w = d.textlength(txt, font=f_tag)
        d.rounded_rectangle([M, y, M + w + 44, y + 50], radius=25, fill=NARANJA)
        d.text((M + 22, y + 10), txt, font=f_tag, fill="#FFFFFF")
        y += 82
    else:
        # sin etiqueta de lector: la seccion, que da contexto
        f_sec = fuente("mono_bold", 26)
        d.text((M, y + 8), seccion_de(a).upper(), font=f_sec, fill=VERDE)
        y += 82
    # la pregunta arriba y el dato abajo, como respuesta (editor, 13/10/2026)
    num = str(a.get("numero", "")).strip()
    f_lab = fuente("sans", 34)
    lab = envolver(d, etiqueta_corta(a.get("numero_label")), f_lab, W - 2 * M, 3)[0] if num else []
    tam_n = tam_numero(d, num, W - 2 * M) if num else 0
    alto_dato = (int(tam_n * 1.08) + 46 * len(lab) + 60) if num else 0
    alto_libre = H - 190 - y - alto_dato
    for tam in (84, 76, 68, 60, 54, 48, 44):
        f_tit = fuente("serif_bold", tam)
        lineas, cortado = envolver(d, gancho(a), f_tit, W - 2 * M, 6)
        if not cortado and len(lineas) * tam * 1.2 <= alto_libre:
            break
    for linea in lineas:
        d.text((M, y), linea, font=f_tit, fill=TINTA)
        y += int(tam * 1.2)
    if num:
        y += 30
        d.line([M, y, M + 160, y], fill=REGLA, width=4)
        y += 30
        d.text((M - 4, y), num, font=fuente("mono_bold", tam_n), fill=VERDE)
        y += int(tam_n * 1.08)
        for linea in lab:
            d.text((M, y), linea, font=f_lab, fill=SUAVE)
            y += 46
    # pie
    d.line([M, H - 150, W - M, H - 150], fill=REGLA, width=3)
    f_pie = fuente("mono", 30)
    # la tilde se dibuja: la tipografia monoespaciada no tiene el simbolo
    d.line([(M + 2, H - 101), (M + 11, H - 91), (M + 28, H - 113)], fill=VERDE, width=5)
    d.text((M + 42, H - 118), "Verificada · la nota completa, link en la bio", font=f_pie, fill=GRIS)
    f_web = fuente("mono_bold", 30)
    d.text((M, H - 74), "coninteres.com", font=f_web, fill=VERDE)
    return im


def generar(a, forzar=False):
    os.makedirs(SALIDA, exist_ok=True)
    destino = os.path.join(SALIDA, a["id"] + ".jpg")
    if os.path.exists(destino) and not forzar:
        return False
    dibujar(a).save(destino, "JPEG", quality=90, optimize=True, progressive=True)
    return True


def main(ids):
    arts = json.load(open(os.path.join(ROOT, "data", "articulos.json"), encoding="utf-8"))["articulos"]
    por_id = {a["id"]: a for a in arts}
    if ids:
        hechas = sum(generar(por_id[i], True) for i in ids)
    else:
        hechas = sum(generar(a) for a in arts[:40])   # las ultimas 40 alcanzan para elegir
    print("OK -> %s  (%d generadas)" % (SALIDA, hechas))


if __name__ == "__main__":
    main(sys.argv[1:])
