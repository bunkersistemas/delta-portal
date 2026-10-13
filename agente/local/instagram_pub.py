"""
instagram_pub.py -- publicaciones de Con Interes en Instagram (@coninteres.ar), con aprobacion
del editor por Telegram (editor, 13/10/2026).

Reglas (todo dentro de las politicas de Meta: solo contenido propio, volumen bajo, nada de
seguir, likes ni mensajes automaticos):
  - hasta 3 posteos por dia, en tres horarios (tarea "Con Interes - Instagram");
  - primero las notas "Pregunta de un lector"; despues, por seccion (lo que toca el
    bolsillo antes que lo tecnico), sin repetir seccion en el dia;
  - cada posteo le llega al editor por Telegram con la imagen y el texto: Publicar /
    Descartar. Sin respuesta en 60 minutos no se publica nada.

  ofrecer            elige la mejor nota disponible y se la manda al editor
  publicar <id>      la publica (lo llama el bot al tocar Publicar)
  descartar <id>     la saca y ofrece la siguiente
  renovar_token      renueva el token (vale 60 dias; la tarea semanal lo llama)
  texto <id>         muestra el texto del posteo (prueba)

El token y el chat del editor viven en la VM (coninteres-privado), nunca en el repo.
"""
import datetime as dt, json, os, re, sys, time, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pedidos_lectores as pl

PRIV = os.path.join(os.path.expanduser("~"), "coninteres-privado")
TOKEN = os.path.join(PRIV, "instagram_token.txt")
EDITOR = os.path.join(PRIV, "editor_telegram.txt")
ESTADO = os.path.join(pl.LOGS, "instagram_estado.json")
IG_ID = "17841475174871564"
API = "https://graph.instagram.com/v21.0/"
SITIO = "https://coninteres.com/"
POR_DIA = 3
MINUTOS_RESPUESTA = 60
PESO = {"DEPORTES": 30, "IA": 25, "ECONOM\u00cdA PROVINCIAL": 20, "ECONOM\u00cdA": 15, "MUNDO": 10,
        "EMPRESAS": 5, "MERCADOS": 0}
BOLSILLO = ("cobra", "cuesta", "sueldo", "salario", "jubil", "precio", "alquiler", "tarifa", "boleto",
            "aumento", "cuota", "gana", "pension", "pensi\u00f3n", "paga")
EMOJI = {"DEPORTES": "\U0001f3c5", "IA": "\U0001f916", "ECONOM\u00cdA PROVINCIAL": "\U0001f4cd",
         "MUNDO": "\U0001f30e", "EMPRESAS": "\U0001f3e2", "MERCADOS": "\U0001f4c8"}
HASHTAG = {"DEPORTES": "#deporte", "IA": "#inteligenciaartificial", "ECONOM\u00cdA PROVINCIAL": "#provincias",
           "MUNDO": "#mundo", "EMPRESAS": "#empresas", "MERCADOS": "#mercados"}


def hoy_ar():
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=3)).date().isoformat()


def leer_estado():
    try:
        return json.load(open(ESTADO, encoding="utf-8"))
    except Exception:
        return {"publicados": {}, "descartados": [], "pendiente": None}


def guardar_estado(e):
    tmp = ESTADO + ".tmp"
    json.dump(e, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, ESTADO)


def token():
    return open(TOKEN, encoding="ascii").read().strip()


def ig(metodo, ruta, datos=None):
    d = dict(datos or {}, access_token=token())
    if metodo == "GET":
        req = urllib.request.Request(API + ruta + "?" + urllib.parse.urlencode(d))
    else:
        req = urllib.request.Request(API + ruta, data=urllib.parse.urlencode(d).encode(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit("ERROR de Instagram: " + e.read().decode()[:400])


def imagen_url(a):
    return SITIO + "assets/ig/" + a["id"] + ".jpg"


def existe(url):
    try:
        # Cloudflare le cierra la puerta al "Python-urllib" generico: el publicador se
        # identifica con su nombre real (13/10/2026)
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD", headers={
                "User-Agent": "ConInteresPublicador/1.0 (+https://coninteres.com)"}), timeout=20) as r:
            return r.status == 200
    except Exception:
        return False


