"""
comunidad.py -- preguntas de la comunidad y moderacion unica (editor, 13/10/2026).

Todo lo que entra desde afuera pasa por el editor ANTES de investigarse o mostrarse:
  - comentarios con preguntas en nuestros posteos de Instagram;
  - preguntas del panel flotante del portal ("Preguntas de la comunidad");
  - pedidos del formulario del portal (investigacion.html), que la base deja en
    estado "moderacion" (trigger pedidos_moderacion).
Lo que se pide desde el chat del bot sigue directo, como hasta ahora.

Al editor le llega cada una por Telegram:
  pregunta:  Investigar (nace un pedido) / Mostrar en el panel / Descartar
  pedido:    Investigar (pasa a recibido) / Descartar

Reglas (dentro de las politicas de Meta y de la ley de datos personales):
  - de un comentario se guarda el texto y su id, NUNCA el usuario ni el nombre;
  - solo se le contesta a quien nos comento, en NUESTRO posteo, y solo dos veces:
    cuando el editor decide investigarla y cuando sale la nota;
  - nada de mensajes privados, likes ni comentarios en posteos ajenos.

  ciclo     lo corre la tarea "Con Interes - Comunidad" cada 10 minutos:
            lee comentarios, avisa lo pendiente y cierra lo que ya tiene nota
  ver       lista las preguntas (prueba)
"""
import datetime as dt, json, os, re, sys, time, unicodedata, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pedidos_lectores as pl
import instagram_pub as igp

URL_P = pl.URL.replace("/pedidos", "/preguntas")
ESTADO = os.path.join(pl.LOGS, "comunidad_estado.json")
POSTEOS_A_MIRAR = 10      # los ultimos posteos: los viejos casi no reciben comentarios
NUESTRO_USUARIO = "coninteres.ar"
ORIGEN = {"instagram": "Instagram", "threads": "Threads", "web": "el portal"}
INTERROGATIVOS = ("que ", "cuant", "como ", "por que", "porque ", "cual", "donde", "cuando", "quien",
                  "es cierto", "es verdad", "se puede", "hay ")


def sb(metodo, consulta="", cuerpo=None, prefer="return=representation"):
    k = open(pl.LLAVE, encoding="ascii").read().strip()
    h = {"apikey": k, "Authorization": "Bearer " + k, "Content-Type": "application/json", "Prefer": prefer}
    datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
    req = urllib.request.Request(URL_P + consulta, data=datos, headers=h, method=metodo)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8") or "[]")


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
    """Solo se modera lo que es una pregunta: un "genial" o un emoji no le llegan al editor.
    Un comentario con links no se toma (suele ser publicidad)."""
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
    ahora = dt.datetime.now(dt.timezone.utc).isoformat()
    for q in sb("GET", "?select=id,texto,origen,nota_contexto&estado=eq.pendiente&avisada=is.null&order=creado&limit=10"):
        l = ["\U0001f64b Pregunta de la comunidad (%s):" % ORIGEN.get(q["origen"], q["origen"]), "",
             "\u00ab%s\u00bb" % q["texto"]]
        tn = titulo_nota(q.get("nota_contexto"))
        if tn:
            l += ["", "En el posteo de: " + tn]
        l += ["", "Si la investigamos, nace un pedido y sale con la etiqueta de lector. En el panel se ve sin nombre."]
        pl.tg("sendMessage", {"chat_id": ed, "text": "\n".join(l), "disable_web_page_preview": True,
                              "reply_markup": {"inline_keyboard": [
                                  [{"text": "\U0001f50d Investigar", "callback_data": "cqi:%d" % q["id"]}],
                                  [{"text": "\U0001f4cc Mostrar en el panel", "callback_data": "cqp:%d" % q["id"]},
                                   {"text": "\u274c Descartar", "callback_data": "cqd:%d" % q["id"]}]]}})
        sb("PATCH", "?id=eq.%d" % q["id"], {"avisada": ahora})
        print("OK|pregunta %d al editor" % q["id"])
    for p in pl.pedir("GET", "?select=id,titulo,tipo,detalle,telegram_chat&estado=eq.moderacion"
                             "&moderacion_avisada=is.null&or=(origen.is.null,origen.neq.prueba)&order=creado&limit=10"):
        l = ["\U0001f4dd Pedido de investigaci\u00f3n desde el portal:", "", "\u00ab%s\u00bb" % p["titulo"].strip()]
        if (p.get("detalle") or "").strip():
            l += ["", p["detalle"].strip()[:700]]
        l += ["", "Contacto: " + ("Telegram" if p.get("telegram_chat") else "sin contacto todav\u00eda")]
        pl.tg("sendMessage", {"chat_id": ed, "text": "\n".join(l), "disable_web_page_preview": True,
                              "reply_markup": {"inline_keyboard": [
                                  [{"text": "\U0001f50d Investigar", "callback_data": "cpi:%d" % p["id"]},
                                   {"text": "\u274c Descartar", "callback_data": "cpd:%d" % p["id"]}]]}})
        pl.pedir("PATCH", "?id=eq.%d" % p["id"], {"moderacion_avisada": ahora})
        print("OK|pedido %d al editor" % p["id"])


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


