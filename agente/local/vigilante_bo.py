"""
vigilante_bo.py -- vigila la primera seccion del Boletin Oficial y marca las
posibles PRIMICIAS: normas que le cambian la plata a la gente (montos, haberes,
tarifas, aranceles, escalas salariales) antes de que las cuenten los diarios.

MODO SOLO AVISO (decision del editor, 11/10/2026): no llama a la redaccion ni
publica nada. Anota lo que encontro para medir durante una o dos semanas
cuantas primicias posibles hay por dia y cuantas habriamos sacado primero.

Uso:
  python agente/local/vigilante_bo.py              una vuelta (la tarea de la VM)
  python agente/local/vigilante_bo.py --ids A-B    calibrar: puntua los avisos
                                                   con id entre A y B, sin estado
Archivos (en coninteres-logs, fuera del repo: es estado de la maquina):
  bo_vistos.json       ids ya leidos, para avisar solo lo nuevo
  bo_candidatas.jsonl  una linea por candidata, con la hora en que se detecto
  bo_corridas.jsonl    una linea por vuelta: edicion, avisos, nuevos, candidatas,
                       error. Una vuelta que no encuentra avisos en la edicion es
                       una FALLA (cambio la pagina), no un "no hay nada".
"""
import datetime as dt, html, json, os, re, sys, time, urllib.request

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOGS = os.path.join(os.path.expanduser("~"), "coninteres-logs")
BASE = "https://www.boletinoficial.gob.ar"
UA = {"User-Agent": "Mozilla/5.0 (ConInteres vigilante del Boletin Oficial; +https://coninteres.com/como-trabajamos.html)"}
UMBRAL = 5

def ahora_ar():
    return dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=3)

def bajar(url, intentos=3):
    for i in range(intentos):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                return r.read().decode("utf-8", "replace")
        except Exception:
            if i == intentos - 1:
                raise
            time.sleep(5 * (i + 1))

def texto(h):
    h = re.sub(r"(?is)<(style|script)[^>]*>.*?</\1>", " ", h)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()

# ---- lectura ---------------------------------------------------------------

def listado():
    """(edicion AAAAMMDD, [(id, fecha, rubro, titulo)]) de la primera seccion."""
    s = bajar(BASE + "/seccion/primera")
    m = re.search(r"fechaSeleccionadaYMD = '(\d{8})'", s)
    edicion = m.group(1) if m else ""
    avisos, rubro = [], ""
    for t in re.finditer(r'(?s)<h5 class="seccion-rubro[^"]*">(.*?)</h5>|<a href="/detalleAviso/primera/(\d+)/(\d{8})"[^>]*>(.*?)</a>', s):
        if t.group(1) is not None:
            rubro = texto(t.group(1))
        else:
            avisos.append((t.group(2), t.group(3), rubro, texto(t.group(4))))
    return edicion, avisos

def aviso(i, fecha):
    url = f"{BASE}/detalleAviso/primera/{i}/{fecha}"
    s = bajar(url)
    def tag(t):
        m = re.search(rf"(?s)<div id=\"tituloDetalleAviso\".*?<{t}>(.*?)</{t}>", s)
        return texto(m.group(1)) if m else ""
    a = s.find('id="cuerpoDetalleAviso"')
    b = s.find("</article>", a)
    cuerpo = texto(s[a:b]) if a != -1 else ""
    return {"id": i, "fecha_bo": fecha, "url": url, "organismo": tag("h1"),
            "norma": tag("h2"), "sumario": tag("h6"), "cuerpo": cuerpo}

# ---- puntaje ---------------------------------------------------------------

