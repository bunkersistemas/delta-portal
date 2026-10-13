"""
comunidad.py -- la voz de los lectores (editor, 13/10/2026).

Una pregunta NO es un pedido de investigacion: es una senal de lo que le interesa a la
gente. Las investigaciones se piden SOLO por el bot de Telegram. Lo que llega por el
portal (panel "Preguntas de la comunidad" e investigacion.html) y por los comentarios de
Instagram es input:
  1. al editor le llega cada pregunta por Telegram: Aprobar / Descartar;
  2. las aprobadas quedan como historial en el panel del portal, sin nombres;
  3. el memo de los viernes las agrupa por tema y propone que investigar; el editor
     elige en la sesion y se vinculan las preguntas al pedido (vincular) o a una nota
     que ya las responde (responder);
  4. cuando sale la nota, las preguntas quedan "Respondida" con el link y, si vinieron
     de Instagram, se le contesta al comentario con la nota (la unica respuesta automatica).

Reglas (politicas de Meta y ley 25.326): de un comentario se guarda el texto y su id,
NUNCA el usuario ni el nombre; solo se contesta en NUESTRO posteo, a quien comento; nada
de mensajes privados, likes ni comentarios en posteos ajenos.

  ciclo                      tarea "Con Interes - Comunidad", cada 10 minutos
  exportar                   JSON de las preguntas (para el memo de los viernes)
  vincular <pedido> <ids>    esas preguntas dieron origen a ese pedido
  responder <url> <ids>      esas preguntas ya las responde una nota publicada
  desde_pedidos              suma al panel, como respondidas, las investigaciones pedidas
                             ya publicadas (lo hace solo pedidos_lectores.cerrar)
  ver                        lista las preguntas

Editor, 13/10/2026: toda investigacion pedida por el bot termina como pregunta RESPONDIDA
en el panel (origen "pedido"), con la pregunta bien formulada de la nota (titulo_busqueda),
no con las palabras del lector, y sin su nombre.
"""
import datetime as dt, json, os, re, sys, unicodedata, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pedidos_lectores as pl
import instagram_pub as igp

URL_P = pl.URL.replace("/pedidos", "/preguntas")
ESTADO = os.path.join(pl.LOGS, "comunidad_estado.json")
POSTEOS_A_MIRAR = 10      # los ultimos posteos: los viejos casi no reciben comentarios
NUESTRO_USUARIO = "coninteres.ar"
ORIGEN = {"instagram": "Instagram", "threads": "Threads", "web": "el portal"}
INTERROGATIVOS = ("que ", "cuant", "como ", "por que", "porque ", "cual", "donde", "cuando", "quien",
                  "es cierto", "es verdad", "se puede", "hay ", "me gustaria", "quisiera", "estaria bueno",
                  "podrian", "investiguen", "saber ")


def sb(metodo, consulta="", cuerpo=None, prefer="return=representation"):
    k = open(pl.LLAVE, encoding="ascii").read().strip()
    h = {"apikey": k, "Authorization": "Bearer " + k, "Content-Type": "application/json", "Prefer": prefer}
    datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
    req = urllib.request.Request(URL_P + consulta, data=datos, headers=h, method=metodo)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8") or "[]")


def ahora():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def leer_estado():
    try:
        return json.load(open(ESTADO, encoding="utf-8"))
    except Exception:
        return {"vistos": []}


def guardar_estado(e):
    e["vistos"] = e["vistos"][-3000:]
    tmp = ESTADO + ".tmp"
    json.dump(e, open(tmp, "w", encoding="utf-8"))
    os.replace(tmp, ESTADO)


def es_pregunta(t):
    """Solo se modera lo que es una pregunta o un pedido de tema: un "genial" o un emoji
    no le llegan al editor. Un comentario con links o menciones no se toma (suele ser
    publicidad o cadena)."""
    t = " ".join((t or "").split())
    if len(t) < 15 or len(t) > 300 or re.search(r"https?://|www\.|@\w", t):
        return False
    b = unicodedata.normalize("NFKD", t.lower()).encode("ascii", "ignore").decode().lstrip(" ")
    return "?" in t or b.startswith(INTERROGATIVOS)


def nota_de_media(media_id):
    for nid, p in igp.leer_estado().get("publicados", {}).items():
        if p.get("media") == media_id:
            return nid
    return None


