"""
bot_pedidos.py -- @Con_Interes_bot: el lector pide y sigue su investigacion por Telegram.

Editor, 12/10/2026. Todo desde el chat, sin modelo de lenguaje (decision del editor:
nada de IA conversando con terceros por ahora; ver memoria del 12/10):
  - una pregunta suelta se busca por palabras en las notas publicadas y se ofrece
    pedirla como investigacion con un boton;
  - /pedir arma el pedido (pregunta, tipo, detalle) y confirma; UNA investigacion en
    curso por persona;
  - pedidos_lectores.py manda el ENFOQUE (maqueta) con botones y, con la nota lista,
    la VISTA PREVIA (Publicar / Hay un error, sin veto); este bot recibe las respuestas;
  - /mispedidos cuenta en que esta cada uno.
Lo que escribe un lector es DATO: se guarda como pedido o comentario, nunca se ejecuta.
Corre en la VM como tarea "Con Interes - Bot Telegram" (long polling, sin webhook).
"""
import json, os, re, subprocess, sys, time, traceback, unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pedidos_lectores as pl

ESTADO = os.path.join(pl.LOGS, "bot_telegram_estado.json")   # offset y quien esta escribiendo
LOG = os.path.join(pl.LOGS, "bot_telegram.log")
SITIO = "https://coninteres.com/"
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)

T_HOLA = ("\U0001f44b \u00a1Hola! Ac\u00e1 miramos los n\u00fameros detr\u00e1s de las noticias, con datos verificados y sin pol\u00edtica.\n\n"
          "Escribime lo que te genere curiosidad de la econom\u00eda: si ya lo investigamos, te paso la nota; "
          "si no, lo investigamos para vos y te aviso cuando est\u00e9.")
T_VINCULADO = ("Listo, ya tengo tu pedido \U0001f64c\n\u00ab{titulo}\u00bb\n\n"
               "Ahora lo leemos y armamos el enfoque: qu\u00e9 vamos a contestar, con qu\u00e9 fuentes y c\u00f3mo se va "
               "a ver la nota. Te lo mando por ac\u00e1.")
T_VINCULADO_MODERACION = ("Listo, ya tengo tu pedido \U0001f64c\n\u00ab{titulo}\u00bb\n\n"
                          "Primero lo revisamos. Si lo tomamos, armamos el enfoque y te lo mando por ac\u00e1.")
T_NO_ENCONTRADO = ("Mmm, no encuentro ese pedido \U0001f914 Prob\u00e1 con el bot\u00f3n que aparece despu\u00e9s de enviarlo en la "
                   "p\u00e1gina, o contame ac\u00e1 qu\u00e9 quer\u00e9s saber.")
T_APROBADO = ("\u00a1Vamos! \U0001f50e Arrancamos a investigar con este enfoque. Cuando la nota est\u00e9 lista te la muestro "
              "antes de publicarla.\n\nVos elegiste qu\u00e9 se investiga; el resultado es el que den los datos.")
T_CONTAME = "Dale. Contame en un mensaje qu\u00e9 quer\u00edas: otro alcance, otro per\u00edodo, otras provincias, otra comparaci\u00f3n..."
T_REENFOQUE = "Anotado \u270d\ufe0f Rehacemos el enfoque con eso y te lo mando por ac\u00e1 en un rato."
T_YA_NO = ("Ese enfoque ya no est\u00e1 esperando respuesta (puede que ya est\u00e9 en investigaci\u00f3n). "
           "Te aviso por ac\u00e1 cuando haya novedades.")
T_NO_ES_TUYO = "Ese pedido no es de este chat \U0001f937"
T_GRACIAS = "\u00a1De nada! Cuando te pique la curiosidad, escribime \U0001f609"

# Botones fijos abajo del chat (teclado de respuesta): mandan este texto al tocarlos.
B_MIS = "\U0001f4cb Mis pedidos"
B_PEDIR = "\u2795 Pedir una investigaci\u00f3n"
TECLADO = {"keyboard": [[{"text": B_MIS}, {"text": B_PEDIR}]], "resize_keyboard": True, "is_persistent": True}
COMANDOS = [{"command": "mispedidos", "description": "En qu\u00e9 est\u00e1 cada investigaci\u00f3n que pediste"},
            {"command": "pedir", "description": "Pedir una investigaci\u00f3n nueva"},
            {"command": "start", "description": "Empezar"}]
