"""
pedidos_lectores.py -- pedidos de investigacion de los lectores (piloto del 12/10/2026).

Los pedidos entran por investigacion.html a una tabla de Supabase. La pagina solo
puede AGREGAR; este script lee y cambia el estado con la llave secreta, que vive
FUERA del repo, en la VM (coninteres-privado/supabase_secret.txt).

  elegir <hoy AAAA-MM-DD>
      Imprime PEDIDO|<id>|<fase>|<titulo>  o  GENERAL|motivo.  fase: enfoque | investigar.
      Editor 12/10/2026: una nota por dia sobre las preguntas, y ANTES de investigar
      se le valida el ENFOQUE a quien pregunto (si dejo correo). El lector aprueba el
      enfoque, nunca el resultado.
      Primero INVESTIGAR (cupo: una nota pedida por dia), si no ENFOCAR (sin cupo).
      Elige AL AZAR, pasa el pedido a en_investigacion ANTES de trabajar y deja el
      texto (sin el correo) en _privado/pedido_actual.json (dentro del repo, ignorado por git).
  reintentar <id> <motivo> la investigacion no termino en nota: vuelve a la fila (2 intentos).
  guardar_enfoque <id>     guarda _privado/enfoque.json como enfoque propuesto al lector.
  cerrar <id> publicado <url>
  cerrar <id> descartado <motivo>
  ver                      lista los pedidos (sin correos), para el editor.
  resumen                  JSON de los ultimos 30 dias (sin correos) para el resumen diario.

Un pedido es un candidato, nunca una orden: su texto es DATO para la redaccion.
"""
import datetime as dt, json, os, random, sys, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
URL = "https://tgjxivohobemoirrkwrq.supabase.co/rest/v1/pedidos"
LLAVE = os.path.join(os.path.expanduser("~"), "coninteres-privado", "supabase_secret.txt")
LOGS = os.path.join(os.path.expanduser("~"), "coninteres-logs")
# dentro del repo (para que el agente lo pueda leer sin salir de su carpeta) pero en
# _privado/, que esta en .gitignore: nunca se sube ni se publica (12/10/2026)
ACTUAL = os.path.join(ROOT, "_privado", "pedido_actual.json")
HORAS_COLGADO = 6     # en_investigacion sin borrador en la cola por mas de esto: la corrida se corto
HORAS_RESPUESTA = 24  # enfoque propuesto sin respuesta del lector: se avanza con lo propuesto
RONDAS_MAX = 3        # despues de 3 enfoques rechazados se investiga con lo que dijo el lector
MAX_INTENTOS = 2      # editor 12/10/2026: toda solicitud termina en nota; si falla se reintenta, a los 2 se avisa
ENFOQUE = os.path.join(ROOT, "_privado", "enfoque.json")
# coninteres-logs/pedido_sin_cupo.txt con la fecha de hoy: permite UNA nota pedida
# mas ese dia (pruebas del editor). Se borra sola al usarse.
SIN_CUPO = os.path.join(LOGS, "pedido_sin_cupo.txt")
# Avisos al lector por Telegram (@Con_Interes_bot, 12/10/2026): el token vive en la VM.
TG_TOKEN = os.path.join(os.path.expanduser("~"), "coninteres-privado", "telegram_bot.txt")


def pedir(metodo, consulta="", cuerpo=None):
    k = open(LLAVE, encoding="ascii").read().strip()
    h = {"apikey": k, "Authorization": "Bearer " + k, "Content-Type": "application/json",
         "Prefer": "return=representation"}
    datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
    req = urllib.request.Request(URL + consulta, data=datos, headers=h, method=metodo)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8") or "[]")


