#!/usr/bin/env python3
"""
marcar_pedido.py <archivo.html> -- etiqueta "Pregunta de un lector" arriba del titulo.

Editor, 13/10/2026: una investigacion pedida por un lector se tiene que ver como tal,
con una etiqueta destacada. La pone aprobar.py al publicar y la redaccion al mandar la
vista previa. Es idempotente: si la etiqueta ya esta, no hace nada.
"""
import io, sys

MARCA = 'class="lector-tag"'
ETIQUETA = ('<div class="lector-tag" style="display:inline-block;font-family:\'IBM Plex Mono\',monospace;'
            'font-size:11px;letter-spacing:.1em;text-transform:uppercase;font-weight:600;color:#fff;'
            'background:#C4701F;padding:5px 11px;border-radius:999px;margin:0 0 14px">'
            '&#128587; Pregunta de un lector</div>\n')


def marcar(ruta):
    html = io.open(ruta, encoding="utf-8").read()
    if MARCA in html:
        return False
    i = html.find("<h1")
    if i < 0:
        raise SystemExit("ERROR: %s no tiene <h1>" % ruta)
    io.open(ruta, "w", encoding="utf-8").write(html[:i] + ETIQUETA + html[i:])
    return True


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    print("OK|etiqueta puesta" if marcar(sys.argv[1]) else "OK|ya tenia la etiqueta")