ESTADOS = {
    "moderacion": "\U0001f440 Recibido: lo estamos revisando antes de investigar",
    "recibido": "\U0001f4e5 Recibido: estamos armando el enfoque",
    "en_investigacion": "\u2699\ufe0f La redacci\u00f3n est\u00e1 trabajando en esto ahora",
    "enfoque_propuesto": "\u270b Te mand\u00e9 el enfoque: espero tu respuesta",
    "enfoque_aprobado": "\u23f3 Enfoque aprobado: en la fila para investigar",
    "en_revision": "\U0001f4f0 Lista: te mand\u00e9 la vista previa para que la mires antes de publicar",
    "revision_ok": "\U0001f4e4 La aprobaste: sale en la pr\u00f3xima vuelta de la redacci\u00f3n",
    "revision_feedback": "\u270d\ufe0f Rehaciendo la nota con tus sugerencias: te la muestro de nuevo",
    "revision_error": "\U0001f50d Revisando contra la fuente lo que marcaste; despu\u00e9s sale",
    "publicado": "\u2705 Publicada",
    "descartado": "\u26d4 Cerrado sin nota",
}
TIPOS = [("cuanto-cuesta", "\U0001f4b0 \u00bfCu\u00e1nto cuesta? \u00bfQui\u00e9n paga?"),
         ("verificar-cifra", "\U0001f50e Verificar una cifra que vi"),
         ("comparar", "\u2696\ufe0f Comparar con otro pa\u00eds u otra \u00e9poca"),
         ("otro", "\u2753 Otra")]
SALUDOS = {"hola", "buenas", "buen dia", "buenos dias", "buenas tardes", "buenas noches", "hey", "holis", "que tal"}
AGRADECE = {"gracias", "muchas gracias", "genial", "joya", "dale", "ok", "listo", "barbaro", "perfecto", "buenisimo"}
VACIAS = set("que los las del como cuanto cuanta cuantos cuantas para por con una uno unos unas sus son esta este "
             "esto eso esa ese hay mas menos tiene tienen fue era ser entre sobre desde hasta cual cuales donde "
             "cuando quien porque pero sin muy hace hacen les nos ella ellos aca alla todo toda todos todas "
             "saber quiero queria quisiera podes puede pueden sabes".split())