def gancho(a):
    sys.path.insert(0, os.path.join(pl.ROOT, "scripts"))
    import build_ig
    return build_ig.gancho(a)


def texto(a):
    """Corto y con disparador (editor, 13/10/2026): la pregunta, un dato que da curiosidad
    sacado de la nota (nunca inventado), el link de la bio y la invitacion a preguntar."""
    s = a.get("seccion", "")
    bajada = " ".join(str(a.get("bajada", "")).split())
    primera = re.split(r"(?<=[.!?])\s", bajada, maxsplit=1)[0] if bajada else ""
    if len(primera) > 220:
        primera = primera[:219].rsplit(" ", 1)[0] + "..."
    l = [gancho(a) + " " + EMOJI.get(s, "\U0001f4ca"), ""]
    if primera:
        l += [primera, ""]
    if a.get("pedido"):
        l.append("\U0001f64b Esta investigaci\u00f3n la pidi\u00f3 un lector.")
    l.append("\U0001f4ce La nota completa, con cada fuente: link en la bio.")
    l.append("\U0001f4ac \u00bfTe qued\u00f3 una pregunta? Dejala en los comentarios: las mejores las investigamos.")
    l += ["", " ".join(["#econom\u00eda", "#argentina", HASHTAG.get(s, "#datos")])]
    return "\n".join(l)


def candidatos(e):
    """Notas de las ultimas 36 horas, ordenadas. Ya publicadas o descartadas, afuera."""
    desde = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=39)).date().isoformat()
    hoy = hoy_ar()
    secciones_hoy = {p.get("seccion") for p in e["publicados"].values() if p.get("dia") == hoy}
    out = []
    for a in pl.articulos():
        if a.get("fecha", "") < desde or a["id"] in e["publicados"] or a["id"] in e["descartados"]:
            continue
        p = 100 if a.get("pedido") else PESO.get(a.get("seccion", ""), 10)
        t = (a.get("titulo", "") + " " + a.get("titulo_busqueda", "")).lower()
        if any(b in t for b in BOLSILLO):
            p += 15
        if len(str(a.get("numero", ""))) <= 10:
            p += 5
        if a.get("seccion") in secciones_hoy and not a.get("pedido"):
            p -= 40          # variedad: no dos de la misma seccion en el dia
        out.append((p, a.get("fecha", ""), a.get("hora", ""), a))
    out.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    return [a for *_, a in out]


def editor():
    return int(open(EDITOR, encoding="ascii").read().strip())


def ofrecer(forzar=False):
    e = leer_estado()
    hoy = hoy_ar()
    if sum(1 for p in e["publicados"].values() if p.get("dia") == hoy) >= POR_DIA and not forzar:
        print("NADA|ya salieron %d posteos hoy" % POR_DIA)
        return
    pen = e.get("pendiente")
    if pen:
        edad = (time.time() - pen["ts"]) / 60
        if edad < MINUTOS_RESPUESTA:
            print("NADA|hay uno esperando respuesta (%s)" % pen["id"])
            return
        e["descartados"].append(pen["id"])   # sin respuesta: no se publica
        e["pendiente"] = None
    for a in candidatos(e):
        if not existe(imagen_url(a)):
            continue
        txt = texto(a)
        pl.tg("sendPhoto", {"chat_id": editor(), "photo": imagen_url(a),
                            "caption": ("\U0001f4f8 Propuesta para Instagram\n\n" + txt)[:1024],
                            "reply_markup": {"inline_keyboard": [
                                [{"text": "\u2705 Publicar", "callback_data": "igpub:" + a["id"][:50]},
                                 {"text": "\u274c Descartar", "callback_data": "igdes:" + a["id"][:50]}]]}})
        e["pendiente"] = {"id": a["id"], "ts": time.time()}
        guardar_estado(e)
        print("OK|ofrecida %s" % a["id"])
        return
    guardar_estado(e)
    print("NADA|no hay notas nuevas con imagen para ofrecer")


HORARIOS = ("12:30", "18:30", "21:30")   # hora argentina (editor, 13/10/2026)


