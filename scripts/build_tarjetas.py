#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_tarjetas.py - Una tarjeta de compartir por nota, con su cifra ancla.

Por que existe: hasta el 01/09/2026 las 106 notas publicadas apuntaban todas a
la MISMA imagen (assets/og-delta.png). En X y en WhatsApp la tarjeta ES el
posteo: es lo que se ve antes que el texto. Cien notas mostrando la misma placa
generica es tirar el activo mas compartible que tenemos, que es el numero.

Genera assets/tarjetas/<id>.png (1200x630, el tamano que piden og:image y
twitter:summary_large_image) con: seccion, titular, la CIFRA ANCLA grande y su
etiqueta. Todo sale de data/articulos.json, o sea del mismo manifiesto que ya
alimenta la portada: si el numero cambia ahi, la tarjeta se rehace.

Despues de correr esto hay que correr inject_meta.py, que es el que apunta el
og:image de cada nota a su tarjeta (y cae a og-delta.png si no existe).

Uso:
  python scripts/build_tarjetas.py            # solo las que faltan
  python scripts/build_tarjetas.py --forzar   # rehace todas
  python scripts/build_tarjetas.py --id <id>  # una sola, para probar
"""
import argparse
import glob
import io
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(ROOT, "assets", "tarjetas")

W, H = 1200, 630
MARGEN = 64

PAPEL = (250, 248, 244)
TINTA = (22, 19, 15)
TINTA_S = (60, 56, 51)
MUTED = (107, 101, 96)
FAINT = (138, 132, 124)
REGLA = (220, 214, 204)

# Mismos colores que GRUPOS en build_portada.py.
COLOR = {
    "tu-plata": (14, 124, 134),
    "el-pais": (196, 112, 31),
    "empresas": (47, 93, 168),
    "los-mercados": (10, 92, 99),
    "tu-provincia": (46, 139, 111),
    "el-mundo": (122, 92, 196),
    "deportes": (192, 57, 43),
}
ETIQUETA = {
    "tu-plata": "Tu plata", "el-pais": "El país", "empresas": "Empresas", "los-mercados": "Los mercados",
    "tu-provincia": "Tu provincia", "el-mundo": "El mundo", "deportes": "Deportes",
}

# La tipografia del sitio (Source Serif 4 / Inter / IBM Plex Mono) son webfonts.
# Para rasterizar usamos los fallbacks que el propio CSS declara y que estan en
# cualquier Windows. Si falta alguna, se degrada sin romper.
FUENTES = {
    "serif":       ["georgia.ttf", "times.ttf", "DejaVuSerif.ttf"],
    "serif_bold":  ["georgiab.ttf", "timesbd.ttf", "DejaVuSerif-Bold.ttf"],
    "sans":        ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"],
    "sans_bold":   ["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"],
    "mono":        ["consola.ttf", "cour.ttf", "DejaVuSansMono.ttf"],
    "mono_bold":   ["consolab.ttf", "courbd.ttf", "DejaVuSansMono-Bold.ttf"],
}
DIRS_FUENTES = [
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
    "/usr/share/fonts/truetype/dejavu",
    "/Library/Fonts",
]
_cache = {}


def fuente(clave, tam):
    k = (clave, tam)
    if k in _cache:
        return _cache[k]
    for nombre in FUENTES[clave]:
        for d in DIRS_FUENTES:
            p = os.path.join(d, nombre)
            if os.path.exists(p):
                try:
                    _cache[k] = ImageFont.truetype(p, tam)
                    return _cache[k]
                except OSError:
                    pass
    _cache[k] = ImageFont.load_default()
    return _cache[k]


def ancho(d, texto, f):
    return d.textlength(texto, font=f)


def escribir_espaciado(d, xy, texto, f, fill, espaciado):
    """Pillow no tiene letter-spacing. La volanta del sitio lo usa y sin esto
    se ve apretada, asi que la dibujamos caracter por caracter."""
    x, y = xy
    for ch in texto:
        d.text((x, y), ch, font=f, fill=fill)
        x += d.textlength(ch, font=f) + espaciado
    return x


def envolver(d, texto, f, ancho_max, max_lineas):
    """Corta en palabras. Devuelve (lineas, se_corto)."""
    palabras, lineas, actual = texto.split(), [], ""
    for p in palabras:
        prueba = (actual + " " + p).strip()
        if ancho(d, prueba, f) <= ancho_max or not actual:
            actual = prueba
        else:
            lineas.append(actual)
            actual = p
            if len(lineas) == max_lineas:
                break
    if actual and len(lineas) < max_lineas:
        lineas.append(actual)
    cortado = len(" ".join(lineas).split()) < len(palabras)
    if cortado:
        ult = lineas[-1]
        while ult and ancho(d, ult + "…", f) > ancho_max:
            ult = ult.rsplit(" ", 1)[0] if " " in ult else ult[:-1]
        lineas[-1] = ult + "…"
    return lineas, cortado


def titular(d, texto, ancho_max):
    """El titular entero siempre que se pueda: probamos tamanos de mayor a
    menor y nos quedamos con el primero que no obligue a cortar. Recien si
    ninguno entra, aceptamos los puntos suspensivos."""
    for tam, maxl, alto in ((52, 3, 64), (46, 4, 57), (41, 5, 51)):
        f = fuente("serif_bold", tam)
        lineas, cortado = envolver(d, texto, f, ancho_max, maxl)
        if not cortado:
            return f, lineas, alto
    return f, lineas, alto


MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def fecha_larga(iso):
    try:
        a, m, dd = (int(x) for x in iso.split("-"))
        return "%d de %s de %d" % (dd, MESES[m - 1], a)
    except (ValueError, AttributeError, IndexError):
        return iso or ""


def tilde(d, x, y, color):
    """Consolas no trae el glifo del check, asi que lo dibujamos."""
    d.line([(x, y + 7), (x + 5, y + 12), (x + 14, y - 1)], fill=color, width=2)
    return x + 22


def grupo_de(articulo, mapa_secciones):
    """De que seccion es. En vez de duplicar la heuristica de palabras clave de
    build_portada.py -que se desincronizaria-, miramos en cual de las paginas
    de seccion ya generadas aparece la nota. Esa es la fuente de verdad."""
    return mapa_secciones.get(articulo["archivo"], "el-pais")


def mapear_secciones():
    mapa = {}
    for p in glob.glob(os.path.join(ROOT, "seccion-*.html")):
        base = os.path.basename(p)[len("seccion-"):-len(".html")]
        gid = base.rsplit("-", 1)[0] if base.rsplit("-", 1)[-1].isdigit() else base
        if gid not in COLOR:
            continue
        html = io.open(p, encoding="utf-8").read()
        for m in set(__import__("re").findall(r'href="(articulos/[^"]+\.html)"', html)):
            mapa[m] = gid
    return mapa


def tarjeta(a, gid):
    color = COLOR.get(gid, COLOR["el-pais"])
    img = Image.new("RGB", (W, H), PAPEL)
    d = ImageDraw.Draw(img)

    # franja de seccion a la izquierda
    d.rectangle([0, 0, 10, H], fill=color)

    x0 = MARGEN + 10
    ancho_util = W - x0 - MARGEN

    # --- cabecera -----------------------------------------------------------
    f_marca = fuente("serif_bold", 34)
    d.text((x0, 52), "%", font=f_marca, fill=color)
    d.text((x0 + ancho(d, "% ", f_marca), 52), "Con Interés", font=f_marca, fill=TINTA)
    f_fecha = fuente("mono", 19)
    fecha = fecha_larga(a.get("fecha", ""))
    d.text((W - MARGEN - ancho(d, fecha, f_fecha), 60), fecha, font=f_fecha, fill=FAINT)
    d.rectangle([x0, 108, W - MARGEN, 110], fill=TINTA)

    # --- volanta ------------------------------------------------------------
    f_kick = fuente("mono_bold", 19)
    volanta = ETIQUETA.get(gid, "El país").upper()
    if a.get("formato"):
        volanta += "   /   " + a["formato"].upper()
    escribir_espaciado(d, (x0, 138), volanta, f_kick, color, 2.2)

    # --- titular ------------------------------------------------------------
    f_tit, lineas, alto_linea = titular(d, a.get("titulo", ""), ancho_util)
    y = 184
    for ln in lineas:
        d.text((x0, y), ln, font=f_tit, fill=TINTA)
        y += alto_linea

    # --- cifra ancla --------------------------------------------------------
    numero = (a.get("numero") or "").strip()
    if numero:
        tam = 104
        f_num = fuente("mono_bold", tam)
        while ancho(d, numero, f_num) > 470 and tam > 44:
            tam -= 4
            f_num = fuente("mono_bold", tam)
        # debajo del titular, sin pisarlo y sin pisar el pie
        y_num = min(max(418, y + 18), 540 - tam)
        d.text((x0, y_num), numero, font=f_num, fill=color)
        an = ancho(d, numero, f_num)

        etiqueta = a.get("numero_label", "")
        if etiqueta:
            f_lab = fuente("sans", 21)
            x_lab = x0 + an + 28
            disponible = W - MARGEN - x_lab
            if disponible < 220:            # el numero se comio el ancho
                x_lab, disponible = x0, ancho_util
                y_lab = y_num + tam + 16
            else:
                y_lab = y_num + 12
            for ln in envolver(d, etiqueta, f_lab, disponible, 4)[0]:
                d.text((x_lab, y_lab), ln, font=f_lab, fill=MUTED)
                y_lab += 29

    # --- pie ----------------------------------------------------------------
    d.rectangle([x0, 556, W - MARGEN, 557], fill=REGLA)
    f_pie = fuente("mono", 19)
    xp = tilde(d, x0 + 1, 584, color)
    d.text((xp, 578), "Verificada · cada cifra con su fuente", font=f_pie, fill=MUTED)
    sitio = "coninteres.com"
    d.text((W - MARGEN - ancho(d, sitio, f_pie), 578), sitio, font=f_pie, fill=color)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--forzar", action="store_true", help="rehace las que ya existen")
    ap.add_argument("--id", help="genera una sola nota, por id")
    args = ap.parse_args()

    arts = json.load(io.open(os.path.join(ROOT, "data", "articulos.json"),
                             encoding="utf-8"))["articulos"]
    if args.id:
        arts = [a for a in arts if a["id"] == args.id]
        if not arts:
            print("No encontre esa nota."); return 1

    os.makedirs(SALIDA, exist_ok=True)
    mapa = mapear_secciones()
    if not mapa:
        print("OJO: no pude leer las paginas de seccion; todas las tarjetas van a")
        print("     salir con el color de 'El pais'. Corre antes build_portada.py.")

    nuevas = saltadas = 0
    sin_numero = []
    for a in arts:
        destino = os.path.join(SALIDA, a["id"] + ".png")
        if os.path.exists(destino) and not args.forzar:
            saltadas += 1
            continue
        if not (a.get("numero") or "").strip():
            sin_numero.append(a["id"])
        tarjeta(a, grupo_de(a, mapa)).save(destino, "PNG", optimize=True)
        nuevas += 1

    print("OK -> %s  (%d generadas, %d ya estaban)" % (SALIDA, nuevas, saltadas))
    if sin_numero:
        print("  [aviso] %d nota(s) sin cifra ancla en el manifiesto; la tarjeta"
              " sale sin numero:" % len(sin_numero))
        for i in sin_numero[:5]:
            print("          -", i)
    print("  Ahora corre:  python scripts/inject_meta.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