def leer_comentarios():
    e = leer_estado()
    vistos = set(e["vistos"])
    m = igp.ig("GET", igp.IG_ID + "/media", {"fields": "id,comments_count", "limit": POSTEOS_A_MIRAR})
    nuevas = 0
    for x in m.get("data", []):
        if not x.get("comments_count"):
            continue
        cs = igp.ig("GET", x["id"] + "/comments", {"fields": "id,text,from", "limit": 50})
        for c in cs.get("data", []):
            if c["id"] in vistos:
                continue
            vistos.add(c["id"])
            e["vistos"].append(c["id"])
            de = c.get("from") or {}
            # lo nuestro no se modera; el usuario se usa solo para esta comparacion y no se guarda
            if de.get("id") == igp.IG_ID or de.get("username") == NUESTRO_USUARIO:
                continue
            if not es_pregunta(c.get("text")):
                continue
            sb("POST", "?on_conflict=ig_comment_id",
               {"texto": " ".join(c["text"].split()), "origen": "instagram", "ig_comment_id": c["id"],
                "ig_media_id": x["id"], "nota_contexto": nota_de_media(x["id"])},
               prefer="return=minimal,resolution=ignore-duplicates")
            nuevas += 1
    guardar_estado(e)
    print("OK|comentarios: %d preguntas nuevas" % nuevas)


def titulo_nota(nid):
    if not nid:
        return ""
    for a in pl.articulos():
        if a["id"] == nid:
            return a.get("titulo", "")
    return ""


def avisar_pendientes():
    ed = igp.editor()
    for q in sb("GET", "?select=id,texto,origen,nota_contexto&estado=eq.pendiente&avisada=is.null&order=creado&limit=10"):
        l = ["\U0001f64b Pregunta de un lector (%s):" % ORIGEN.get(q["origen"], q["origen"]), "",
             "\u00ab%s\u00bb" % q["texto"]]
        tn = titulo_nota(q.get("nota_contexto"))
        if tn:
            l += ["", "En el posteo de: " + tn]
        l += ["", "Aprobada, se ve en el historial del panel (sin nombre) y entra al memo de los viernes."]
        pl.tg("sendMessage", {"chat_id": ed, "text": "\n".join(l), "disable_web_page_preview": True,
                              "reply_markup": {"inline_keyboard": [
                                  [{"text": "\u2705 Aprobar", "callback_data": "cqa:%d" % q["id"]},
                                   {"text": "\u274c Descartar", "callback_data": "cqd:%d" % q["id"]}]]}})
        sb("PATCH", "?id=eq.%d" % q["id"], {"avisada": ahora()})
        print("OK|pregunta %d al editor" % q["id"])


def moderar_pregunta(qid, accion):
    """Lo llama el bot al tocar un boton. Devuelve el texto para el editor."""
    f = sb("GET", "?select=id,estado&id=eq.%d" % int(qid))
    if not f:
        return "No encuentro esa pregunta."
    if f[0]["estado"] != "pendiente":
        return "Esa pregunta ya estaba moderada (%s)." % f[0]["estado"]
    nuevo = "aprobada" if accion == "cqa" else "descartada"
    r = sb("PATCH", "?id=eq.%d&estado=eq.pendiente" % int(qid), {"estado": nuevo, "moderada": ahora()})
    if len(r) != 1:
        return "No pude registrarla: cambi\u00f3 mientras tanto."
    if nuevo == "aprobada":
        return "\u2705 Aprobada: queda en el historial del panel y entra al memo del viernes."
    return "Descartada: no se muestra en ning\u00fan lado."


def responder_ig(q, texto):
    """Le contesta al comentario, en nuestro posteo. Nunca frena: si falla, se anota."""
    if q.get("origen") != "instagram" or not q.get("ig_comment_id"):
        return False
    try:
        igp.ig("POST", q["ig_comment_id"] + "/replies", {"message": texto})
        return True
    except SystemExit as e:
        print("AVISO|no salio la respuesta al comentario de la pregunta %s: %s" % (q["id"], e))
        return False


def marcar_respondida(q, url):
    cambio = {"estado": "respondida", "nota_url": url}
    if not q.get("respondida_ig") and responder_ig(
            q, "\u00a1Gracias por la pregunta! Con lo que nos preguntaron armamos esta nota \U0001f4f0 " + url):
        cambio["respondida_ig"] = ahora()
    sb("PATCH", "?id=eq.%d" % q["id"], cambio)
    print("OK|pregunta %d respondida: %s" % (q["id"], url))


def seguimiento():
    """Las vinculadas a un pedido: cuando el pedido sale publicado, quedan respondidas."""
    for q in sb("GET", "?select=*&estado=eq.aprobada&pedido_id=not.is.null"):
        f = pl.pedir("GET", "?select=estado,salida&id=eq.%d" % q["pedido_id"])
        if f and f[0]["estado"] == "publicado" and f[0].get("salida"):
            marcar_respondida(q, f[0]["salida"].strip().split()[0])


