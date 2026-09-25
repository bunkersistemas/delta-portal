#!/usr/bin/env python3
"""
aprobar.py — Aprueba un borrador de la cola y lo publica.

Mueve la nota de cola/ a articulos/, pasa su metadata de cola.json a
articulos.json, marca el tema como publicada en cubiertas.json, quita el
cintillo de borrador y regenera la portada.

Uso:  python3 scripts/aprobar.py <id-del-borrador>
Ej.:  python3 scripts/aprobar.py 2026-07-18-malvinas-sea-lion
"""
import json, os, sys, subprocess, datetime, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

def load(n):
    with open(os.path.join(DATA, n), encoding="utf-8") as f: return json.load(f)
def save(n, d):
    with open(os.path.join(DATA, n), "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

def main(draft_id):
    cola = load("cola.json"); art = load("articulos.json"); cub = load("cubiertas.json")
    draft = next((b for b in cola["borradores"] if b["id"] == draft_id), None)
    if not draft:
        print(f"ERROR: no encontré el borrador '{draft_id}' en la cola."); sys.exit(1)

    src = os.path.join(ROOT, "cola", f"{draft_id}.html")
    dst = os.path.join(ROOT, "articulos", f"{draft_id}.html")
    if not os.path.exists(src):
        print(f"ERROR: falta el archivo {src}"); sys.exit(1)

    # 1) mover HTML y limpiar marcas de borrador
    html = open(src, encoding="utf-8").read()
    html = "\n".join(l for l in html.split("\n")
                     if 'class="draft-ribbon"' not in l
                     and 'name="robots" content="noindex"' not in l)
    # quitar el cintillo de borrador del cuerpo (.borrador); la regla CSS queda, es inocua
    html = re.sub(r'\n?<div class="borrador">.*?</div>\s*</div>\s*\n', "\n", html, flags=re.S)
    html = html.replace(
        "Borrador generado por la redacción de agentes y pendiente de aprobación. ",
        "")
    with open(dst, "w", encoding="utf-8") as f: f.write(html)
    os.remove(src)

    # 2) armar entrada de articulos.json
    entry = {
        "id": draft["id"], "titulo": draft["titulo"], "bajada": draft.get("bajada",""),
        "titulo_busqueda": draft.get("titulo_busqueda",""),
        "seccion": draft["seccion"], "formato": draft.get("formato",""),
        "numero": draft.get("numero",""), "numero_label": draft.get("numero_label",""),
        "fecha": draft.get("fecha",""), "hora": draft.get("hora",""),
        "archivo": f"articulos/{draft_id}.html",
        "verificacion": draft.get("verificacion","verificada"),
        "fuentes": draft.get("fuentes",0), "lectura": draft.get("lectura",""),
    }
    art["articulos"].insert(0, entry)
    art["portal"]["actualizado"] = datetime.datetime.now().astimezone().replace(microsecond=0).isoformat() \
        if os.environ.get("DELTA_NOW") is None else os.environ["DELTA_NOW"]

    # 3) sacar de la cola
    cola["borradores"] = [b for b in cola["borradores"] if b["id"] != draft_id]

    # 4) cubiertas -> publicada
    for t in cub["temas"]:
        if t.get("articulo_id") == draft_id: t["estado"] = "publicada"

    save("articulos.json", art); save("cola.json", cola); save("cubiertas.json", cub)

    # 5) regenerar el sitio, la tarjeta de compartir y los metadatos.
    #    El orden importa: build_portada deja al dia las paginas de seccion, de
    #    donde build_tarjetas saca el color de la nota; e inject_meta se corre
    #    ultimo porque apunta el og:image a la tarjeta, que ya tiene que existir.
    #    build_feed va al final porque cada item cita la tarjeta de su nota.
    for script in ("build_portada.py", "build_tarjetas.py", "inject_meta.py",
                   "build_feed.py"):
        subprocess.run([sys.executable, os.path.join(ROOT, "scripts", script)], check=True)
    print(f"PUBLICADA: {draft['titulo']}")

    # 6) mostrar el kit social listo para pegar (X + Telegram), si existe
    kit = os.path.join(ROOT, "kits", f"{draft_id}.md")
    if os.path.exists(kit):
        print("\n===== KIT SOCIAL (copiar y pegar) =====\n")
        print(open(kit, encoding="utf-8").read())
        print("\n===== fin del kit =====")
    else:
        print(f"\n[aviso] no hay kit social en kits/{draft_id}.md — "
              "generar el kit para X/Telegram antes de difundir (ver NEWSROOM.md §9).")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 scripts/aprobar.py <id-del-borrador>"); sys.exit(1)
    main(sys.argv[1])
