"""
pedidos_lectores.py -- pedidos de investigacion de los lectores (piloto del 12/10/2026).

Los pedidos entran por el bot de Telegram (desde el 13/10/2026, el UNICO canal para
pedir una investigacion; el portal junta preguntas, ver comunidad.py) a una tabla de
Supabase. Este script lee y cambia el estado con la llave secreta, que vive
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
# el enfoque corre en su propia tarea (12/10/2026), a veces al mismo tiempo que la
# redaccion: usa archivos propios para no pisarse
ACTUAL_ENFOQUE = os.path.join(ROOT, "_privado", "enfoque_pedido.json")
FRENA_ENFOQUE = os.path.join(ROOT, "_privado", "enfoque_frena.txt")
# lo que el lector senalo en la vista previa, para la corrida de correccion
REVISION = os.path.join(ROOT, "_privado", "revision.json")
EN_REVISION = ("en_revision", "revision_ok", "revision_error", "revision_feedback")
HORAS_COLGADO = 6     # en_investigacion sin borrador en la cola por mas de esto: la corrida se corto
HORAS_RESPUESTA = 24  # enfoque propuesto sin respuesta del lector: se avanza con lo propuesto
RONDAS_MAX = 3        # despues de 3 enfoques rechazados se investiga con lo que dijo el lector
# Editor, 12/10/2026 (periodo de prueba): toda investigacion pedida sale EL MISMO DIA.
# None = sin cupo diario. Para volver a una por dia: CUPO_DIARIO = 1.
CUPO_DIARIO = None
# rondas de "Sugerir cambios" por nota (editor, 13/10/2026: una sola era poco)
RONDAS_FEEDBACK = 3
HORAS_REVISION = 12  # vista previa al lector: sin respuesta en 12 h se publica igual (sin veto)
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
    t = m.get("tabla") or {}
    if t.get("columnas") and t.get("filas"):
        l.append(" | ".join(t["columnas"]))
        for fila in t["filas"][:4]:
            l.append(" | ".join(str(x) for x in fila))
        if t.get("faltan"):
            l.append("(faltan: %s)" % t["faltan"])
        l.append("")
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
        avisar(pid, "\u00a1Sali\u00f3 tu investigaci\u00f3n!\n" + texto + "\n\nGracias por pedirla. Cuando quieras pedir otra, "
               "escribime por ac\u00e1.")
    else:
        avisar(pid, "No pudimos convertir tu pedido en una nota. El motivo: " + texto[:600])


def contacto(p):
    """Hay a quien consultarle el enfoque: dejo correo o vinculo Telegram."""
    return bool(p.get("correo") or p.get("telegram_chat"))


def elegir(hoy, modo="investigar"):
    """modo investigar: la redaccion programada (cupo de una nota pedida por dia).
    modo enfoque: la tarea "Con Interes - Enfoque", que dispara el bot al llegar un pedido."""
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
    hechas_hoy = sum(1 for x in articulos() if x.get("pedido") and x.get("fecha") == hoy)
    if CUPO_DIARIO is not None:
        # con cupo, las que esperan la vista previa del lector cuentan como del dia
        hechas_hoy += len(pedir("GET", "?select=id&estado=in.(%s)" % ",".join(EN_REVISION)))
    hoy_salio = CUPO_DIARIO is not None and hechas_hoy >= CUPO_DIARIO
    if modo == "enfoque":
        if not enfocar:
            print("GENERAL|no hay pedidos esperando enfoque")
            return
        # el mas viejo primero: el que pidio antes recibe antes su enfoque
        p, fase = enfocar[0], "enfoque"
    elif investigar and (not hoy_salio or forzado):
        # por orden de llegada: el que pidio antes sale antes
        p, fase = investigar[0], "investigar"
    elif investigar:
        print("GENERAL|hoy ya salio una nota pedida por un lector (%d listos para investigar)" % len(investigar))
        return
    else:
        print("GENERAL|no hay pedidos para investigar")
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
    with open(ACTUAL_ENFOQUE if fase == "enfoque" else ACTUAL, "w", encoding="utf-8") as f:
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


def devolver_enfoque(pid, motivo):
    """La corrida de enfoque no dejo enfoque: vuelve a esperar uno. A los MAX_INTENTOS
    se investiga sin consultar (toda solicitud termina en nota)."""
    act = pedir("GET", "?select=intentos&id=eq.%d" % int(pid))
    if len(act) != 1:
        raise SystemExit("ERROR: no existe el pedido %s" % pid)
    n = act[0]["intentos"] + 1
    estado = "enfoque_aprobado" if n >= MAX_INTENTOS else "recibido"
    pedir("PATCH", "?id=eq.%d" % int(pid), {"estado": estado, "intentos": n, "motivo": motivo[:1000]})
    print("OK|pedido %s -> %s (enfoque fallido %d)" % (pid, estado, n))


def en_curso(chat):
    """Pedidos abiertos de un chat: editor 12/10/2026, una investigacion en curso por persona."""
    return pedir("GET", "?select=id,titulo,estado&telegram_chat=eq.%d"
                        "&estado=in.(moderacion,recibido,en_investigacion,enfoque_propuesto,enfoque_aprobado,en_revision,revision_ok,revision_error,revision_feedback)" % int(chat))


def crear_desde_chat(chat, titulo, tipo, detalle, solicitante=None):
    import uuid
    filas = pedir("POST", "", {"titulo": titulo, "tipo": tipo, "detalle": detalle or "",
                               "origen": "telegram", "telegram_chat": int(chat), "solicitante": solicitante,
                               "codigo_tg": str(uuid.uuid4())})
    return filas[0]["id"]


def tiene_telegram(pid):
    f = pedir("GET", "?select=telegram_chat&id=eq.%d" % int(pid))
    print("SI" if f and f[0].get("telegram_chat") else "NO")


def botones_revision(pid, rondas):
    """Primera vista previa: Publicar / Sugerir cambios / Error de datos. Despues de rehacerla
    con el feedback (una vez por nota), solo Publicar / Error de datos."""
    b = [[{"text": "\U0001f44d Publicar", "callback_data": "pub:%d" % int(pid)}]]
    if rondas < RONDAS_FEEDBACK:
        b.append([{"text": "\U0001f4ac Sugerir cambios", "callback_data": "fb:%d" % int(pid)}])
    b.append([{"text": "\U0001f4dd Error de datos", "callback_data": "err:%d" % int(pid)}])
    return b


def texto_revision(borrador, rondas, explicacion=""):
    quedan = RONDAS_FEEDBACK - rondas
    if rondas:
        cab = ("\u270d\ufe0f La rehicimos con lo que nos sugeriste" + (": " + explicacion if explicacion else ".")
               + "\n\nMirala de nuevo:\n")
        pie = ("Si est\u00e1 bien, toc\u00e1 \u00abPublicar\u00bb. Si ves un dato mal, \u00abError de datos\u00bb. "
               + ("Si todav\u00eda no es lo que buscabas, \u00abSugerir cambios\u00bb (te %s %d). "
                  % ("queda" if quedan == 1 else "quedan", quedan) if quedan > 0 else "")
               + "Si no nos escrib\u00eds en %d horas, sale as\u00ed." % HORAS_REVISION)
    else:
        cab = "\U0001f4f0 Tu investigaci\u00f3n est\u00e1 lista. Antes de publicarla, mirala vos primero:\n"
        pie = ("\u2022 \u00abSugerir cambios\u00bb: el t\u00edtulo, el enfoque del relato, el orden, qu\u00e9 destacar, algo que "
               "no se entiende. La rehacemos y te la mostramos otra vez (hasta %d veces).\n"
               "\u2022 \u00abError de datos\u00bb: un n\u00famero mal o algo que falta de lo que aprobaste; lo revisamos "
               "contra la fuente.\n\n"
               "Lo que no cambia es el resultado: es el que dan los datos. Si no nos escrib\u00eds en %d horas, "
               "sale as\u00ed." % (RONDAS_FEEDBACK, HORAS_REVISION))
    return cab + "https://coninteres.com/cola/%s.html\n\n" % borrador + pie


def a_revision(pid, borrador, rondas=0, explicacion=""):
    """Editor, 12-13/10/2026: el lector ve la nota antes de publicarla, SIN VETO."""
    hasta = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=HORAS_REVISION)
    filas = pedir("PATCH", "?id=eq.%d" % int(pid), {"estado": "en_revision", "borrador": borrador,
                                                      "revision_hasta": hasta.isoformat(),
                                                      "revision_rondas": int(rondas)})
    if len(filas) != 1 or filas[0]["estado"] != "en_revision":
        raise SystemExit("ERROR: el pedido %s no quedo en revision" % pid)
    print("OK|pedido %s -> en_revision (%s, ronda %d)" % (pid, borrador, int(rondas)))
    avisar(pid, texto_revision(borrador, int(rondas), explicacion), botones_revision(pid, int(rondas)))


def revisiones():
    """Que hacer con las vistas previas: CORREGIR (error de datos), REHACER (feedback) o
    PUBLICAR, |pid|borrador. Una por llamada (la redaccion hace una por corrida)."""
    ahora = dt.datetime.now(dt.timezone.utc).isoformat()
    f = pedir("GET", "?select=id,estado,borrador,revision_hasta,revision_comentario,titulo,detalle,enfoque"
                     "&estado=in.(%s)&order=revision_hasta" % ",".join(EN_REVISION))
    for p in f:
        if p["estado"] in ("revision_error", "revision_feedback"):
            os.makedirs(os.path.dirname(REVISION), exist_ok=True)
            with open(REVISION, "w", encoding="utf-8") as h:
                json.dump({"pedido": p["id"], "borrador": p["borrador"], "pregunta_del_lector": p["titulo"],
                           "detalle_del_pedido": p.get("detalle") or "",
                           "enfoque_aprobado": json.loads(p["enfoque"]) if p.get("enfoque") else None,
                           "tipo": "error_de_datos" if p["estado"] == "revision_error" else "sugerencia",
                           "lo_que_dijo_el_lector": p.get("revision_comentario") or ""},
                          h, ensure_ascii=False, indent=2)
            print("%s|%d|%s" % ("CORREGIR" if p["estado"] == "revision_error" else "REHACER", p["id"], p["borrador"]))
            return
    for p in f:
        if p["estado"] == "revision_ok" or (p["estado"] == "en_revision" and (p.get("revision_hasta") or "") < ahora):
            print("PUBLICAR|%d|%s" % (p["id"], p["borrador"]))
            return
    print("NADA|")


def borradores_en_revision():
    for p in pedir("GET", "?select=borrador&estado=in.(%s)" % ",".join(EN_REVISION)):
        if p.get("borrador"):
            print(p["borrador"])


def marcar_revision(pid, chat, accion, texto=""):
    """Lo usa el bot. accion: True/"ok" (publicar), False/"error" (error de datos) o
    "feedback" (sugerir cambios, una sola vez por nota)."""
    if accion is True:
        accion = "ok"
    elif accion is False:
        accion = "error"
    f = pedir("GET", "?select=estado,telegram_chat,revision_rondas&id=eq.%d" % int(pid))
    if not f or f[0].get("telegram_chat") != chat or f[0]["estado"] != "en_revision":
        return False
    if accion == "feedback" and (f[0].get("revision_rondas") or 0) >= RONDAS_FEEDBACK:
        return False
    cuerpo = {"ok": {"estado": "revision_ok"},
              "error": {"estado": "revision_error", "revision_comentario": texto[:1500]},
              "feedback": {"estado": "revision_feedback", "revision_comentario": texto[:1500]}}[accion]
    filas = pedir("PATCH", "?id=eq.%d&estado=eq.en_revision" % int(pid), cuerpo)
    return len(filas) == 1


def reenviar_vista_previa(pid):
    """Vuelve a mandar la vista previa vigente (por ejemplo, con botones nuevos)."""
    f = pedir("GET", "?select=estado,borrador,revision_rondas&id=eq.%d" % int(pid))
    if not f or f[0]["estado"] != "en_revision":
        raise SystemExit("ERROR: el pedido %s no esta en vista previa" % pid)
    avisar(pid, texto_revision(f[0]["borrador"], f[0].get("revision_rondas") or 0),
           botones_revision(pid, f[0].get("revision_rondas") or 0))


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
        filas = pedir("GET", "?select=id,creado,cerrado,origen,solicitante,tipo,estado,titulo,motivo,salida,correo,token"
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
    elif len(a) == 3 and a[0] == "elegir" and a[2] == "enfoque":
        elegir(a[1], "enfoque")
    elif len(a) == 2 and a[0] == "tiene_telegram":
        tiene_telegram(a[1])
    elif len(a) == 3 and a[0] == "a_revision":
        a_revision(a[1], a[2])
    elif len(a) == 4 and a[0] == "segunda_vista_previa":
        # una ronda mas de las que ya hubo
        r = pedir("GET", "?select=revision_rondas&id=eq.%d" % int(a[1]))
        a_revision(a[1], a[2], ((r[0].get("revision_rondas") or 0) if r else 0) + 1, a[3])
    elif len(a) == 2 and a[0] == "reenviar_vista_previa":
        reenviar_vista_previa(a[1])
    elif a == ["revisiones"]:
        revisiones()
    elif len(a) == 3 and a[0] == "avisar":
        avisar(a[1], a[2])
    elif a == ["borradores_en_revision"]:
        borradores_en_revision()
    elif len(a) == 3 and a[0] == "devolver_enfoque":
        devolver_enfoque(a[1], a[2])
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