def ids_de(args):
    ids = [int(x) for x in ",".join(args).replace(" ", ",").split(",") if x.strip()]
    if not ids:
        raise SystemExit("ERROR: faltan los ids de las preguntas")
    return ids


def vincular(pid, ids):
    if not pl.pedir("GET", "?select=id&id=eq.%d" % int(pid)):
        raise SystemExit("ERROR: no existe el pedido %s" % pid)
    for i in ids:
        r = sb("PATCH", "?id=eq.%d&estado=eq.aprobada" % i, {"pedido_id": int(pid)})
        print("OK|pregunta %d -> pedido %s" % (i, pid) if r else "AVISO|pregunta %d no esta aprobada: no se vinculo" % i)


def responder(url, ids):
    if not url.startswith("https://coninteres.com/"):
        raise SystemExit("ERROR: la nota tiene que ser una URL de coninteres.com")
    for i in ids:
        f = sb("GET", "?select=*&id=eq.%d&estado=eq.aprobada" % i)
        if f:
            marcar_respondida(f[0], url)
        else:
            print("AVISO|pregunta %d no esta aprobada: no se toca" % i)


def pregunta_de_nota(pid, url):
    """La pregunta publica de la nota (titulo_busqueda); si no esta, el titulo del pedido."""
    for a in pl.articulos():
        if str(a.get("pedido")) == str(pid) or url.endswith(a.get("archivo", "@")):
            t = a.get("titulo_busqueda") or ""
            if t:
                return t
    f = pl.pedir("GET", "?select=titulo&id=eq.%d" % int(pid))
    return f[0]["titulo"].strip() if f else ""


def desde_pedido(pid, url):
    url = url.strip().split()[0]
    ya = (sb("GET", "?select=id&pedido_id=eq.%d" % int(pid))
          or sb("GET", "?select=id&nota_url=eq." + urllib.parse.quote(url, safe="")))
    if ya:
        print("NADA|pedido %s: ya esta en el panel (pregunta %s)" % (pid, ya[0]["id"]))
        return
    t = " ".join(pregunta_de_nota(pid, url).split())
    if len(t) > 300:
        t = t[:297].rsplit(" ", 1)[0] + "..."
    if len(t) < 10:
        print("AVISO|pedido %s: sin pregunta para el panel" % pid)
        return
    sb("POST", "", {"texto": t, "origen": "pedido", "estado": "respondida", "moderada": ahora(),
                    "pedido_id": int(pid), "nota_url": url}, prefer="return=minimal")
    print("OK|pedido %s al panel como respondida" % pid)


def desde_pedidos():
    for p in pl.pedir("GET", "?select=id,salida&estado=eq.publicado&salida=not.is.null&order=id"):
        desde_pedido(p["id"], p["salida"])


def exportar():
    """Para el memo: las aprobadas y respondidas de los ultimos 60 dias (sin ids de Instagram)."""
    try:
        desde = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=60)).isoformat()
        filas = sb("GET", "?select=id,creado,origen,estado,texto,nota_contexto,pedido_id,nota_url"
                          "&estado=in.(aprobada,respondida)&creado=gt." + urllib.parse.quote(desde) + "&order=creado")
        print(json.dumps({"preguntas": filas}, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": "%s: %s" % (type(e).__name__, e)}))


def ciclo():
    # cada parte por separado: si Instagram no contesta, igual se avisa lo del portal
    for paso in (leer_comentarios, avisar_pendientes, seguimiento):
        try:
            paso()
        except SystemExit as e:
            print("AVISO|%s: %s" % (paso.__name__, e))
        except Exception as e:
            print("AVISO|%s: %s" % (paso.__name__, e))


def ver():
    for q in sb("GET", "?select=id,estado,origen,texto,pedido_id,nota_url&order=creado.desc&limit=50"):
        print("%(id)s|%(estado)s|%(origen)s|%(pedido_id)s|%(texto)s" % q)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    cmd = sys.argv[1]
    if cmd == "ciclo":
        ciclo()
    elif cmd == "exportar":
        exportar()
    elif cmd == "desde_pedidos":
        desde_pedidos()
    elif cmd == "ver":
        ver()
    elif cmd == "vincular" and len(sys.argv) > 3:
        vincular(sys.argv[2], ids_de(sys.argv[3:]))
    elif cmd == "responder" and len(sys.argv) > 3:
        responder(sys.argv[2], ids_de(sys.argv[3:]))
    elif cmd in ("cqa", "cqd") and len(sys.argv) > 2:
        print(moderar_pregunta(sys.argv[2], cmd))
    else:
        raise SystemExit(__doc__)
