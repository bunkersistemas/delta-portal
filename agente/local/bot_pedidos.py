"""
bot_pedidos.py -- @Con_Interes_bot: el lector sigue su pedido de investigacion por Telegram.

Editor, 12/10/2026: en vez de mail (todavia no hay remitente), el lector toca "Segui
tu pedido por Telegram" en investigacion.html, que abre t.me/Con_Interes_bot?start=<codigo>.
El bot busca el pedido por ese codigo y guarda el chat; desde ahi:
  - pedidos_lectores.py le manda el ENFOQUE (titulo tentativo, secciones, enlace a la
    maqueta) con dos botones, y el aviso de nota publicada;
  - este bot recibe la respuesta: "Si, es esto" aprueba; "No, queria otra cosa" le pide
    que escriba que queria, y eso vuelve a la redaccion como en enfoque.html.

El bot NO hace nada mas: no busca, no responde preguntas, no toca el sitio. Lo que
escribe un lector es DATO: solo se guarda como comentario del enfoque.
Corre en la VM como tarea "Con Interes - Bot Telegram" (long polling, sin webhook).
"""
import json, os, re, subprocess, sys, time, traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pedidos_lectores as pl

ESTADO = os.path.join(pl.LOGS, "bot_telegram_estado.json")   # offset y quien esta escribiendo
LOG = os.path.join(pl.LOGS, "bot_telegram.log")
FORM = "https://coninteres.com/investigacion.html?de=telegram"
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)

T_HOLA = ("Hola. Soy el bot de Con Inter\u00e9s. Ac\u00e1 ped\u00eds una investigaci\u00f3n y la "
          "segu\u00eds de punta a punta: te mostramos el enfoque antes de investigar, lo aprob\u00e1s "
          "con un bot\u00f3n y te avisamos cuando sale la nota.\n\n"
          "Toc\u00e1 \u00ab\u2795 Pedir una investigaci\u00f3n\u00bb para empezar.")
T_VINCULADO = ("Listo, tu pedido qued\u00f3 vinculado:\n\u00ab{titulo}\u00bb\n\n"
               "Ahora lo leemos y armamos el enfoque: qu\u00e9 vamos a contestar y con qu\u00e9 fuentes. "
               "Te lo mandamos por ac\u00e1, suele tardar unas horas.")
T_NO_ENCONTRADO = ("No encontr\u00e9 ese pedido. Us\u00e1 el bot\u00f3n que aparece despu\u00e9s de "
                   "enviarlo en la p\u00e1gina, o ped\u00ed una investigaci\u00f3n ac\u00e1: " + FORM)
T_OTRO = ("Por ahora solo te acompa\u00f1o con tus pedidos de investigaci\u00f3n. "
          "Us\u00e1 los botones de abajo: \u00ab\u2795 Pedir una investigaci\u00f3n\u00bb o \u00ab\U0001f4cb Mis pedidos\u00bb.")
T_APROBADO = ("Listo. Empezamos a investigar con este enfoque. Te avisamos por ac\u00e1 cuando "
              "salga la nota.\n\nVos elegiste qu\u00e9 se investiga; el resultado es el que den los datos.")
T_CONTAME = ("Contanos en un mensaje qu\u00e9 quer\u00edas saber: otro alcance, otro per\u00edodo, "
             "otras provincias, otra comparaci\u00f3n...")
T_REENFOQUE = "Gracias. Rehacemos el enfoque con lo que nos dijiste y te lo mandamos por ac\u00e1."
T_YA_NO = ("Ese enfoque ya no est\u00e1 esperando respuesta (puede que ya est\u00e9 en "
           "investigaci\u00f3n). Te avisamos por ac\u00e1 cuando haya novedades.")
T_NO_ES_TUYO = "Ese pedido no est\u00e1 vinculado a este chat."