MONTO = re.compile(r"\$\s?\d{1,3}(?:\.\d{3})+(?:,\d+)?|\$\s?\d{4,}|PESOS [A-Z ,]{6,}\(\$", re.I)
PLATA = [
    (r"haber(es)? (minimo|mínimo|previsional|jubilatori)|movilidad jubilatoria|jubilaci|\bpensi[oó]n", "haberes y jubilaciones"),
    (r"asignaci[oó]n (universal|familiar|por hijo|por embarazo)|asignaciones familiares", "asignaciones"),
    (r"\bbono\b|suma (fija|no remunerativa|extraordinaria)", "bono o suma fija"),
    (r"salario m[ií]nimo|escala(s)? salarial|acuerdo salarial|remuneraciones? (b[aá]sicas|m[ií]nimas)|homol[oó]g", "sueldos y paritarias"),
    (r"retiros? (voluntario|de voluntad)|indemnizaci", "retiros e indemnizaciones"),
    (r"cuadro tarifario|tarifa|peaje|boleto|pasaje", "tarifas"),
    (r"derechos? de (exportaci|importaci)|arancel|al[ií]cuota|impuesto|tasa de|monotribut|m[ií]nimo no imponible|deducci", "impuestos y aranceles"),
    (r"subsidio|tarifa social|beca|prestaci[oó]n (dineraria|econ[oó]mica)|canasta", "subsidios y prestaciones"),
    (r"precio|valor (de|del) (la )?(unidad|m[oó]dulo|punto)|unidad retributiva|m[oó]dulo", "precios y valores de referencia"),
    (r"audiencia p[uú]blica", "audiencia publica (suele anticipar tarifas)"),
    (r"\bRIGI\b|grandes inversiones|privatizaci|venta .{0,60}acciones", "grandes inversiones o privatizaciones"),
    (r"tope|l[ií]mite (de|m[aá]ximo)|monto m[aá]ximo|actual[ií]zase|increm[eé]ntase|f[ií]jase", "fija o actualiza un monto"),
]
ORGANISMOS = r"ENTE (NACIONAL )?REGULADOR|SEGURIDAD SOCIAL|ANSES|RECAUDACI[OÓ]N|ARCA|MINISTERIO DE ECONOM|ENERG[IÍ]A|ENTE NACIONAL REGULADOR|TRABAJO|CAPITAL HUMANO|BANCO CENTRAL|SERVICIOS DE SALUD|TRANSPORTE|PODER EJECUTIVO|COMERCIO|JEFATURA DE GABINETE"
# temas que casi siempre son una pregunta de plata de mucha gente
FUERTES = r"cuadro tarifario|haber m[ií]nimo|salario m[ií]nimo|retiros? (voluntario|de voluntad)|asignaci[oó]n universal|\bbono\b|derechos? de exportaci|monotribut|movilidad jubilatoria|ganancias|canasta b[aá]sica|derechos? de importaci|audiencia p[uú]blica|\bRIGI\b|privatizaci"
# un anexo que fija valores: los montos no estan en el cuerpo pero existen
ANEXO_VALORES = r"(apru[eé]base|aprobar|f[ií]jase|fijar|establ[eé]cese|establecer|actual[ií]zase|actualizar)[^.]{0,200}(cuadro|valores|montos|tarifa|escala|importes)[^.]{0,200}anexo"
RUTINA = [
    r"des[ií]gnase|dase por designad|designaci[oó]n transitoria|pr[oó]rr[oó]gase .{0,80}designaci",
    r"ac[eé]ptase la renuncia|dase por conclu[ií]d|lim[ií]tase",
    r"asignase .{0,60}funci[oó]n|convocase a (concurso|elecciones)",
    r"ejercicio combinado|tropas|sumario|inscr[ií]base en el registro|reconocese .{0,40}personer",
    r"danse? por asignad|dase por prorrogad|sobrese|subasta|tribunal de disciplina|imponer .{0,30}sanci",
]

def parte_dispositiva(c):
    m = re.search(r"(RESUELVE|DECRETA|DISPONE|RESUELVEN|ACUERDA)\s*:", c)
    return c[m.end():] if m else c

def puntuar(a, cubiertas=""):
    disp = parte_dispositiva(a["cuerpo"])
    cab = " ".join([a["organismo"], a["norma"], a["sumario"]])
    motivos, p = [], 0
    montos = [m.group(0) for m in MONTO.finditer(disp)]
    if montos:
        p += 3; motivos.append(f"montos en lo que dispone ({len(montos)})")
    elif re.search(ANEXO_VALORES, disp[:3000], re.I):
        p += 2; motivos.append("fija valores en un anexo")
    temas = [n for r, n in PLATA if re.search(r, cab + " " + disp[:4000], re.I)]
    p += 2 * min(len(temas), 2); motivos += temas
    if re.search(FUERTES, cab + " " + disp[:4000], re.I):
        p += 2; motivos.append("tema de mucha gente")
    if a.get("rubro", "").upper().startswith("LEY") or re.match(r"Ley \d", a["norma"]):
        p += 2; motivos.append("ley")
    elif a["sumario"].startswith("DNU"):
        p += 1; motivos.append("DNU")
    if re.search(ORGANISMOS, a["organismo"], re.I):
        p += 1; motivos.append("organismo con plata de la gente")
    if any(re.search(r, a["sumario"] + " " + disp[:600], re.I) for r in RUTINA):
        p -= 4; motivos.append("parece rutina administrativa")
    if re.search(r"DNRYRT|DTRT", a["sumario"]) or re.search(r"RELACIONES Y REGULACIONES DEL TRABAJO", a["organismo"], re.I):
        # registro de acuerdos salariales de cada convenio: salen de a decenas
        # por dia y casi todos son de empresas chicas. Se cuentan aparte.
        p -= 2; motivos.append("registro de acuerdo salarial")
    cubierto = bool(a["norma"]) and a["norma"].lower() in cubiertas
    if cubierto:
        p -= 3; motivos.append("ya figura en data/cubiertas.json")
    ctx = []
    for m in list(MONTO.finditer(disp))[:3]:
        ctx.append(disp[max(0, m.start() - 120):m.end() + 60])
    return p, motivos, ctx, cubierto