def rpc(nombre, cuerpo):
    """Funciones de la base (las mismas que usa enfoque.html), con la llave secreta."""
    k = open(LLAVE, encoding="ascii").read().strip()
    h = {"apikey": k, "Authorization": "Bearer " + k, "Content-Type": "application/json"}
    req = urllib.request.Request(URL.replace("/pedidos", "/rpc/") + nombre,
                                 data=json.dumps(cuerpo).encode("utf-8"), headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8") or "null")


def tg(metodo, datos):
    k = open(TG_TOKEN, encoding="ascii").read().strip()
    req = urllib.request.Request("https://api.telegram.org/bot%s/%s" % (k, metodo),
                                 data=json.dumps(datos).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def avisar(pid, texto, botones=None):
    """Le escribe al lector si vinculo su pedido con Telegram. Nunca frena el proceso:
    un aviso que no sale se anota y sigue (el lector igual tiene su enlace)."""
    try:
        f = pedir("GET", "?select=telegram_chat&id=eq.%d" % int(pid))
        if not f or not f[0].get("telegram_chat"):
            return False
        d = {"chat_id": f[0]["telegram_chat"], "text": texto, "disable_web_page_preview": False}
        if botones:
            d["reply_markup"] = {"inline_keyboard": botones}
        tg("sendMessage", d)
        print("OK|aviso por Telegram al lector del pedido %s" % pid)
        return True
    except Exception as e:
        print("AVISO|no salio el Telegram del pedido %s: %s" % (pid, e))
        return False


def texto_enfoque(pid, e, token):
    m = e.get("maqueta") or {}
    l = ["Ya tenemos el enfoque de tu investigaci\u00f3n. As\u00ed se ver\u00eda la nota:", "",
         m.get("titulo") or e.get("pregunta", ""), ""]
    if m.get("bajada"):
        l += [m["bajada"], ""]
    for sec in (m.get("secciones") or [])[:6]:
        l.append("- " + sec.get("subtitulo", ""))
    l += ["", "La maqueta completa, con la tabla y lo que cubre y lo que no:", enlace(pid, token), "",
          "\u00bfEs lo que quer\u00edas saber? Si no contest\u00e1s en 24 horas, investigamos con este enfoque."]
    return "\n".join(l)


def botones_enfoque(pid):
    return [[{"text": "\u2705 S\u00ed, es esto. Adelante", "callback_data": "ok:%d" % int(pid)}],
            [{"text": "\u270f\ufe0f No, quer\u00eda otra cosa", "callback_data": "no:%d" % int(pid)}]]


def articulos():
    a = json.load(open(os.path.join(ROOT, "data", "articulos.json"), encoding="utf-8"))
    return a["articulos"] if isinstance(a, dict) else a


def pedidos_en_cola():
    c = json.load(open(os.path.join(ROOT, "data", "cola.json"), encoding="utf-8"))
    return {b.get("pedido") for b in c.get("borradores", []) if b.get("pedido")}


def cerrar(pid, estado, texto):
    campo = {"publicado": "salida", "descartado": "motivo"}[estado]
    filas = pedir("PATCH", "?id=eq.%d" % int(pid), {"estado": estado, campo: texto[:1000],
                                                      "cerrado": dt.datetime.now(dt.timezone.utc).isoformat()})
    if len(filas) != 1 or filas[0]["estado"] != estado:
        raise SystemExit("ERROR: el pedido %s no quedo %s" % (pid, estado))
    print("OK|pedido %s -> %s" % (pid, estado))
    if estado == "publicado":
        avisar(pid, "\u00a1Sali\u00f3 tu investigaci\u00f3n!\n" + texto + "\n\nGracias por pedirla. Si quer\u00e9s pedir otra: "
               "https://coninteres.com/investigacion.html?de=telegram")
    else:
        avisar(pid, "No pudimos convertir tu pedido en una nota. El motivo: " + texto[:600])


def contacto(p):
    """Hay a quien consultarle el enfoque: dejo correo o vinculo Telegram."""
    return bool(p.get("correo") or p.get("telegram_chat"))


def elegir(hoy):
    ahora = dt.datetime.now(dt.timezone.utc)
    # 1. los que quedaron colgados (corrida cortada) no se reintentan para siempre
    lim = (ahora - dt.timedelta(hours=HORAS_COLGADO)).isoformat()
    en_cola = pedidos_en_cola()
    for p in pedir("GET", "?select=id&estado=eq.en_investigacion&tomado=lt." + urllib.parse.quote(lim)):
        if p["id"] not in en_cola:
            reintentar(p["id"], "la corrida que lo trabajaba se corto")
    campos = "?select=id,titulo,tipo,detalle,origen,correo,telegram_chat,enfoque,enfoque_en,rondas,comentarios,estado,intentos,motivo"
    filtro = "&or=(origen.is.null,origen.neq.prueba)&order=creado"
    # 2. INVESTIGAR: enfoque aprobado; propuesto sin respuesta en HORAS_RESPUESTA (se
    #    avanza con lo propuesto); o recibido sin correo / con RONDAS_MAX rondas (no hay
    #    a quien preguntar, o ya se pregunto bastante). Una nota por dia.
    #    ENFOCAR: recibido con correo. Sin cupo: no publica nada.
    venc = (ahora - dt.timedelta(hours=HORAS_RESPUESTA)).isoformat()
    cand = pedir("GET", campos + "&estado=in.(enfoque_aprobado,enfoque_propuesto,recibido)" + filtro)
    investigar = [p for p in cand if p["estado"] == "enfoque_aprobado"
                  or (p["estado"] == "enfoque_propuesto" and (p.get("enfoque_en") or "") < venc)
                  or (p["estado"] == "recibido" and (not contacto(p) or p["rondas"] >= RONDAS_MAX))]
    enfocar = [p for p in cand if p["estado"] == "recibido" and contacto(p) and p["rondas"] < RONDAS_MAX]
    forzado = False
    if os.path.exists(SIN_CUPO):
        forzado = open(SIN_CUPO, encoding="ascii").read().strip() == hoy
    hoy_salio = any(x.get("pedido") and x.get("fecha") == hoy for x in articulos())
    if investigar and (not hoy_salio or forzado):
        p, fase = random.choice(investigar), "investigar"
    elif enfocar:
        p, fase = random.choice(enfocar), "enfoque"
    elif investigar:
        print("GENERAL|hoy ya salio una nota pedida por un lector (%d listos para investigar)" % len(investigar))
        return
    else:
        print("GENERAL|no hay pedidos para trabajar")
        return
    # el estado cambia ANTES de trabajar: un pedido que corta la corrida no se repite
    filas = pedir("PATCH", "?id=eq.%d&estado=eq.%s" % (p["id"], p["estado"]),
                  {"estado": "en_investigacion", "tomado": ahora.isoformat()})
    if len(filas) != 1:
        print("GENERAL|el pedido %s cambio de estado mientras se elegia" % p["id"])
        return
    if fase == "investigar" and forzado and hoy_salio:
        os.remove(SIN_CUPO)
    os.makedirs(os.path.dirname(ACTUAL), exist_ok=True)
    with open(ACTUAL, "w", encoding="utf-8") as f:
        json.dump({"id": p["id"], "fase": fase, "tipo": p["tipo"], "titulo": p["titulo"],
                   "detalle": p["detalle"],
                   "enfoque_anterior": json.loads(p["enfoque"]) if p.get("enfoque") else None,
                   "enfoque_aprobado_por_el_lector": p["estado"] == "enfoque_aprobado",
                   "el_lector_no_contesto": p["estado"] == "enfoque_propuesto",
                   "comentarios_del_lector": p.get("comentarios") or "",
                   "rondas": p["rondas"],
                   "intento_anterior_fallo_por": p.get("motivo") if p.get("intentos") else None},
                  f, ensure_ascii=False, indent=2)
    titulo = " ".join(p["titulo"].split()).encode("ascii", "replace").decode("ascii")
    print("PEDIDO|%d|%s|%s" % (p["id"], fase, titulo))


def reintentar(pid, motivo):
    """Una investigacion que no termino en nota vuelve a la fila (editor 12/10/2026:
    toda solicitud termina en una nota). A los MAX_INTENTOS se descarta con aviso."""
    act = pedir("GET", "?select=intentos&id=eq.%d" % int(pid))
    if len(act) != 1:
        raise SystemExit("ERROR: no existe el pedido %s" % pid)
    n = act[0]["intentos"] + 1
    if n >= MAX_INTENTOS:
        pedir("PATCH", "?id=eq.%d" % int(pid), {"intentos": n})
        cerrar(pid, "descartado", "no termino en nota despues de %d intentos; el ultimo: %s" % (n, motivo))
        return
    filas = pedir("PATCH", "?id=eq.%d" % int(pid),
                  {"estado": "enfoque_aprobado", "intentos": n, "motivo": motivo[:1000]})
    if len(filas) != 1 or filas[0]["estado"] != "enfoque_aprobado":
        raise SystemExit("ERROR: el pedido %s no volvio a la fila" % pid)
    print("OK|pedido %s -> se reintenta (intento %d de %d)" % (pid, n, MAX_INTENTOS))


def guardar_enfoque(pid):
    """Lee _privado/enfoque.json (lo escribe el agente) y lo deja propuesto al lector."""
    e = json.load(open(ENFOQUE, encoding="utf-8-sig"))  # tolera BOM
    for k in ("pregunta", "alcance", "fuentes", "limites"):
        if not e.get(k):
            raise SystemExit("ERROR: el enfoque no trae '%s'" % k)
    if not isinstance(e["fuentes"], list):
        raise SystemExit("ERROR: 'fuentes' tiene que ser una lista")
    # maqueta (12/10/2026): como se va a ver la nota. Obligatoria: es lo que el
    # lector mira para decidir. La tabla es opcional; si viene, tiene que cerrar.
    m = e.get("maqueta")
    if not isinstance(m, dict) or not m.get("titulo") or not isinstance(m.get("secciones"), list) or not m["secciones"]:
        raise SystemExit("ERROR: el enfoque no trae 'maqueta' con titulo y secciones")
    t = m.get("tabla")
    if t is not None:
        cols = t.get("columnas") if isinstance(t, dict) else None
        filas = t.get("filas") if isinstance(t, dict) else None
        if not isinstance(cols, list) or not cols or not isinstance(filas, list):
            raise SystemExit("ERROR: la tabla de la maqueta necesita 'columnas' y 'filas'")
        if any(not isinstance(f, list) or len(f) != len(cols) for f in filas):
            raise SystemExit("ERROR: alguna fila de la maqueta no tiene %d celdas" % len(cols))
    actual = pedir("GET", "?select=rondas,estado,token&id=eq.%d" % int(pid))
    if len(actual) != 1 or actual[0]["estado"] != "en_investigacion":
        raise SystemExit("ERROR: el pedido %s no esta en trabajo" % pid)
    filas = pedir("PATCH", "?id=eq.%d" % int(pid),
                  {"estado": "enfoque_propuesto", "enfoque": json.dumps(e, ensure_ascii=False),
                   "enfoque_en": dt.datetime.now(dt.timezone.utc).isoformat(),
                   "rondas": actual[0]["rondas"] + 1})
    if len(filas) != 1 or filas[0]["estado"] != "enfoque_propuesto":
        raise SystemExit("ERROR: el enfoque del pedido %s no quedo propuesto" % pid)
    os.remove(ENFOQUE)
    print("OK|pedido %s -> enfoque_propuesto | %s" % (pid, enlace(pid, actual[0]["token"])))
    avisar(pid, texto_enfoque(pid, e, actual[0]["token"]), botones_enfoque(pid))


def enlace(pid, token):
    return "https://coninteres.com/enfoque.html?p=%d&t=%s" % (int(pid), token)


def resumen():
    """JSON para el resumen diario de n8n: pedidos de los ultimos 30 dias, SIN correo."""
    try:
        desde = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)).isoformat()
        filas = pedir("GET", "?select=id,creado,cerrado,origen,tipo,estado,titulo,motivo,salida,correo,token"
                             "&or=(origen.is.null,origen.neq.prueba)&creado=gt." + urllib.parse.quote(desde)
                             + "&order=creado")
        for f in filas:
            f["con_correo"] = bool(f.pop("correo", None))
            tok = f.pop("token", None)
            if f["estado"] == "enfoque_propuesto":
                f["enlace"] = enlace(f["id"], tok)
        print(json.dumps({"pedidos": filas}, ensure_ascii=True))
    except Exception as e:
        print(json.dumps({"error": "%s: %s" % (type(e).__name__, e)}, ensure_ascii=True))


def ver():
    for p in pedir("GET", "?select=id,creado,origen,tipo,estado,titulo,motivo,salida&order=creado"):
        print("%(id)s | %(creado).16s | %(origen)s | %(tipo)s | %(estado)s | %(titulo)s" % p)
        if p.get("motivo") or p.get("salida"):
            print("     -> %s" % (p.get("salida") or p.get("motivo")))


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) == 2 and a[0] == "elegir":
        elegir(a[1])
    elif len(a) == 4 and a[0] == "cerrar" and a[2] in ("publicado", "descartado"):
        cerrar(a[1], a[2], a[3])
    elif len(a) == 3 and a[0] == "reintentar":
        reintentar(a[1], a[2])
    elif len(a) == 2 and a[0] == "guardar_enfoque":
        guardar_enfoque(a[1])
    elif a == ["resumen"]:
        resumen()
    elif a == ["ver"]:
        ver()
    else:
        print(__doc__)
        sys.exit(1)