def titulo_pedido(t):
    """El pedido tiene un tope de 140: la pregunta entera viaja en el detalle."""
    t = " ".join(t.split())
    if len(t) <= 140:
        return t
    if "?" in t[:140]:
        return t[:t.index("?") + 1]
    return t[:137].rsplit(" ", 1)[0] + "..."


def moderar_pregunta(qid, accion):
    """Lo llama el bot al tocar un boton. Devuelve el texto para el editor."""
    f = sb("GET", "?select=*&id=eq.%d" % int(qid))
    if not f:
        return "No encuentro esa pregunta."
    q = f[0]
    if q["estado"] != "pendiente":
        return "Esa pregunta ya estaba moderada (%s)." % q["estado"]
    ahora = dt.datetime.now(dt.timezone.utc).isoformat()
    if accion == "cqd":
        sb("PATCH", "?id=eq.%d&estado=eq.pendiente" % q["id"], {"estado": "descartada", "moderada": ahora})
        return "Descartada. No se muestra en ning\u00fan lado."
    if accion == "cqp":
        sb("PATCH", "?id=eq.%d&estado=eq.pendiente" % q["id"], {"estado": "en_panel", "moderada": ahora})
        return "\U0001f4cc Queda en el panel de preguntas del portal, sin nombre."
    detalle = ("Pregunta de la comunidad, llegada por %s: %s" % (ORIGEN.get(q["origen"], q["origen"]), q["texto"]))
    if q.get("nota_contexto"):
        detalle += "\n(La hicieron en el posteo de la nota %s.)" % q["nota_contexto"]
    p = pl.pedir("POST", "", {"titulo": titulo_pedido(q["texto"]), "tipo": "otro", "detalle": detalle[:1500],
                              "origen": "comunidad-" + q["origen"]})[0]
    sb("PATCH", "?id=eq.%d&estado=eq.pendiente" % q["id"],
       {"estado": "investigando", "moderada": ahora, "pedido_id": p["id"]})
    contestada = responder_ig(q, "\u00a1Buena pregunta! \U0001f50d La estamos investigando. Cuando salga la nota "
                                 "te contestamos por ac\u00e1.")
    return ("\U0001f50d Va a investigaci\u00f3n: es el pedido %d. Sale con la etiqueta de lector.%s"
            % (p["id"], " Le contestamos el comentario." if contestada else ""))


def moderar_pedido(pid, accion):
    f = pl.pedir("GET", "?select=id,estado,telegram_chat&id=eq.%d" % int(pid))
    if not f:
        return "No encuentro ese pedido."
    p = f[0]
    if p["estado"] != "moderacion":
        return "Ese pedido ya estaba moderado (%s)." % p["estado"]
    if accion == "cpd":
        pl.pedir("PATCH", "?id=eq.%d&estado=eq.moderacion" % p["id"],
                 {"estado": "descartado", "motivo": "moderacion: no se investiga",
                  "cerrado": dt.datetime.now(dt.timezone.utc).isoformat()})
        pl.avisar(p["id"], "Gracias por tu pedido. Esta vez no lo vamos a investigar, pero pod\u00e9s mandarnos otro "
                           "cuando quieras.")
        return "Descartado."
    pl.pedir("PATCH", "?id=eq.%d&estado=eq.moderacion" % p["id"], {"estado": "recibido"})
    pl.avisar(p["id"], "\u00a1Tu pedido entr\u00f3 a la redacci\u00f3n! \U0001f64c Ahora armamos el enfoque y te lo "
                       "mando por ac\u00e1.")
    return "\U0001f50d Pedido %d a investigaci\u00f3n." % p["id"]


def seguimiento():
    """Las que se estan investigando: si el pedido salio, queda Respondida con su nota y se le
    contesta al comentario; si se cerro sin nota, vuelve al panel como pregunta."""
    for q in sb("GET", "?select=*&estado=eq.investigando&pedido_id=not.is.null"):
        f = pl.pedir("GET", "?select=estado,salida&id=eq.%d" % q["pedido_id"])
        if not f:
            continue
        if f[0]["estado"] == "publicado" and f[0].get("salida"):
            url = f[0]["salida"].strip().split()[0]
            cambio = {"estado": "respondida", "nota_url": url}
            if responder_ig(q, "\u00a1Ya est\u00e1 la respuesta a tu pregunta! \U0001f4f0 " + url):
                cambio["respondida_ig"] = dt.datetime.now(dt.timezone.utc).isoformat()
            sb("PATCH", "?id=eq.%d" % q["id"], cambio)
            print("OK|pregunta %d respondida: %s" % (q["id"], url))
        elif f[0]["estado"] == "descartado":
            sb("PATCH", "?id=eq.%d" % q["id"], {"estado": "en_panel"})
            print("OK|pregunta %d: el pedido se cerro sin nota, vuelve al panel" % q["id"])


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
    for q in sb("GET", "?select=id,estado,origen,texto,pedido_id,nota_url&order=creado.desc&limit=30"):
        print("%(id)s|%(estado)s|%(origen)s|%(pedido_id)s|%(texto)s" % q)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    cmd = sys.argv[1]
    if cmd == "ciclo":
        ciclo()
    elif cmd == "ver":
        ver()
    elif cmd in ("cqi", "cqp", "cqd"):
        print(moderar_pregunta(sys.argv[2], cmd))
    elif cmd in ("cpi", "cpd"):
        print(moderar_pedido(sys.argv[2], cmd))
    else:
        raise SystemExit(__doc__)
