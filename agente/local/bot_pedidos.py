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
import json, os, re, sys, time, traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pedidos_lectores as pl

ESTADO = os.path.join(pl.LOGS, "bot_telegram_estado.json")   # offset y quien esta escribiendo
LOG = os.path.join(pl.LOGS, "bot_telegram.log")
FORM = "https://coninteres.com/investigacion.html?de=telegram"
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)

T_HOLA = ("Hola. Soy el bot de Con Inter\u00e9s. Por ac\u00e1 segu\u00eds las investigaciones que "
          "pediste: te mostramos el enfoque antes de investigar y te avisamos cuando sale la nota.\n\n"
          "Para pedir una investigaci\u00f3n: " + FORM)
T_VINCULADO = ("Listo, tu pedido qued\u00f3 vinculado:\n\u00ab{titulo}\u00bb\n\n"
               "Ahora lo leemos y armamos el enfoque: qu\u00e9 vamos a contestar y con qu\u00e9 fuentes. "
               "Te lo mandamos por ac\u00e1, suele tardar unas horas.")
T_NO_ENCONTRADO = ("No encontr\u00e9 ese pedido. Us\u00e1 el bot\u00f3n que aparece despu\u00e9s de "
                   "enviarlo en la p\u00e1gina, o ped\u00ed una investigaci\u00f3n ac\u00e1: " + FORM)
T_OTRO = ("Por ahora solo te acompa\u00f1o con tus pedidos de investigaci\u00f3n. "
          "Para pedir una: " + FORM)
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
        return {"offset": 0, "esperando": {}}


def guardar_estado(e):
    tmp = ESTADO + ".tmp"
    json.dump(e, open(tmp, "w", encoding="utf-8"))
    os.replace(tmp, ESTADO)


def decir(chat, texto, botones=None):
    d = {"chat_id": chat, "text": texto}
    if botones:
        d["reply_markup"] = {"inline_keyboard": botones}
    pl.tg("sendMessage", d)


def pedido_de(pid, chat):
    """El pedido, solo si esta vinculado a ESTE chat."""
    f = pl.pedir("GET", "?select=id,titulo,estado,token,telegram_chat,enfoque&id=eq.%d" % int(pid))
    if not f or f[0].get("telegram_chat") != chat:
        return None
    return f[0]


def al_start(chat, codigo):
    if not codigo:
        decir(chat, T_HOLA)
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
    decir(chat, T_VINCULADO.format(titulo=p["titulo"]))
    if p["estado"] == "enfoque_propuesto" and p.get("enfoque"):
        decir(chat, pl.texto_enfoque(p["id"], json.loads(p["enfoque"]), p["token"]),
              pl.botones_enfoque(p["id"]))


def al_boton(est, q):
    chat = q["message"]["chat"]["id"]
    accion, _, pid = (q.get("data") or "").partition(":")
    pl.tg("answerCallbackQuery", {"callback_query_id": q["id"]})
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


def al_mensaje(est, m):
    chat = m["chat"]["id"]
    texto = (m.get("text") or "").strip()
    # se anota QUE llego, nunca el contenido (12/10/2026: un mensaje sin rastro)
    tipo_msg = ("start con codigo" if texto.startswith("/start ") else "start sin codigo"
                if texto.startswith("/start") else "respuesta de enfoque"
                if str(chat) in est["esperando"] else "texto suelto")
    anotar("mensaje recibido: " + tipo_msg)
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
        return
    decir(chat, T_OTRO)


def main():
    anotar("bot iniciado")
    est = leer_estado()
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