def turno():
    """Lo llama la tarea cada 15 minutos: si en la Argentina es la hora de un horario (hasta
    50 minutos despues) y ese horario no se uso hoy, ofrece una nota. Asi el cambio de hora
    de la VM (Madrid) no corre los horarios."""
    ahora = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=3)
    e = leer_estado()
    hechos = e.setdefault("turnos", {})
    for h in HORARIOS:
        hh, mm = map(int, h.split(":"))
        ini = ahora.replace(hour=hh, minute=mm, second=0, microsecond=0)
        clave = ahora.date().isoformat() + " " + h
        if ini <= ahora < ini + dt.timedelta(minutes=50) and clave not in hechos:
            hechos[clave] = time.time()
            guardar_estado(e)
            print("turno %s" % clave)
            ofrecer()
            return
    print("NADA|no es horario de Instagram")


def articulo(id_):
    for a in pl.articulos():
        if a["id"].startswith(id_):
            return a
    raise SystemExit("ERROR: no esta la nota %s" % id_)


def publicar(id_):
    e = leer_estado()
    a = articulo(id_)
    if a["id"] in e["publicados"]:
        return {"ya": True, "permalink": e["publicados"][a["id"]].get("permalink")}
    cont = ig("POST", IG_ID + "/media", {"image_url": imagen_url(a), "caption": texto(a)})
    for _ in range(20):
        st = ig("GET", cont["id"], {"fields": "status_code"})
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") == "ERROR":
            raise SystemExit("ERROR: Instagram no pudo procesar la imagen")
        time.sleep(3)
    pub = ig("POST", IG_ID + "/media_publish", {"creation_id": cont["id"]})
    link = ig("GET", pub["id"], {"fields": "permalink"}).get("permalink", "")
    e["publicados"][a["id"]] = {"dia": hoy_ar(), "seccion": a.get("seccion"), "media": pub["id"],
                                "permalink": link, "ts": time.time()}
    if e.get("pendiente") and e["pendiente"]["id"] == a["id"]:
        e["pendiente"] = None
    guardar_estado(e)
    # la pagina de la bio lo lee de aca
    k = open(pl.LLAVE, encoding="ascii").read().strip()
    req = urllib.request.Request(pl.URL.replace("/pedidos", "/ig_publicaciones"), method="POST",
                                 data=json.dumps({"nota_id": a["id"], "titulo": a["titulo"], "gancho": gancho(a),
                                                  "imagen_url": imagen_url(a), "nota_url": SITIO + a["archivo"],
                                                  "ig_media_id": pub["id"], "permalink": link}).encode(),
                                 headers={"apikey": k, "Authorization": "Bearer " + k,
                                          "Content-Type": "application/json", "Prefer": "return=minimal"})
    try:
        urllib.request.urlopen(req, timeout=30)
    except Exception as ex:
        print("AVISO|no se registro en la pagina de la bio: %s" % ex)
    print("OK|publicada %s %s" % (a["id"], link))
    return {"permalink": link}


def descartar(id_):
    e = leer_estado()
    a = articulo(id_)
    if a["id"] not in e["descartados"]:
        e["descartados"].append(a["id"])
    if e.get("pendiente") and e["pendiente"]["id"] == a["id"]:
        e["pendiente"] = None
    guardar_estado(e)
    ofrecer()


def renovar_token():
    r = json.load(urllib.request.urlopen(
        "https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token="
        + urllib.parse.quote(token()), timeout=30))
    open(TOKEN, "w", encoding="ascii").write(r["access_token"])
    print("OK|token renovado, vence en %d dias" % (r.get("expires_in", 0) // 86400))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["turno"]:
        turno()
    elif a == ["ofrecer"]:
        ofrecer()
    elif len(a) == 2 and a[0] == "publicar":
        publicar(a[1])
    elif len(a) == 2 and a[0] == "descartar":
        descartar(a[1])
    elif a == ["renovar_token"]:
        renovar_token()
    elif len(a) == 2 and a[0] == "texto":
        sys.stdout.buffer.write((texto(articulo(a[1])) + "\n").encode("utf-8"))
    else:
        print(__doc__)
        sys.exit(1)
