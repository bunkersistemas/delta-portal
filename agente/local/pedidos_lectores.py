"""
pedidos_lectores.py -- pedidos de investigacion de los lectores (piloto del 12/10/2026).

Los pedidos entran por investigacion.html a una tabla de Supabase. La pagina solo
puede AGREGAR; este script lee y cambia el estado con la llave secreta, que vive
FUERA del repo, en la VM (coninteres-privado/supabase_secret.txt).

  elegir <hoy AAAA-MM-DD>
      Imprime PEDIDO|<id>|<titulo>  o  GENERAL|motivo.
      Editor 12/10/2026: una nota por dia sobre las preguntas, para probar rapido.
      Le toca si hoy no se publico ninguna nota con "pedido" y hay pedidos nuevos.
      Elige uno AL AZAR, lo pasa a en_investigacion ANTES de trabajar y deja el
      texto (sin el correo) en coninteres-logs/pedido_actual.json.
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
ACTUAL = os.path.join(LOGS, "pedido_actual.json")
HORAS_COLGADO = 6   # en_investigacion sin borrador en la cola por mas de esto: la corrida se corto


def pedir(metodo, consulta="", cuerpo=None):
    k = open(LLAVE, encoding="ascii").read().strip()
    h = {"apikey": k, "Authorization": "Bearer " + k, "Content-Type": "application/json",
         "Prefer": "return=representation"}
    datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
    req = urllib.request.Request(URL + consulta, data=datos, headers=h, method=metodo)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8") or "[]")


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


def elegir(hoy):
    # 1. los que quedaron colgados (corrida cortada) no se reintentan para siempre
    lim = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=HORAS_COLGADO)).isoformat()
    en_cola = pedidos_en_cola()
    for p in pedir("GET", "?select=id,creado&estado=eq.en_investigacion&creado=lt." + urllib.parse.quote(lim)):
        if p["id"] not in en_cola:
            cerrar(p["id"], "descartado", "la corrida que lo investigaba se corto")
    # 2. una por dia
    if any(x.get("pedido") and x.get("fecha") == hoy for x in articulos()):
        print("GENERAL|hoy ya salio una nota pedida por un lector")
        return
    nuevos = pedir("GET", "?select=id,titulo,tipo,detalle,origen&estado=eq.recibido"
                          "&or=(origen.is.null,origen.neq.prueba)&order=creado")
    if not nuevos:
        print("GENERAL|no hay pedidos nuevos")
        return
    p = random.choice(nuevos)
    # el estado cambia ANTES de trabajar: un pedido que corta la corrida no se repite
    filas = pedir("PATCH", "?id=eq.%d&estado=eq.recibido" % p["id"], {"estado": "en_investigacion"})
    if len(filas) != 1:
        print("GENERAL|el pedido %s cambio de estado mientras se elegia" % p["id"])
        return
    os.makedirs(LOGS, exist_ok=True)
    with open(ACTUAL, "w", encoding="utf-8") as f:
        json.dump({"id": p["id"], "tipo": p["tipo"], "titulo": p["titulo"], "detalle": p["detalle"]},
                  f, ensure_ascii=False, indent=2)
    titulo = " ".join(p["titulo"].split()).encode("ascii", "replace").decode("ascii")
    print("PEDIDO|%d|%s (%d nuevos)" % (p["id"], titulo, len(nuevos)))


def resumen():
    """JSON para el resumen diario de n8n: pedidos de los ultimos 30 dias, SIN correo."""
    try:
        desde = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)).isoformat()
        filas = pedir("GET", "?select=id,creado,cerrado,origen,tipo,estado,titulo,motivo,salida,correo"
                             "&or=(origen.is.null,origen.neq.prueba)&creado=gt." + urllib.parse.quote(desde)
                             + "&order=creado")
        for f in filas:
            f["con_correo"] = bool(f.pop("correo", None))
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
    elif a == ["resumen"]:
        resumen()
    elif a == ["ver"]:
        ver()
    else:
        print(__doc__)
        sys.exit(1)
