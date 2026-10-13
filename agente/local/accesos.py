"""
accesos.py -- el bot de Telegram es PRIVADO (editor, 13/10/2026).

No se publica en ningun lado. Quien le escriba sin acceso recibe "canal privado" y al
editor le llega la solicitud (id y nombre de Telegram) con Aceptar / Rechazar. Al
aceptar, el editor escribe el NOMBRE real de esa persona: recien ahi tiene acceso, y
cada pedido queda con ese nombre (columna solicitante, que solo lee la VM).

La lista vive en la VM, fuera del repo: coninteres-privado/autorizados.json
  {"autorizados": {"<chat>": {"nombre": ..., "desde": ...}},
   "pendientes":  {"<chat>": {"telegram": ..., "ts": ...}},
   "rechazados":  ["<chat>", ...]}

  python accesos.py ver                       lista (para el editor, desde la VM)
  python accesos.py piloto                    habilita a los chats que ya tienen pedidos
                                              (amigos del piloto) con su nombre de Telegram
                                              y le pide al editor que les ponga el nombre real
"""
import datetime as dt, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pedidos_lectores as pl

ARCHIVO = os.path.join(os.path.expanduser("~"), "coninteres-privado", "autorizados.json")
EDITOR = os.path.join(os.path.expanduser("~"), "coninteres-privado", "editor_telegram.txt")

T_PRIVADO = ("\U0001f512 Este es un canal privado de Con Inter\u00e9s.\n\n"
             "Le avis\u00e9 al editor de tu solicitud de acceso. Si te habilita, te escribo por ac\u00e1.")
T_YA_PEDIDO = "\U0001f512 Tu solicitud de acceso ya est\u00e1 con el editor. Si te habilita, te escribo por ac\u00e1."
T_PRIVADO_CORTO = "\U0001f512 Este es un canal privado de Con Inter\u00e9s."
T_BIENVENIDA = ("\u2705 \u00a1Listo, {nombre}! Ya ten\u00e9s acceso.\n\n"
                "Escribime lo que quieras saber de la econom\u00eda: si ya lo investigamos, te paso la nota; "
                "si no, lo investigamos y te aviso cuando est\u00e9.")


def editor():
    return int(open(EDITOR, encoding="ascii").read().strip())


def leer():
    try:
        d = json.load(open(ARCHIVO, encoding="utf-8"))
    except FileNotFoundError:
        d = {}
    d.setdefault("autorizados", {})
    d.setdefault("pendientes", {})
    d.setdefault("rechazados", [])
    return d


def guardar(d):
    tmp = ARCHIVO + ".tmp"
    json.dump(d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, ARCHIVO)


def ahora():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def autorizado(chat):
    return chat == editor() or str(chat) in leer()["autorizados"]


def nombre_de(chat):
    if chat == editor():
        return "el editor"
    a = leer()["autorizados"].get(str(chat))
    return a["nombre"] if a else None


def telegram_de(usuario):
    """El nombre que la persona puso en Telegram: solo se le muestra al editor."""
    u = usuario or {}
    t = " ".join(x for x in (u.get("first_name"), u.get("last_name")) if x)
    if u.get("username"):
        t += " (@%s)" % u["username"]
    return t or "sin nombre en Telegram"


def solicitar(chat, usuario, decir):
    """Alguien sin acceso escribio. Avisa al editor una sola vez."""
    d = leer()
    k = str(chat)
    if k in d["rechazados"]:
        decir(chat, T_PRIVADO_CORTO)
        return "rechazado"
    if k in d["pendientes"]:
        decir(chat, T_YA_PEDIDO)
        return "pendiente"
    d["pendientes"][k] = {"telegram": telegram_de(usuario), "ts": ahora()}
    guardar(d)
    decir(chat, T_PRIVADO)
    decir(editor(), "\U0001f511 Solicitud de acceso al bot:\n\n%s\nID %s\n\n\u00bfLe das acceso? "
                    "Si acept\u00e1s, te pido su nombre." % (telegram_de(usuario), k),
          [[{"text": "\u2705 Aceptar", "callback_data": "acc:%s" % k},
            {"text": "\u274c Rechazar", "callback_data": "rech:%s" % k}]])
    return "nueva"


def aceptar(k):
    """Primer paso: queda esperando el nombre (todavia no tiene acceso)."""
    d = leer()
    p = d["pendientes"].get(k)
    return p["telegram"] if p else None


def rechazar(k):
    d = leer()
    d["pendientes"].pop(k, None)
    if k not in d["rechazados"]:
        d["rechazados"].append(k)
    guardar(d)


def habilitar(k, nombre):
    d = leer()
    previo = d["autorizados"].get(k)
    d["autorizados"][k] = {"nombre": nombre.strip()[:80], "desde": previo["desde"] if previo else ahora()}
    d["pendientes"].pop(k, None)
    if k in d["rechazados"]:
        d["rechazados"].remove(k)
    guardar(d)


def quitar(k):
    d = leer()
    a = d["autorizados"].pop(k, None)
    if a and k not in d["rechazados"]:
        d["rechazados"].append(k)
    guardar(d)
    return a["nombre"] if a else None


def botones_persona(k):
    return [[{"text": "\u270f\ufe0f Poner nombre", "callback_data": "nom:%s" % k},
             {"text": "\u26d4 Quitar acceso", "callback_data": "quit:%s" % k}]]


def lista_texto():
    d = leer()
    if not d["autorizados"]:
        return "Nadie tiene acceso al bot salvo vos."
    l = ["\U0001f465 Tienen acceso al bot:", ""]
    for k, a in d["autorizados"].items():
        l.append("\u2022 %s (ID %s, desde %s)" % (a["nombre"], k, a["desde"][:10]))
    if d["pendientes"]:
        l += ["", "Solicitudes sin responder: %d" % len(d["pendientes"])]
    return "\n".join(l)


def piloto():
    """Los amigos del piloto ya tienen pedidos: se los habilita para no cortarles nada a
    mitad de camino, con su nombre de Telegram, y se le pide al editor el nombre real."""
    d = leer()
    chats = {f["telegram_chat"] for f in pl.pedir("GET", "?select=telegram_chat&telegram_chat=not.is.null")}
    ed = editor()
    nuevos = 0
    for c in sorted(chats):
        if c == ed or str(c) in d["autorizados"]:
            continue
        try:
            u = pl.tg("getChat", {"chat_id": c}).get("result", {})
        except Exception:
            u = {}
        tg_nombre = telegram_de(u)
        d["autorizados"][str(c)] = {"nombre": "(piloto) " + tg_nombre, "desde": ahora()}
        guardar(d)
        tit = [f["titulo"].strip() for f in pl.pedir("GET", "?select=titulo&telegram_chat=eq.%d&order=creado" % c)]
        pl.tg("sendMessage", {"chat_id": ed, "disable_web_page_preview": True,
                              "text": ("\U0001f465 Ya usaba el bot en el piloto, as\u00ed que lo dej\u00e9 con acceso:\n\n%s\nID %s\n"
                                       "Pedidos: %s\n\nPonele el nombre real, o quitale el acceso." % (tg_nombre, c, " / ".join(tit)[:600])),
                              "reply_markup": {"inline_keyboard": botones_persona(str(c))}})
        nuevos += 1
    print("OK|piloto: %d chats habilitados" % nuevos)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "ver":
        print(lista_texto())
    elif cmd == "piloto":
        piloto()
    else:
        raise SystemExit(__doc__)
