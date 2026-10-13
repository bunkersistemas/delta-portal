"""
vigilante.py -- "El Vigilante": la conversacion de @Con_Interes_bot (editor, 12/10/2026).

Un amigo que investiga: imparcial, honesto, no politico, con datos que hacen pensar.
La personalidad esta en vigilante_persona.md. Claude conversa, pero SOLO puede hacer
cinco cosas, todas sobre los pedidos de ESE chat (el chat lo pone este codigo, nunca
el modelo):
  buscar_notas, crear_pedido, mis_pedidos, responder_enfoque, responder_vista_previa.
No tiene acceso a nada mas: ni al sitio, ni a git, ni a otros chats, ni a la web.

La clave de la API (con tope de gasto) vive en la VM:
coninteres-privado/anthropic_api.txt. Historial corto por chat (texto, sin bloques
de razonamiento) en coninteres-logs/vigilante/.
"""
import json, os, re, sys, time, unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pedidos_lectores as pl

MODELO = "claude-opus-5-5"
ESFUERZO = "low"            # charla: rapido y barato; subir solo si se mide que hace falta
MAX_TOKENS = 2000
TURNOS_HISTORIAL = 8        # pares usuario/Vigilante que se le recuerdan
TOPE_DIARIO = 40            # mensajes por chat por dia (freno de costo y de abuso)
CLAVE = os.path.join(os.path.expanduser("~"), "coninteres-privado", "anthropic_api.txt")
HIST = os.path.join(pl.LOGS, "vigilante")
PERSONA = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "vigilante_persona.md"),
               encoding="utf-8").read()
SITIO = "https://coninteres.com/"
TIPOS = ["cuanto-cuesta", "verificar-cifra", "comparar", "otro"]

TOOLS = [
    {"name": "buscar_notas", "strict": True,
     "description": "Busca entre las notas publicadas de Con Interes (todas verificadas). Devuelve titulo, "
                    "bajada, fecha, la cifra principal y el link. Es la UNICA fuente de numeros que podes dar.",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["consulta"],
                      "properties": {"consulta": {"type": "string", "description": "palabras clave del tema"}}}},
    {"name": "crear_pedido", "strict": True,
     "description": "Crea un pedido de investigacion para esta persona. Usala SOLO despues de que la persona "
                    "dijo que si a la pregunta como se la mostraste. Cada persona puede tener una sola "
                    "investigacion en curso: si ya tiene una, la herramienta lo avisa.",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["titulo", "tipo", "detalle"],
                      "properties": {
                          "titulo": {"type": "string", "description": "la pregunta, en una linea (5 a 140 letras)"},
                          "tipo": {"type": "string", "enum": TIPOS},
                          "detalle": {"type": "string", "description": "lo que la persona aclaro: alcance, lugar, "
                                                                     "periodo, con que comparar; vacio si nada"}}}},
    {"name": "mis_pedidos", "strict": True,
     "description": "Los pedidos de investigacion de esta persona y en que estado esta cada uno.",
     "input_schema": {"type": "object", "additionalProperties": False, "properties": {}}},
    {"name": "responder_enfoque", "strict": True,
     "description": "Registra la respuesta de esta persona al ENFOQUE que le mandamos de uno de sus pedidos: "
                    "aprueba (true) o pide otro enfoque (false, con lo que quiere cambiar en comentario).",
     "input_schema": {"type": "object", "additionalProperties": False,
                      "required": ["pedido_id", "aprueba", "comentario"],
                      "properties": {"pedido_id": {"type": "integer"}, "aprueba": {"type": "boolean"},
                                     "comentario": {"type": "string"}}}},
    {"name": "responder_vista_previa", "strict": True,
     "description": "Registra la respuesta a la VISTA PREVIA de la nota: publicar (true) o marcar un error "
                    "(false, con el error y la fuente si la dio en comentario). No existe 'no publicar': "
                    "un error se revisa contra la fuente y despues la nota sale igual.",
     "input_schema": {"type": "object", "additionalProperties": False,
                      "required": ["pedido_id", "publicar", "comentario"],
                      "properties": {"pedido_id": {"type": "integer"}, "publicar": {"type": "boolean"},
                                     "comentario": {"type": "string"}}}},
]