def anotar(t):
    l = time.strftime("%Y-%m-%d %H:%M:%S") + "  " + t
    print(l, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(l + "\n")


def leer_estado():
    try:
        return json.load(open(ESTADO, encoding="utf-8"))
    except Exception:
        return {"offset": 0, "esperando": {}, "conv": {}, "revision": {}}


def guardar_estado(e):
    tmp = ESTADO + ".tmp"
    json.dump(e, open(tmp, "w", encoding="utf-8"))
    os.replace(tmp, ESTADO)


# Botones fijos abajo del chat (teclado de respuesta): mandan este texto al tocarlos.
B_MIS = "\U0001f4cb Mis pedidos"
B_PEDIR = "\u2795 Pedir una investigaci\u00f3n"
TECLADO = {"keyboard": [[{"text": B_MIS}, {"text": B_PEDIR}]], "resize_keyboard": True, "is_persistent": True}
COMANDOS = [{"command": "mispedidos", "description": "En qu\u00e9 est\u00e1 cada investigaci\u00f3n que pediste"},
            {"command": "pedir", "description": "Pedir una investigaci\u00f3n nueva"},
            {"command": "start", "description": "Empezar"}]
ESTADOS = {
    "recibido": "\U0001f4e5 Recibido: estamos armando el enfoque",
    "en_investigacion": "\u2699\ufe0f La redacci\u00f3n est\u00e1 trabajando en tu pedido ahora",
    "enfoque_propuesto": "\u270b Te mandamos el enfoque: esperamos tu respuesta",
    "enfoque_aprobado": "\u23f3 Enfoque aprobado: en la fila para investigar (sale una investigaci\u00f3n por d\u00eda)",
    "en_revision": "\U0001f4f0 Lista: te mandamos la vista previa para que la mires antes de publicar",
    "revision_ok": "\U0001f4e4 La aprobaste: se publica en la pr\u00f3xima vuelta de la redacci\u00f3n",
    "revision_error": "\U0001f50d Revisando contra la fuente lo que nos marcaste; despu\u00e9s se publica",
    "publicado": "\u2705 Publicada",
    "descartado": "\u26d4 Cerrado sin nota",
}


def decir(chat, texto, botones=None, teclado=False):
    d = {"chat_id": chat, "text": texto, "disable_web_page_preview": True}
    if botones:
        d["reply_markup"] = {"inline_keyboard": botones}
    elif teclado:
        d["reply_markup"] = TECLADO
    pl.tg("sendMessage", d)


def mis_pedidos(chat):
    f = pl.pedir("GET", "?select=id,titulo,estado,salida,motivo,token,creado&telegram_chat=eq.%d&order=creado.desc&limit=10" % chat)
    if not f:
        decir(chat, "Todav\u00eda no ten\u00e9s pedidos vinculados a este chat.\n\nPara pedir una investigaci\u00f3n: " + FORM
              + "\nDespu\u00e9s de enviarla, toc\u00e1 \u00abSegu\u00ed tu pedido por Telegram\u00bb.", teclado=True)
        return
    l = ["\U0001f4cb Tus pedidos (los \u00faltimos %d):" % len(f), ""]
    for p in f:
        l.append("\u2022 \u00ab%s\u00bb" % p["titulo"].strip())
        l.append("  " + ESTADOS.get(p["estado"], p["estado"]))
        if p["estado"] == "publicado" and p.get("salida"):
            l.append("  " + p["salida"])
        elif p["estado"] == "enfoque_propuesto":
            l.append("  Ver el enfoque: " + pl.enlace(p["id"], p["token"]))
        elif p["estado"] == "descartado" and p.get("motivo"):
            l.append("  Motivo: " + p["motivo"][:220])
        l.append("")
    decir(chat, "\n".join(l).strip(), teclado=True)


TIPOS = [("cuanto-cuesta", "\U0001f4b0 \u00bfCu\u00e1nto cuesta? \u00bfQui\u00e9n paga?"),
         ("verificar-cifra", "\U0001f50e Verificar una cifra que vi"),
         ("comparar", "\u2696\ufe0f Comparar con otro pa\u00eds u otra \u00e9poca"),
         ("otro", "\u2753 Otra")]


def disparar_enfoque():
    """La tarea de enfoque corre al toque (si ya esta corriendo, la vuelta en curso
    lo toma o lo toma la siguiente)."""
    try:
        subprocess.run(["schtasks", "/run", "/tn", "Con Interes - Enfoque"], capture_output=True, timeout=30)
        anotar("tarea de enfoque disparada")
    except Exception as e:
        anotar("AVISO: no se pudo disparar el enfoque: %s" % e)


def disparar_redaccion():
    """La redaccion publica o corrige la vista previa al empezar su vuelta."""
    try:
        subprocess.run(["schtasks", "/run", "/tn", "Con Interes - Redaccion programada"], capture_output=True, timeout=30)
        anotar("redaccion disparada")
    except Exception as e:
        anotar("AVISO: no se pudo disparar la redaccion: %s" % e)


def pedir_nueva(est, chat):
    # editor, 12/10/2026: una investigacion en curso por persona
    abiertos = pl.en_curso(chat)
    if abiertos:
        p = abiertos[0]
        decir(chat, "Ya ten\u00e9s una investigaci\u00f3n en curso:\n\u00ab%s\u00bb\n%s\n\n"
              "Para que cada pedido tenga su tiempo, va una por persona. Cuando salga, ped\u00ed la pr\u00f3xima."
              % (p["titulo"].strip(), ESTADOS.get(p["estado"], p["estado"])), teclado=True)
        return
    est["conv"][str(chat)] = {"paso": "titulo"}
    decir(chat, "\u00bfQu\u00e9 quer\u00e9s saber? Escribilo en una l\u00ednea, como se lo preguntar\u00edas a un amigo.\n\n"
          "Por ejemplo: \u00ab\u00bfCu\u00e1nto le cuesta a un club de barrio mantener una pileta?\u00bb",
          botones=[[{"text": "Cancelar", "callback_data": "cancelar"}]])


def seguir_conversacion(est, chat, texto):
    """Devuelve True si el mensaje era parte de un pedido en armado."""
    c = est["conv"].get(str(chat))
    if not c:
        return False
    if c["paso"] == "titulo":
        if not (5 <= len(texto) <= 140):
            decir(chat, "Escribilo en una l\u00ednea, entre 5 y 140 letras.")
            return True
        c.update(paso="tipo", titulo=texto)
        decir(chat, "\u00bfQu\u00e9 tipo de pregunta es?",
              botones=[[{"text": t, "callback_data": "tipo:" + k}] for k, t in TIPOS])
        return True
    if c["paso"] == "detalle":
        c.update(paso="confirmar", detalle=texto[:1500])
        confirmar(chat, c)
        return True
    decir(chat, "Us\u00e1 los botones del mensaje anterior para seguir, o toc\u00e1 Cancelar.")
    return True


def confirmar(chat, c):
    tipo = dict(TIPOS).get(c.get("tipo"), "")
    decir(chat, "As\u00ed queda tu pedido:\n\n\u00ab%s\u00bb\n%s%s\n\n\u00bfLo enviamos?"
          % (c["titulo"], tipo, ("\n\n" + c["detalle"]) if c.get("detalle") else ""),
          botones=[[{"text": "\U0001f4e8 Enviar", "callback_data": "enviar"},
                    {"text": "Cancelar", "callback_data": "cancelar"}]])


def pedido_de(pid, chat):
    """El pedido, solo si esta vinculado a ESTE chat."""
    f = pl.pedir("GET", "?select=id,titulo,estado,token,telegram_chat,enfoque&id=eq.%d" % int(pid))
    if not f or f[0].get("telegram_chat") != chat:
        return None
    return f[0]


def al_start(chat, codigo):
    if not codigo:
        decir(chat, T_HOLA, teclado=True)
        return
    if not UUID.match(codigo):
        decir(chat, T_NO_ENCONTRADO)
        return
    f = pl.pedir("GET", "?select=id,titulo,estado,token,enfoque,telegram_chat&codigo_tg=eq." + codigo)
    if not f:
        decir(chat, T_NO_ENCONTRADO)
        return
    p = f[0]
    if p.get("telegram_chat") and p["telegram_chat"] != chat:
        # el codigo ya lo uso otro chat: no se le pasa el pedido a nadie mas
        decir(chat, T_NO_ENCONTRADO)
        anotar("pedido %s: codigo usado desde otro chat, no se vincula" % p["id"])
        return
    pl.pedir("PATCH", "?id=eq.%d" % p["id"], {"telegram_chat": chat})
    anotar("pedido %s vinculado a un chat" % p["id"])
    decir(chat, T_VINCULADO.format(titulo=p["titulo"]), teclado=True)
    if p["estado"] == "enfoque_propuesto" and p.get("enfoque"):
        decir(chat, pl.texto_enfoque(p["id"], json.loads(p["enfoque"]), p["token"]),
              pl.botones_enfoque(p["id"]))


def al_boton(est, q):
    chat = q["message"]["chat"]["id"]
    accion, _, pid = (q.get("data") or "").partition(":")
    pl.tg("answerCallbackQuery", {"callback_query_id": q["id"]})
    if accion in ("tipo", "detalle", "enviar", "cancelar"):
        al_boton_conversacion(est, q, chat, accion, pid)
        return
    if accion in ("pub", "err") and pid.isdigit():
        sacar_botones(q)
        if accion == "pub":
            if pl.marcar_revision(pid, chat, True):
                anotar("pedido %s: el lector aprobo la vista previa" % pid)
                decir(chat, "\U0001f44d Listo. La publicamos en un rato y te mandamos el link.", teclado=True)
                disparar_redaccion()
            else:
                decir(chat, "Esa vista previa ya no est\u00e1 esperando respuesta.", teclado=True)
        else:
            est["revision"][str(chat)] = int(pid)
            anotar("pedido %s: el lector va a contar un error de la vista previa" % pid)
            decir(chat, "Contanos qu\u00e9 viste mal o qu\u00e9 falt\u00f3. Si ten\u00e9s la fuente (un link, una "
                  "resoluci\u00f3n, un documento), pegala: nos ayuda a verificarlo.")
        return
    if accion not in ("ok", "no") or not pid.isdigit():
        return
    p = pedido_de(pid, chat)
    if not p:
        decir(chat, T_NO_ES_TUYO)
        return
    # los botones se sacan del mensaje: no se responde dos veces
    try:
        pl.tg("editMessageReplyMarkup", {"chat_id": chat, "message_id": q["message"]["message_id"],
                                         "reply_markup": {"inline_keyboard": []}})
    except Exception:
        pass
    if p["estado"] != "enfoque_propuesto":
        decir(chat, T_YA_NO)
        return
    if accion == "ok":
        r = pl.rpc("enfoque_responder", {"p_id": int(pid), "p_token": p["token"], "p_ok": True, "p_texto": None})
        anotar("pedido %s: enfoque aprobado por Telegram (%s)" % (pid, r))
        decir(chat, T_APROBADO if r == "aprobado" else T_YA_NO)
    else:
        est["esperando"][str(chat)] = int(pid)
        anotar("pedido %s: el lector va a escribir que queria" % pid)
        decir(chat, T_CONTAME)


def sacar_botones(q):
    try:
        pl.tg("editMessageReplyMarkup", {"chat_id": q["message"]["chat"]["id"], "message_id": q["message"]["message_id"],
                                         "reply_markup": {"inline_keyboard": []}})
    except Exception:
        pass


def al_boton_conversacion(est, q, chat, accion, valor):
    c = est["conv"].get(str(chat))
    sacar_botones(q)
    if accion == "cancelar":
        est["conv"].pop(str(chat), None)
        decir(chat, "Listo, no enviamos nada.", teclado=True)
        return
    if not c:
        decir(chat, "Ese pedido ya no est\u00e1 en armado. Toc\u00e1 \u00ab\u2795 Pedir una investigaci\u00f3n\u00bb para empezar otro.", teclado=True)
        return
    if accion == "tipo" and c["paso"] == "tipo" and valor in dict(TIPOS):
        c.update(paso="detalle", tipo=valor)
        decir(chat, "Contanos un poco m\u00e1s, si quer\u00e9s: por qu\u00e9 te interesa, d\u00f3nde lo viste, "
              "qu\u00e9 te gustar\u00eda comparar.",
              botones=[[{"text": "Saltear", "callback_data": "detalle:no"}]])
        return
    if accion == "detalle" and c["paso"] == "detalle":
        c.update(paso="confirmar", detalle="")
        confirmar(chat, c)
        return
    if accion == "enviar" and c["paso"] == "confirmar":
        est["conv"].pop(str(chat), None)
        if pl.en_curso(chat):
            decir(chat, "Ya ten\u00e9s una investigaci\u00f3n en curso: cuando salga, ped\u00ed la pr\u00f3xima.", teclado=True)
            return
        pid = pl.crear_desde_chat(chat, c["titulo"], c["tipo"], c.get("detalle", ""))
        anotar("pedido %s creado desde el chat" % pid)
        decir(chat, "\U0001f4e8 Recibimos tu pedido.\n\nAhora la redacci\u00f3n lo lee y arma el enfoque: qu\u00e9 vamos "
              "a contestar, con qu\u00e9 fuentes y c\u00f3mo se va a ver la nota. Te lo mandamos por ac\u00e1 en un rato "
              "para que lo apruebes.", teclado=True)
        disparar_enfoque()
        return
    decir(chat, "Ese bot\u00f3n ya no corresponde. Segu\u00ed desde el \u00faltimo mensaje.")


def al_mensaje(est, m):
    chat = m["chat"]["id"]
    texto = (m.get("text") or "").strip()
    # se anota QUE llego, nunca el contenido (12/10/2026: un mensaje sin rastro)
    tipo_msg = ("start con codigo" if texto.startswith("/start ") else "start sin codigo"
                if texto.startswith("/start") else "respuesta de enfoque"
                if str(chat) in est["esperando"] else "texto suelto")
    if texto in ("/mispedidos", B_MIS) or texto.startswith("/mispedidos@"):
        tipo_msg = "mis pedidos"
    elif texto in ("/pedir", B_PEDIR) or texto.startswith("/pedir@"):
        tipo_msg = "pedir"
    elif str(chat) in est["conv"]:
        tipo_msg = "armando pedido"
    elif str(chat) in est["revision"] and not texto.startswith("/"):
        tipo_msg = "error de vista previa"
    anotar("mensaje recibido: " + tipo_msg)
    if tipo_msg == "mis pedidos":
        est["esperando"].pop(str(chat), None)
        est["conv"].pop(str(chat), None)
        mis_pedidos(chat)
        return
    if tipo_msg == "pedir":
        est["esperando"].pop(str(chat), None)
        pedir_nueva(est, chat)
        return
    if tipo_msg == "armando pedido" and seguir_conversacion(est, chat, texto):
        return
    if tipo_msg == "error de vista previa":
        pid = est["revision"].pop(str(chat))
        if pl.marcar_revision(pid, chat, False, texto):
            anotar("pedido %s: el lector senalo un error en la vista previa" % pid)
            decir(chat, "Gracias. Lo revisamos contra la fuente: si tiene raz\u00f3n, se corrige antes de "
                  "publicar. Te contamos qu\u00e9 encontramos.", teclado=True)
            disparar_redaccion()
        else:
            decir(chat, "Esa vista previa ya no est\u00e1 esperando respuesta.", teclado=True)
        return
    if texto.startswith("/start"):
        est["esperando"].pop(str(chat), None)
        al_start(chat, texto[6:].strip())
        return
    pid = est["esperando"].get(str(chat))
    if pid and texto:
        p = pedido_de(pid, chat)
        est["esperando"].pop(str(chat), None)
        if not p or p["estado"] != "enfoque_propuesto":
            decir(chat, T_YA_NO)
            return
        r = pl.rpc("enfoque_responder", {"p_id": int(pid), "p_token": p["token"], "p_ok": False,
                                         "p_texto": texto[:1500]})
        anotar("pedido %s: pidio otro enfoque por Telegram (%s)" % (pid, r))
        decir(chat, T_REENFOQUE if r == "reenfoque" else T_YA_NO)
        if r == "reenfoque":
            disparar_enfoque()
        return
    decir(chat, T_OTRO, teclado=True)


def main():
    anotar("bot iniciado")
    try:
        pl.tg("setMyCommands", {"commands": COMANDOS})
    except Exception:
        anotar("AVISO: no se pudo registrar el menu de comandos")
    est = leer_estado()
    est.setdefault("conv", {})
    est.setdefault("revision", {})
    while True:
        try:
            r = pl.tg("getUpdates", {"offset": est["offset"], "timeout": 50,
                                     "allowed_updates": ["message", "callback_query"]})
            for u in r.get("result", []):
                est["offset"] = u["update_id"] + 1
                try:
                    if "callback_query" in u:
                        al_boton(est, u["callback_query"])
                    elif "message" in u and u["message"].get("chat", {}).get("type") == "private":
                        al_mensaje(est, u["message"])
                except Exception:
                    anotar("ERROR atendiendo un mensaje: " + traceback.format_exc().replace("\n", " | ")[-600:])
                guardar_estado(est)
        except Exception:
            anotar("ERROR en el ciclo: " + traceback.format_exc().replace("\n", " | ")[-400:])
            time.sleep(15)


if __name__ == "__main__":
    main()