def anotar(t):
    l = time.strftime("%Y-%m-%d %H:%M:%S") + "  " + t
    print(l, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(l + "\n")


def leer_estado():
    try:
        return json.load(open(ESTADO, encoding="utf-8"))
    except Exception:
        return {"offset": 0, "esperando": {}, "conv": {}, "revision": {}, "sugerido": {}, "anotado": {}}


def guardar_estado(e):
    tmp = ESTADO + ".tmp"
    json.dump(e, open(tmp, "w", encoding="utf-8"))
    os.replace(tmp, ESTADO)


def decir(chat, texto, botones=None, teclado=False):
    d = {"chat_id": chat, "text": texto, "disable_web_page_preview": True}
    if botones:
        d["reply_markup"] = {"inline_keyboard": botones}
    elif teclado:
        d["reply_markup"] = TECLADO
    pl.tg("sendMessage", d)


def plano(t):
    t = unicodedata.normalize("NFKD", (t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def buscar_notas(consulta, n=3):
    """Notas publicadas que coinciden con la consulta, sin modelo de lenguaje.
    Cada palabra pesa segun lo rara que es en el archivo (una palabra que aparece en
    pocas notas, como "contadores", pesa mucho mas que "cobran" o "menos"). Se descartan
    las notas que quedan muy por debajo de la mejor."""
    import math
    raiz = lambda w: w[:6]   # "pension"/"pensiones", "jubilado"/"jubilada": misma raiz
    palabras = list(dict.fromkeys(raiz(p) for p in re.findall(r"[a-z0-9]+", plano(consulta))
                                  if len(p) > 2 and p not in VACIAS))
    if not palabras:
        return []
    docs = []
    for a in pl.articulos():
        texto = plano(" ".join(str(a.get(k, "")) for k in ("titulo", "titulo_busqueda", "bajada", "numero_label")))
        docs.append(({raiz(t) for t in re.findall(r"[a-z0-9]+", texto)}, a))   # palabras enteras, no pedazos
    total = len(docs) or 1
    peso = {}
    for w in palabras:
        df = sum(1 for t, _ in docs if w in t)
        peso[w] = math.log((total + 1) / (df + 1)) if df else 0.0
    docs_de = {id(a): t for t, a in docs}
    hallados = []
    for t, a in docs:
        puntos = sum(peso[w] for w in palabras if w in t)
        if puntos > 0:
            hallados.append((puntos, a.get("fecha", ""), a))
    if not hallados:
        return []
    hallados.sort(key=lambda x: (x[0], x[1]), reverse=True)
    mejor = hallados[0][0]
    # la mejor tiene que coincidir en algo poco comun, y las demas acercarse a ella
    if mejor < math.log(total / 25.0):
        return []
    # todas tienen que traer la palabra mas distintiva de la pregunta (la que mas pesa)
    clave = max((w for w in palabras if peso[w] > 0), key=lambda w: peso[w])
    return [a for p, _, a in hallados if p >= 0.7 * mejor and (clave in docs_de[id(a)] or p >= 0.9 * mejor)][:n]


def mis_pedidos(chat, est=None):
    f = pl.pedir("GET", "?select=id,titulo,estado,salida,motivo,token,creado&telegram_chat=eq.%d&order=creado.desc&limit=10" % chat)
    if not f:
        decir(chat, "Todav\u00eda no pediste ninguna investigaci\u00f3n por ac\u00e1.\n\nEscribime lo que quer\u00e9s saber, "
              "o toc\u00e1 \u00ab\u2795 Pedir una investigaci\u00f3n\u00bb.", teclado=True)
        return
    l = ["\U0001f4cb Tus pedidos:", ""]
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


def disparar_enfoque():
    """La tarea de enfoque corre al toque (si ya esta corriendo, la vuelta en curso
    lo toma o lo toma la siguiente)."""
    try:
        subprocess.run(["schtasks", "/run", "/tn", "Con Interes - Enfoque"], capture_output=True, timeout=30)
        anotar("tarea de enfoque disparada")
    except Exception as e:
        anotar("AVISO: no se pudo disparar el enfoque: %s" % e)


def disparar_redaccion():
    """La redaccion investiga, o publica/corrige la vista previa, al empezar su vuelta."""
    try:
        subprocess.run(["schtasks", "/run", "/tn", "Con Interes - Redaccion programada"], capture_output=True, timeout=30)
        anotar("redaccion disparada")
    except Exception as e:
        anotar("AVISO: no se pudo disparar la redaccion: %s" % e)


def ya_tiene_una(chat):
    """editor, 12/10/2026: una investigacion en curso por persona. Avisa y devuelve True."""
    abiertos = pl.en_curso(chat)
    if not abiertos:
        return False
    p = abiertos[0]
    decir(chat, "Ya ten\u00e9s una investigaci\u00f3n en marcha:\n\u00ab%s\u00bb\n%s\n\nVa una por persona, as\u00ed cada una tiene "
          "su tiempo. Apenas salga, pedime la pr\u00f3xima \U0001f609" % (p["titulo"].strip(), ESTADOS.get(p["estado"], p["estado"])),
          teclado=True)
    return True


def pedir_nueva(est, chat, pregunta=""):
    if ofrecer_anotado(est, chat):
        return
    if ya_tiene_una(chat):
        return
    pregunta = " ".join((pregunta or "").split())
    if 5 <= len(pregunta) <= 140:
        est["conv"][str(chat)] = {"paso": "tipo", "titulo": pregunta}
        decir(chat, "Anoto tu pregunta:\n\u00ab%s\u00bb\n\n\u00bfQu\u00e9 tipo de pregunta es?" % pregunta,
              botones=[[{"text": t, "callback_data": "tipo:" + k}] for k, t in TIPOS]
              + [[{"text": "Cancelar", "callback_data": "cancelar"}]])
        return
    est["conv"][str(chat)] = {"paso": "titulo"}
    if pregunta:
        decir(chat, "Es un poco larga para el t\u00edtulo \U0001f605 \u00bfMe la resum\u00eds en una l\u00ednea? (hasta 140 letras)\n\n"
              "Lo dem\u00e1s me lo cont\u00e1s en el paso siguiente.",
              botones=[[{"text": "Cancelar", "callback_data": "cancelar"}]])
        return
    decir(chat, "\u00bfQu\u00e9 quer\u00e9s saber? Escribilo en una l\u00ednea, como se lo preguntar\u00edas a un amigo.\n\n"
          "Por ejemplo: \u00ab\u00bfCu\u00e1nto le cuesta a un club de barrio mantener una pileta?\u00bb",
          botones=[[{"text": "Cancelar", "callback_data": "cancelar"}]])


def seguir_conversacion(est, chat, texto):
    """Devuelve True si el mensaje era parte de un pedido en armado."""
    c = est["conv"].get(str(chat))
    if not c:
        return False
    if c.get("modo") == "indaga":
        seguir_indagacion(est, chat, c, texto)
        return True
    if c["paso"] == "titulo":
        if len(texto) < 5:
            decir(chat, "Contame un poco m\u00e1s \U0001f64f")
            return True
        empezar_indagacion(est, chat, texto, buscar_notas(texto))
        return True
    if False:
        decir(chat, "\u00bfQu\u00e9 tipo de pregunta es?",
              botones=[[{"text": t, "callback_data": "tipo:" + k}] for k, t in TIPOS])
        return True
    if c["paso"] == "detalle":
        c.update(paso="confirmar", detalle=texto[:1500])
        confirmar(chat, c)
        return True
    decir(chat, "Seguimos con los botones del mensaje de arriba, o toc\u00e1 Cancelar.")
    return True


def confirmar(chat, c):
    tipo = dict(TIPOS).get(c.get("tipo"), "")
    decir(chat, "As\u00ed queda:\n\n\u00ab%s\u00bb\n%s%s\n\n\u00bfLo mandamos?"
          % (c["titulo"], tipo, ("\n\n" + c["detalle"]) if c.get("detalle") else ""),
          botones=[[{"text": "\U0001f4e8 Mandar", "callback_data": "enviar"},
                    {"text": "Cancelar", "callback_data": "cancelar"}]])


# ---- charla guiada: indagar hasta tener la pregunta bien armada (editor, 12/10/2026) ----
DONDE = [("ar", "\U0001f1e6\U0001f1f7 Argentina"), ("mundo", "\U0001f30e El mundo"),
         ("prov", "\U0001f4cd Una provincia o ciudad"), ("pais", "\U0001f5fa\ufe0f Otro pa\u00eds"),
         ("igual", "\U0001f937 Da igual")]
CUANDO = [("hoy", "Hoy"), ("1", "El \u00faltimo a\u00f1o"), ("5", "Los \u00faltimos 5 a\u00f1os"),
          ("10", "Los \u00faltimos 10 a\u00f1os"), ("20", "Los \u00faltimos 20 a\u00f1os"), ("igual", "Da igual")]
PROVINCIAS = ("buenos aires", "caba", "ciudad de buenos aires", "cordoba", "santa fe", "rosario", "mendoza",
              "tucuman", "salta", "jujuy", "chaco", "corrientes", "misiones", "entre rios", "formosa",
              "santiago del estero", "catamarca", "la rioja", "san juan", "san luis", "la pampa", "neuquen",
              "rio negro", "chubut", "santa cruz", "tierra del fuego", "provincia", "municipio", "ciudad")


def pregunta_por_su_pedido(llano):
    return bool(re.search(r"\b(mi|mis) (pedido|pedidos|investigacion|investigaciones|consulta)\b", llano)) or llano in (
        "novedades", "hay novedades", "ya salio", "ya esta", "como viene", "como va", "falta mucho")


def detectar(c, texto):
    """Completa donde/cuando si la persona ya lo dijo, para no volver a preguntarlo."""
    t = plano(texto)
    if "donde" not in c:
        if re.search(r"\b(mundo|mundial|global|internacional|planeta)\b", t):
            c["donde"] = "El mundo"
        elif any(re.search(r"\b%s\b" % p, t) for p in PROVINCIAS):
            c["donde"] = "Una provincia o ciudad"
        elif re.search(r"\b(argentin\w*|nacional|el pais)\b", t):
            c["donde"] = "Argentina"
    if "cuando" not in c:
        m = re.search(r"\b(\d{1,2}) (anos|decadas)\b", t)
        d = re.search(r"\bdesde (el )?(19|20)(\d\d)\b", t)
        if m:
            c["cuando"] = "Los \u00faltimos %s %s" % (m.group(1), "a\u00f1os" if m.group(2) == "anos" else "d\u00e9cadas")
        elif d:
            c["cuando"] = "Desde " + d.group(2) + d.group(3)
        elif re.search(r"\b(hoy|actual|actualmente|este mes|este ano)\b", t):
            c["cuando"] = "Hoy"


def empezar_indagacion(est, chat, texto, notas):
    c = {"modo": "indaga", "pregunta": " ".join(texto.split())[:1500], "partes": [], "paso": ""}
    detectar(c, texto)
    est["conv"][str(chat)] = c
    intro = ["Buena pregunta \U0001f9d0"]
    if notas:
        intro += ["", "Para ir leyendo mientras tanto, esto ya lo investigamos \U0001f447"]
        for a in notas:
            intro += ["\u2022 " + a["titulo"], "  " + SITIO + a.get("archivo", "")]
    decir(chat, "\n".join(intro))
    siguiente_pregunta(chat, c)


def siguiente_pregunta(chat, c):
    listo = [{"text": "\u2705 Con eso alcanza", "callback_data": "listo"}]
    if "donde" not in c:
        c["paso"] = "donde"
        decir(chat, "Para investigarla bien, contame un par de cosas. \u00bfD\u00f3nde lo miramos?",
              botones=[[{"text": t, "callback_data": "dn:" + k}] for k, t in DONDE])
    elif "cuando" not in c:
        c["paso"] = "cuando"
        decir(chat, "\u00bfQu\u00e9 per\u00edodo te interesa?",
              botones=[[{"text": t, "callback_data": "cu:" + k}] for k, t in CUANDO])
    elif not c.get("foco_preguntado"):
        c["paso"] = "foco"
        c["foco_preguntado"] = True
        decir(chat, "\u00bfQu\u00e9 es lo que m\u00e1s te interesa saber? Contamelo con tus palabras: cu\u00e1nto, si creci\u00f3 "
              "o cay\u00f3, comparado con qui\u00e9n, en pesos o en d\u00f3lares, qu\u00e9 te hace dudar...",
              botones=[listo])
    else:
        confirmar_indaga(chat, c)


def seguir_indagacion(est, chat, c, texto):
    if c.get("paso") == "donde_cual":
        c["donde"] = texto[:120]
        siguiente_pregunta(chat, c)
        return
    if c.get("paso") == "agregar" or texto:
        c["partes"].append(texto[:800])
        detectar(c, texto)
    if c.get("paso") in ("foco", "agregar", "confirmar"):
        c["foco_preguntado"] = True
        confirmar_indaga(chat, c)
    else:
        siguiente_pregunta(chat, c)


def armar_pedido(c):
    p = c["pregunta"]
    titulo = p if len(p) <= 140 else p[:137].rsplit(" ", 1)[0] + "..."
    lineas = []
    if titulo != p:
        lineas.append("Pregunta completa: " + p)
    lineas.append("D\u00f3nde: " + c.get("donde", "sin precisar"))
    lineas.append("Per\u00edodo: " + c.get("cuando", "sin precisar"))
    if c["partes"]:
        lineas.append("Lo que quiere saber: " + " / ".join(c["partes"]))
    t = plano(p + " " + " ".join(c["partes"]))
    tipo = ("comparar" if re.search(r"\b(compar\w*|versus|vs|mejor|peor|contra)\b", t) else
            "verificar-cifra" if re.search(r"\b(es cierto|es verdad|verdad que|chequea\w*|verific\w*)\b", t) else
            "cuanto-cuesta" if re.search(r"\b(cuanto|cuesta|cobra|paga|gana|vale|sale)\b", t) else "otro")
    return titulo, tipo, "\n".join(lineas)[:1500]


def confirmar_indaga(chat, c):
    c["paso"] = "confirmar"
    titulo, _, _ = armar_pedido(c)
    l = ["As\u00ed la entiendo:", "", "\u00ab%s\u00bb" % titulo,
         "\U0001f4cd D\u00f3nde: " + c.get("donde", "sin precisar"),
         "\U0001f5d3\ufe0f Per\u00edodo: " + c.get("cuando", "sin precisar")]
    if c["partes"]:
        l.append("\U0001f3af Lo que quer\u00e9s saber: " + " / ".join(c["partes"])[:600])
    l += ["", "\u00bfLa mandamos a la redacci\u00f3n? Antes de investigar te muestro el enfoque."]
    decir(chat, "\n".join(l), botones=[[{"text": "\U0001f4e8 Mandar", "callback_data": "mandar"},
                                         {"text": "\u270f\ufe0f Agregar algo", "callback_data": "agregar"}],
                                        [{"text": "Cancelar", "callback_data": "cancelar"}]])


def ofrecer_anotado(est, chat):
    """Si dejo una pregunta anotada y ya no tiene nada en curso, se la ofrece."""
    a = est.setdefault("anotado", {}).get(str(chat))
    if not a or pl.en_curso(chat):
        return False
    decir(chat, "Antes de seguir: ten\u00e9s anotada esta pregunta para cuando terminara la anterior \U0001f4dd\n\n"
          "\u00ab%s\u00bb\n\n\u00bfLa mandamos ahora?" % a["titulo"],
          botones=[[{"text": "\U0001f4e8 S\u00ed, mandala", "callback_data": "anot_si"},
                    {"text": "Descartarla", "callback_data": "anot_no"}]])
    return True


def crear_y_avisar(chat, titulo, tipo, detalle):
    pid = pl.crear_desde_chat(chat, titulo, tipo, detalle)
    anotar("pedido %s creado desde el chat" % pid)
    decir(chat, "\U0001f4e8 \u00a1Recibido! La redacci\u00f3n lo lee y arma el enfoque: qu\u00e9 vamos a contestar, con qu\u00e9 "
          "fuentes y c\u00f3mo se va a ver la nota. Te lo mando por ac\u00e1 en unos minutos.", teclado=True)
    disparar_enfoque()


def al_boton_indaga(est, q, chat, accion, valor):
    sacar_botones(q)
    if accion in ("anot_si", "anot_no"):
        a = est["anotado"].pop(str(chat), None)
        if not a:
            decir(chat, "Ya no tengo nada anotado.", teclado=True)
        elif accion == "anot_no":
            decir(chat, "Listo, la descart\u00e9. Cuando quieras, preguntame otra cosa.", teclado=True)
        elif not ya_tiene_una(chat):
            crear_y_avisar(chat, a["titulo"], a["tipo"], a["detalle"])
        return
    c = est["conv"].get(str(chat))
    if not c or c.get("modo") != "indaga":
        decir(chat, "Esa pregunta ya no est\u00e1 en armado. Escribime lo que quer\u00e9s saber y arrancamos.", teclado=True)
        return
    if accion == "dn":
        if valor in ("prov", "pais"):
            c["paso"] = "donde_cual"
            decir(chat, "\u00bfCu\u00e1l?" if valor == "pais" else "\u00bfCu\u00e1l? (una provincia, una ciudad, o varias)")
            return
        c["donde"] = dict(DONDE).get(valor, "sin precisar").split(" ", 1)[-1] if valor != "igual" else "sin precisar"
        siguiente_pregunta(chat, c)
    elif accion == "cu":
        c["cuando"] = dict(CUANDO).get(valor, "sin precisar") if valor != "igual" else "sin precisar"
        siguiente_pregunta(chat, c)
    elif accion == "listo":
        c["foco_preguntado"] = True
        confirmar_indaga(chat, c)
    elif accion == "agregar":
        c["paso"] = "agregar"
        decir(chat, "Dale, escribime qu\u00e9 sumar \u270d\ufe0f")
    elif accion == "mandar":
        est["conv"].pop(str(chat), None)
        titulo, tipo, detalle = armar_pedido(c)
        abiertos = pl.en_curso(chat)
        if abiertos:
            est["anotado"][str(chat)] = {"titulo": titulo, "tipo": tipo, "detalle": detalle}
            decir(chat, "Ya ten\u00e9s una investigaci\u00f3n en marcha (\u00ab%s\u00bb). Esta queda anotada \U0001f4dd y te la "
                  "ofrezco apenas salga la otra: va una por persona, as\u00ed cada una tiene su tiempo."
                  % abiertos[0]["titulo"].strip()[:80], teclado=True)
            return
        crear_y_avisar(chat, titulo, tipo, detalle)


def responder_pregunta(est, chat, texto):
    """Texto suelto: saludo, agradecimiento, o una pregunta que se busca en las notas."""
    llano = plano(texto).strip(" !.?\u00a1\u00bf")
    if llano in SALUDOS:
        decir(chat, T_HOLA, teclado=True)
        return
    if llano in AGRADECE:
        decir(chat, T_GRACIAS, teclado=True)
        return
    # preguntas por el estado de lo que ya pidio (12/10/2026: "como viene mi investigacion?")
    if pregunta_por_su_pedido(llano):
        mis_pedidos(chat)
        return
    # "avisame cuando..." -> se le confirma que el aviso llega solo
    if re.search(r"\bavis(a|ame|en|ar)\b|\bme (avisas|avisan|escribis)\b|\bespero\b", llano):
        decir(chat, "\u00a1S\u00ed! Te escribo por ac\u00e1 apenas haya novedades: el enfoque para que lo apruebes, "
              "la vista previa antes de publicar y el link cuando salga. No ten\u00e9s que hacer nada \U0001f44c",
              teclado=True)
        return
    if ofrecer_anotado(est, chat):
        return
    empezar_indagacion(est, chat, texto, buscar_notas(texto))
    return
    notas = buscar_notas(texto)
    est["sugerido"][str(chat)] = texto[:1500]
    boton = [[{"text": "\U0001f4e8 Pedir esto como investigaci\u00f3n", "callback_data": "sug"}]]
    if notas:
        l = ["Lo m\u00e1s cercano que encontr\u00e9 entre lo que ya investigamos \U0001f447", ""]
        for a in notas:
            l.append("\u2022 " + a["titulo"])
            l.append("  " + SITIO + a.get("archivo", ""))
        l += ["", "\u00bfNo es exactamente lo que buscabas? Lo investigamos para vos."]
        decir(chat, "\n".join(l), botones=boton)
    else:
        decir(chat, "Eso todav\u00eda no lo investigamos \U0001f9d0 \u00bfQuer\u00e9s que lo hagamos? Te muestro el enfoque antes de "
              "arrancar y la nota antes de publicarla.", botones=boton)


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
    if p["estado"] == "moderacion":
        decir(chat, T_VINCULADO_MODERACION.format(titulo=p["titulo"]), teclado=True)
    else:
        decir(chat, T_VINCULADO.format(titulo=p["titulo"]), teclado=True)
    if p["estado"] == "enfoque_propuesto" and p.get("enfoque"):
        decir(chat, pl.texto_enfoque(p["id"], json.loads(p["enfoque"]), p["token"]),
              pl.botones_enfoque(p["id"]))


def sacar_botones(q):
    try:
        pl.tg("editMessageReplyMarkup", {"chat_id": q["message"]["chat"]["id"], "message_id": q["message"]["message_id"],
                                         "reply_markup": {"inline_keyboard": []}})
    except Exception:
        pass


def al_boton(est, q):
    chat = q["message"]["chat"]["id"]
    accion, _, pid = (q.get("data") or "").partition(":")
    pl.tg("answerCallbackQuery", {"callback_query_id": q["id"]})
    if accion in ("igpub", "igdes"):
        al_boton_instagram(q, chat, accion, pid)
        return
    if accion in ("cqa", "cqd") and pid.isdigit():
        al_boton_moderacion(q, chat, accion, int(pid))
        return
    if accion == "sug":
        sacar_botones(q)
        t = est["sugerido"].pop(str(chat), "")
        if t:
            empezar_indagacion(est, chat, t, [])
        else:
            pedir_nueva(est, chat)
        return
    if accion in ("dn", "cu", "listo", "mandar", "agregar", "anot_si", "anot_no"):
        al_boton_indaga(est, q, chat, accion, pid)
        return
    if accion in ("tipo", "detalle", "enviar", "cancelar"):
        al_boton_conversacion(est, q, chat, accion, pid)
        return
    if accion == "fb" and pid.isdigit():
        sacar_botones(q)
        est["revision"][str(chat)] = {"pid": int(pid), "tipo": "feedback"}
        anotar("pedido %s: el lector va a sugerir cambios" % pid)
        decir(chat, "Dale, contame qu\u00e9 cambiar\u00edas: el t\u00edtulo, el enfoque, qu\u00e9 destacar, algo que no se entiende... "
              "Con eso la rehacemos y te la muestro de nuevo. (Hay hasta 3 rondas de sugerencias "
              "por nota.)")
        return
    if accion in ("pub", "err") and pid.isdigit():
        sacar_botones(q)
        if accion == "pub":
            if pl.marcar_revision(pid, chat, True):
                anotar("pedido %s: el lector aprobo la vista previa" % pid)
                decir(chat, "\U0001f44d \u00a1Sale! La publicamos en un rato y te paso el link.", teclado=True)
                disparar_redaccion()
            else:
                decir(chat, "Esa vista previa ya no est\u00e1 esperando respuesta.", teclado=True)
        else:
            est["revision"][str(chat)] = {"pid": int(pid), "tipo": "error"}
            anotar("pedido %s: el lector va a contar un error de la vista previa" % pid)
            decir(chat, "Contame qu\u00e9 viste mal o qu\u00e9 falt\u00f3. Si ten\u00e9s la fuente (un link, una resoluci\u00f3n, "
                  "un documento), pegala: as\u00ed lo verificamos m\u00e1s r\u00e1pido.")
        return
    if accion not in ("ok", "no") or not pid.isdigit():
        return
    p = pedido_de(pid, chat)
    if not p:
        decir(chat, T_NO_ES_TUYO)
        return
    sacar_botones(q)   # no se responde dos veces
    if p["estado"] != "enfoque_propuesto":
        decir(chat, T_YA_NO)
        return
    if accion == "ok":
        r = pl.rpc("enfoque_responder", {"p_id": int(pid), "p_token": p["token"], "p_ok": True, "p_texto": None})
        anotar("pedido %s: enfoque aprobado por Telegram (%s)" % (pid, r))
        decir(chat, T_APROBADO if r == "aprobado" else T_YA_NO)
        if r == "aprobado":
            disparar_redaccion()   # periodo de prueba: sale el mismo dia
    else:
        est["esperando"][str(chat)] = int(pid)
        anotar("pedido %s: el lector va a escribir que queria" % pid)
        decir(chat, T_CONTAME)


def al_boton_instagram(q, chat, accion, nota):
    """Publicar / Descartar un posteo de Instagram (13/10/2026). Solo el editor."""
    import instagram_pub as igp
    try:
        es_editor = chat == igp.editor()
    except Exception:
        es_editor = False
    if not es_editor:
        anotar("boton de Instagram desde un chat que no es el del editor: ignorado")
        return
    sacar_botones(q)
    if accion == "igdes":
        anotar("instagram: el editor descarto %s" % nota)
        decir(chat, "Descartada. Te mando la siguiente \U0001f447")
        try:
            igp.descartar(nota)
        except SystemExit as e:
            decir(chat, "No pude ofrecer otra: %s" % e)
        return
    decir(chat, "Publicando en Instagram... \u23f3")
    try:
        r = igp.publicar(nota)
        anotar("instagram: publicada %s" % nota)
        decir(chat, "\u2705 Publicada en Instagram:\n" + (r.get("permalink") or "https://www.instagram.com/coninteres.ar/"))
    except SystemExit as e:
        anotar("instagram: fallo la publicacion de %s: %s" % (nota, e))
        decir(chat, "\u26a0\ufe0f No se pudo publicar: %s" % e)


def al_boton_moderacion(q, chat, accion, id_):
    """Preguntas de los lectores (13/10/2026): lo que entra por el portal o por los comentarios
    de Instagram lo aprueba el editor antes de mostrarse en el historial del panel. Una
    pregunta no es un pedido: no dispara ninguna investigacion. Solo el editor."""
    import comunidad, instagram_pub as igp
    try:
        es_editor = chat == igp.editor()
    except Exception:
        es_editor = False
    if not es_editor:
        anotar("boton de moderacion desde un chat que no es el del editor: ignorado")
        return
    sacar_botones(q)
    try:
        r = comunidad.moderar_pregunta(id_, accion)
    except Exception as e:
        anotar("moderacion %s %s fallo: %s" % (accion, id_, e))
        decir(chat, "\u26a0\ufe0f No pude registrar la moderaci\u00f3n: %s" % e)
        return
    anotar("moderacion %s %s: %s" % (accion, id_, r))
    decir(chat, r)


def al_boton_conversacion(est, q, chat, accion, valor):
    c = est["conv"].get(str(chat))
    sacar_botones(q)
    if accion == "cancelar":
        est["conv"].pop(str(chat), None)
        decir(chat, "Listo, no mandamos nada. Cuando quieras, ac\u00e1 estoy.", teclado=True)
        return
    if not c:
        decir(chat, "Ese pedido ya no est\u00e1 en armado. Escribime lo que quer\u00e9s saber y arrancamos de nuevo.", teclado=True)
        return
    if accion == "tipo" and c["paso"] == "tipo" and valor in dict(TIPOS):
        c.update(paso="detalle", tipo=valor)
        decir(chat, "\u00bfMe cont\u00e1s un poco m\u00e1s? Por qu\u00e9 te interesa, d\u00f3nde lo viste, con qu\u00e9 te gustar\u00eda comparar...",
              botones=[[{"text": "Saltear", "callback_data": "detalle:no"}]])
        return
    if accion == "detalle" and c["paso"] == "detalle":
        c.update(paso="confirmar", detalle="")
        confirmar(chat, c)
        return
    if accion == "enviar" and c["paso"] == "confirmar":
        est["conv"].pop(str(chat), None)
        if ya_tiene_una(chat):
            return
        pid = pl.crear_desde_chat(chat, c["titulo"], c["tipo"], c.get("detalle", ""))
        anotar("pedido %s creado desde el chat" % pid)
        decir(chat, "\U0001f4e8 \u00a1Recibido! Ahora la redacci\u00f3n lo lee y arma el enfoque: qu\u00e9 vamos a contestar, con qu\u00e9 "
              "fuentes y c\u00f3mo se va a ver la nota. Te lo mando por ac\u00e1 en unos minutos para que me digas si va.",
              teclado=True)
        disparar_enfoque()
        return
    decir(chat, "Ese bot\u00f3n ya no corresponde. Seguimos desde el \u00faltimo mensaje.")


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
    elif str(chat) in est["conv"] and not texto.startswith("/") and pregunta_por_su_pedido(plano(texto).strip(" !.?\u00a1\u00bf")):
        tipo_msg = "estado en medio de la charla"
    elif str(chat) in est["conv"] and not texto.startswith("/"):
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
        est["conv"].pop(str(chat), None)
        pedir_nueva(est, chat)
        return
    if tipo_msg == "estado en medio de la charla":
        mis_pedidos(chat)
        decir(chat, "Y la pregunta que est\u00e1bamos armando sigue ac\u00e1: seguimos cuando quieras \U0001f44c")
        return
    if tipo_msg == "armando pedido" and seguir_conversacion(est, chat, texto):
        return
    if tipo_msg == "error de vista previa":
        r = est["revision"].pop(str(chat))
        if not isinstance(r, dict):          # estado viejo (antes del 13/10): era un error de datos
            r = {"pid": int(r), "tipo": "error"}
        pid = r["pid"]
        if r["tipo"] == "feedback":
            if pl.marcar_revision(pid, chat, "feedback", texto):
                anotar("pedido %s: el lector sugirio cambios en la vista previa" % pid)
                decir(chat, "Anotado \u270d\ufe0f La rehacemos con eso y te la muestro de nuevo antes de publicar. "
                      "Lo que no cambia son los datos: cambia c\u00f3mo se cuenta.", teclado=True)
                disparar_redaccion()
            else:
                decir(chat, "Esa vista previa ya no est\u00e1 esperando sugerencias.", teclado=True)
            return
        if pl.marcar_revision(pid, chat, "error", texto):
            anotar("pedido %s: el lector senalo un error en la vista previa" % pid)
            decir(chat, "Gracias \U0001f64f Lo revisamos contra la fuente: si ten\u00e9s raz\u00f3n, se corrige antes de publicar. "
                  "Te cuento qu\u00e9 encontramos.", teclado=True)
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
    if texto:
        responder_pregunta(est, chat, texto)


def main():
    anotar("bot iniciado")
    try:
        pl.tg("setMyCommands", {"commands": COMANDOS})
    except Exception:
        anotar("AVISO: no se pudo registrar el menu de comandos")
    est = leer_estado()
    for k in ("esperando", "conv", "revision", "sugerido", "anotado"):
        est.setdefault(k, {})
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