def leer_cubiertas():
    try:
        return open(os.path.join(ROOT, "data", "cubiertas.json"), encoding="utf-8").read().lower()
    except OSError:
        return ""

# ---- vuelta ----------------------------------------------------------------

def anotar(nombre, obj):
    os.makedirs(LOGS, exist_ok=True)
    with open(os.path.join(LOGS, nombre), "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def vuelta():
    hora = ahora_ar().strftime("%Y-%m-%dT%H:%M:%S")
    reg = {"hora": hora, "edicion": "", "avisos": 0, "nuevos": 0, "candidatas": 0, "error": ""}
    ruta = os.path.join(LOGS, "bo_vistos.json")
    try:
        vistos = json.load(open(ruta, encoding="utf-8")) if os.path.exists(ruta) else {}
        edicion, avisos = listado()
        reg["edicion"], reg["avisos"] = edicion, len(avisos)
        if not avisos:
            raise RuntimeError("la edicion no trajo ningun aviso: cambio la pagina o fallo la lectura")
        primera_vez = not vistos
        cub = leer_cubiertas()
        for i, fecha, rubro, titulo in avisos:
            if i in vistos:
                continue
            reg["nuevos"] += 1
            if primera_vez:
                # la primera vuelta marca la edicion como vista sin avisar:
                # lo de hoy ya no es primicia de nadie
                vistos[i] = fecha
                continue
            a = aviso(i, fecha)
            p, motivos, ctx, cubierto = puntuar(a, cub)
            vistos[i] = fecha
            if p >= UMBRAL:
                reg["candidatas"] += 1
                anotar("bo_candidatas.jsonl", {
                    "detectado": hora, "fecha_bo": fecha, "id": i, "url": a["url"], "rubro": rubro,
                    "organismo": a["organismo"], "norma": a["norma"], "sumario": a["sumario"],
                    "puntaje": p, "motivos": motivos, "montos": ctx, "cubierto": cubierto,
                    "primer_medio": "", "nuestra_nota": ""})
            time.sleep(1)
        corte = (ahora_ar() - dt.timedelta(days=40)).strftime("%Y%m%d")
        vistos = {k: v for k, v in vistos.items() if v >= corte}
        tmp = ruta + ".tmp"
        json.dump(vistos, open(tmp, "w", encoding="utf-8"))
        os.replace(tmp, ruta)
        if primera_vez:
            reg["error"] = ""
            reg["nota"] = "primera vuelta: edicion marcada como vista sin avisar"
    except Exception as e:
        reg["error"] = f"{type(e).__name__}: {e}"[:300]
    anotar("bo_corridas.jsonl", reg)
    print(json.dumps(reg, ensure_ascii=False))
    return 1 if reg["error"] else 0

def calibrar(desde, hasta):
    cub = leer_cubiertas()
    for i in range(desde, hasta + 1):
        try:
            a = aviso(str(i), "20260101")
        except Exception as e:
            print(f"{i}\tERROR\t{e}"); continue
        if not a["organismo"]:
            continue
        p, motivos, ctx, _ = puntuar(a, cub)
        marca = "**" if p >= UMBRAL else "  "
        print(f"{marca}{p:>3}\t{i}\t{a['organismo'][:40]}\t{a['norma'][:28]}\t{a['sumario'][:90]}\t{'; '.join(motivos)}", flush=True)
        time.sleep(0.5)

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--ids":
        d, h = sys.argv[2].split("-")
        calibrar(int(d), int(h))
    else:
        sys.exit(vuelta())
