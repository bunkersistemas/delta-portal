#!/usr/bin/env python3
"""
inject_meta.py — Inyecta (o refresca) los metadatos de marca y redes sociales
en cada nota publicada, tomando los datos de data/articulos.json.

Idempotente: reemplaza el bloque marcado <!-- DELTA-META --> si ya existe.
Se puede correr las veces que haga falta. Lo llama aprobar.py al publicar.

Uso:  python3 scripts/inject_meta.py
"""
import json, os, re
from html import escape

def fecha_iso(a):
    """Fecha y hora con huso (Argentina, -03:00). Google ordena las noticias por
    frescura: con la fecha sola todas las del dia empatan a medianoche."""
    f, h = str(a.get("fecha", "")), str(a.get("hora", ""))
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", f) and re.fullmatch(r"\d{2}:\d{2}", h):
        return f"{f}T{h}:00-03:00"
    return f

def jsonld_block(a, url, img):
    """JSON-LD schema.org/Article para SEO (rich results + comprensión de Google)."""
    data = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        # titulo completo: el tope de 110 de Google ya no rige y cortaba a mitad de frase
        "headline": a.get("titulo", ""),
        "description": a.get("bajada", ""),
        "datePublished": fecha_iso(a),
        "dateModified": fecha_iso(a),
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
        "image": [img],
        "articleSection": a.get("seccion", ""),
        "inLanguage": "es-AR",
        "author": {"@type": "Organization", "name": "Con Interés", "url": SITE},
        "publisher": {
            "@type": "Organization",
            "name": "Con Interés",
            "url": SITE,
            "logo": {"@type": "ImageObject", "url": f"{SITE}/assets/og-delta.png"},
        },
    }
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f'<script type="application/ld+json">{payload}</script>\n'

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://coninteres.com"   # mantener igual que build_portada.py

BLOCK_RE = re.compile(r"[ \t]*<!-- DELTA-META:start -->.*?<!-- DELTA-META:end -->\n?", re.S)

def imagen_de(a):
    """La tarjeta propia de la nota, con su cifra ancla, si existe.

    Hasta el 01/09/2026 todas las notas compartían la misma placa genérica y en
    X —donde la tarjeta ES el posteo— eso desperdiciaba lo más compartible que
    tenemos, que es el número. Las genera scripts/build_tarjetas.py; si falta,
    se cae a la placa de marca y no se rompe nada.
    """
    rel = f"assets/tarjetas/{a['id']}.png"
    if os.path.exists(os.path.join(ROOT, rel)):
        return f"{SITE}/{rel}"
    return f"{SITE}/assets/og-delta.png"


def meta_block(a):
    url = f"{SITE}/{a['archivo']}"
    # la pregunta que busca la gente, si la hay, va a lo que lee Google y las
    # redes; el titulo de portada arranca con el dato (25/09/2026)
    title = escape(a.get('titulo_busqueda') or a['titulo']) + " — Con Interés"
    desc = escape(a.get('bajada', ''))
    img = imagen_de(a)
    return (
        "<!-- DELTA-META:start -->\n"
        '<link rel="icon" type="image/svg+xml" href="../assets/favicon.svg">\n'
        f'<link rel="canonical" href="{url}">\n'
        # sin esto Discover solo puede mostrar la miniatura chica, no la tarjeta
        '<meta name="robots" content="max-image-preview:large">\n'
        f'<meta name="description" content="{desc}">\n'
        '<meta property="og:type" content="article">\n'
        '<meta property="og:site_name" content="Con Interés">\n'
        f'<meta property="og:title" content="{title}">\n'
        f'<meta property="og:description" content="{desc}">\n'
        f'<meta property="og:url" content="{url}">\n'
        f'<meta property="og:image" content="{img}">\n'
        '<meta property="og:locale" content="es_AR">\n'
        '<meta name="twitter:card" content="summary_large_image">\n'
        f'<meta name="twitter:title" content="{title}">\n'
        f'<meta name="twitter:description" content="{desc}">\n'
        f'<meta name="twitter:image" content="{img}">\n'
        + jsonld_block(a, url, img)
        + "<!-- DELTA-META:end -->\n"
    )

def main():
    arts = json.load(open(os.path.join(ROOT, "data", "articulos.json"), encoding="utf-8"))["articulos"]
    n = 0
    for a in arts:
        path = os.path.join(ROOT, a["archivo"])
        if not os.path.exists(path):
            print(f"  (falta {a['archivo']}, salteo)"); continue
        html = open(path, encoding="utf-8").read()
        html = BLOCK_RE.sub("", html)            # saca bloque previo si existe
        if a.get("titulo_busqueda"):
            html = re.sub(r"<title>.*?</title>",
                          "<title>" + escape(a["titulo_busqueda"]).replace("\\", "\\\\") + " — CON INTERÉS</title>",
                          html, count=1, flags=re.S)
        block = meta_block(a)
        # insertar después del <meta name="viewport" ...>
        m = re.search(r'<meta name="viewport"[^>]*>\n?', html)
        if m:
            html = html[:m.end()] + block + html[m.end():]
        else:                                    # fallback: después de <title>
            html = re.sub(r"(</title>\n?)", r"\1" + block, html, count=1)
        open(path, "w", encoding="utf-8").write(html)
        n += 1
    print(f"OK -> metadatos inyectados en {n} nota(s)")

if __name__ == "__main__":
    main()