def _plano(t):
    t = unicodedata.normalize("NFKD", (t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def buscar_notas(consulta):
    palabras = [p for p in re.findall(r"[a-z0-9]+", _plano(consulta)) if len(p) > 2]
    if not palabras:
        return {"notas": []}
    puntaje = []
    for a in pl.articulos():
        texto = _plano(" ".join(str(a.get(k, "")) for k in
                                ("titulo", "titulo_busqueda", "bajada", "numero_label", "seccion")))
        # primero cuantas palabras distintas de la consulta aparecen, despues cuantas veces
        p = (sum(1 for w in palabras if w in texto), sum(texto.count(w) for w in palabras))
        if p[0]:
            puntaje.append((p, a.get("fecha", ""), a))
    puntaje.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return {"notas": [{"titulo": a["titulo"], "bajada": a.get("bajada", "")[:400], "fecha": a.get("fecha", ""),
                       "cifra": ("%s %s" % (a.get("numero", ""), a.get("numero_label", ""))).strip()[:300],
                       "link": SITIO + a.get("archivo", "")} for _, _, a in puntaje[:5]]}


def mis_pedidos(chat):
    f = pl.pedir("GET", "?select=id,titulo,estado,salida,motivo,creado&telegram_chat=eq.%d"
                        "&order=creado.desc&limit=10" % int(chat))
    return {"pedidos": [{"id": p["id"], "titulo": p["titulo"], "estado": p["estado"],
                         "link_nota": p.get("salida"), "motivo": (p.get("motivo") or "")[:200]} for p in f]}


def crear_pedido(chat, titulo, tipo, detalle):
    titulo = " ".join((titulo or "").split())
    if not 5 <= len(titulo) <= 140:
        return {"error": "el titulo tiene que tener entre 5 y 140 letras"}
    if tipo not in TIPOS:
        tipo = "otro"
    abiertos = pl.en_curso(chat)
    if abiertos:
        return {"error": "ya tiene una investigacion en curso", "en_curso": abiertos[0]}
    pid = pl.crear_desde_chat(chat, titulo, tipo, (detalle or "")[:1500])
    return {"ok": True, "pedido_id": pid,
            "que_sigue": "la redaccion arma el enfoque y se lo manda por este chat en unos minutos"}


def responder_enfoque(chat, pid, aprueba, comentario):
    f = pl.pedir("GET", "?select=id,estado,token,telegram_chat&id=eq.%d" % int(pid))
    if not f or f[0].get("telegram_chat") != chat:
        return {"error": "ese pedido no es de esta persona"}
    if f[0]["estado"] != "enfoque_propuesto":
        return {"error": "ese pedido no tiene un enfoque esperando respuesta", "estado": f[0]["estado"]}
    if not aprueba and len((comentario or "").strip()) < 3:
        return {"error": "para pedir otro enfoque hace falta saber que quiere cambiar"}
    r = pl.rpc("enfoque_responder", {"p_id": int(pid), "p_token": f[0]["token"], "p_ok": bool(aprueba),
                                     "p_texto": (comentario or "")[:1500] or None})
    return {"resultado": r}


def responder_vista_previa(chat, pid, publicar, comentario):
    if not publicar and len((comentario or "").strip()) < 3:
        return {"error": "para marcar un error hace falta saber cual es"}
    ok = pl.marcar_revision(pid, chat, bool(publicar), comentario or "")
    return {"ok": ok} if ok else {"error": "ese pedido no tiene una vista previa esperando respuesta"}


def ejecutar(chat, nombre, entrada):
    try:
        if nombre == "buscar_notas":
            return buscar_notas(entrada.get("consulta", ""))
        if nombre == "mis_pedidos":
            return mis_pedidos(chat)
        if nombre == "crear_pedido":
            return crear_pedido(chat, entrada.get("titulo"), entrada.get("tipo"), entrada.get("detalle"))
        if nombre == "responder_enfoque":
            return responder_enfoque(chat, entrada["pedido_id"], entrada["aprueba"], entrada.get("comentario"))
        if nombre == "responder_vista_previa":
            return responder_vista_previa(chat, entrada["pedido_id"], entrada["publicar"], entrada.get("comentario"))
        return {"error": "herramienta desconocida"}
    except Exception as e:
        return {"error": "fallo interno: %s" % type(e).__name__}


# ---- historial corto y tope diario --------------------------------------------
def _hist_path(chat):
    os.makedirs(HIST, exist_ok=True)
    return os.path.join(HIST, "%d.json" % int(chat))


def leer_hist(chat):
    try:
        return json.load(open(_hist_path(chat), encoding="utf-8"))
    except Exception:
        return {"turnos": [], "dia": "", "usados": 0}


def guardar_hist(chat, h):
    h["turnos"] = h["turnos"][-TURNOS_HISTORIAL:]
    tmp = _hist_path(chat) + ".tmp"
    json.dump(h, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, _hist_path(chat))


def responder(chat, texto, cliente=None, acciones=None):
    """Devuelve el texto de El Vigilante. `acciones` (lista) recibe lo que se ejecuto,
    para que el bot dispare el enfoque o la redaccion cuando corresponde."""
    hoy = time.strftime("%Y-%m-%d")
    h = leer_hist(chat)
    if h.get("dia") != hoy:
        h["dia"], h["usados"] = hoy, 0
    if h["usados"] >= TOPE_DIARIO:
        return ("Hoy ya charlamos un mont\u00f3n \U0001f604 Ma\u00f1ana seguimos. Si ten\u00e9s un pedido en curso, "
                "te aviso por ac\u00e1 cuando haya novedades.")
    h["usados"] += 1
    if cliente is None:
        import anthropic
        cliente = anthropic.Anthropic(api_key=open(CLAVE, encoding="ascii").read().strip())
    # el historial va como texto plano (sin bloques de razonamiento de turnos viejos)
    mensajes = []
    for t in h["turnos"]:
        mensajes.append({"role": "user", "content": t["u"]})
        mensajes.append({"role": "assistant", "content": t["a"]})
    hoy_ar = time.strftime("%d/%m/%Y")
    mensajes.append({"role": "user", "content": "[%s] %s" % (hoy_ar, texto[:3000])})
    final = ""
    for _ in range(6):
        r = cliente.beta.messages.create(
            model=MODELO, max_tokens=MAX_TOKENS,
            system=[{"type": "text", "text": PERSONA, "cache_control": {"type": "ephemeral"}}],
            tools=TOOLS, messages=mensajes,
            output_config={"effort": ESFUERZO},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",   # si un filtro de seguridad rechaza, otro modelo contesta
        )
        if r.stop_reason == "refusal":
            final = "De eso prefiero no hablar. \u00bfTe ayudo con algo de econom\u00eda y datos?"
            break
        usos = [b for b in r.content if b.type == "tool_use"]
        texto_r = "".join(b.text for b in r.content if b.type == "text").strip()
        if r.stop_reason != "tool_use" or not usos:
            final = texto_r
            break
        mensajes.append({"role": "assistant", "content": r.content})
        resultados = []
        for u in usos:
            res = ejecutar(chat, u.name, u.input or {})
            if acciones is not None:
                acciones.append((u.name, u.input, res))
            resultados.append({"type": "tool_result", "tool_use_id": u.id,
                               "content": json.dumps(res, ensure_ascii=False)})
        mensajes.append({"role": "user", "content": resultados})
    if not final:
        final = "Se me mezclaron los papeles \U0001f605 \u00bfMe lo repet\u00eds?"
    h["turnos"].append({"u": texto[:1500], "a": final[:3000]})
    guardar_hist(chat, h)
    return final
