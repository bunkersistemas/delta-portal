#!/usr/bin/env python3
"""
build_portada.py — Regenera la portada (index.html) del portal Con Interés
a partir de los manifiestos data/articulos.json y data/cola.json.

Lo ejecuta el agente Publicador en cada publicación. Determinista:
mismos manifiestos -> misma portada.

Uso:  python3 scripts/build_portada.py
"""
import json, os, datetime
from html import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

# URL base pública del sitio. Cuando se configure un dominio propio,
# cambiar SOLO esta línea (ej. "https://deltadiario.com").
SITE = "https://coninteres.com"

def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)

art = load("articulos.json")
cola = load("cola.json")
portal = art["portal"]
# La nota más reciente es la que la redacción insertó ARRIBA del manifiesto (orden de
# publicación real). NO se ordena por "hora": ese campo es un rótulo y no siempre es
# confiable. Así la principal es siempre la última nota publicada.
articulos = list(art["articulos"])
borradores = cola.get("borradores", [])

# ---- helpers -----------------------------------------------------------
MESES = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"]
DIAS = ["LUN","MAR","MIÉ","JUE","VIE","SÁB","DOM"]
try:
    _md = datetime.date.fromisoformat(portal["actualizado"][:10])
    FECHA_MASTHEAD = f"{DIAS[_md.weekday()]} {_md.day} · {MESES[_md.month-1].upper()} · {_md.year}"
except Exception:
    FECHA_MASTHEAD = ""
def fecha_bonita(f):
    try:
        d = datetime.date.fromisoformat(f)
        return f"{d.day} {MESES[d.month-1]} {d.year}"
    except Exception:
        return f

def actualizado_hace(iso):
    try:
        t = datetime.datetime.fromisoformat(iso)
        return t.strftime("%d/%m %H:%M")
    except Exception:
        return iso

SEC_COLOR = {
    "ECONOMÍA": "#0E7C86", "ECONOMÍA PROVINCIAL": "#C4701F", "MERCADOS": "#0A5C63", "MUNDO": "#7A5CC4",
    # compat / fallback
    "PLATA": "#0E7C86", "MÁQUINAS": "#C4701F", "CIENCIA": "#2E8B6F",
    "EL MUNDO EN NÚMEROS": "#7A5CC4", "DEPORTES": "#C0392B", "NEGOCIOS": "#0A5C63",
    "TECNOLOGÍA": "#C4701F",
}

def chip_verif(v):
    if v == "verificada":
        return '<span class="verif ok">&#10003; Verificada</span>'
    if v == "pendiente":
        return '<span class="verif pend">&#9651; En verificación</span>'
    return f'<span class="verif">{escape(v)}</span>'

# ---- lead + grid -------------------------------------------------------
def card_lead(a):
    sc = SEC_COLOR.get(a["seccion"], "#0E7C86")
    num = a.get('numero','')
    # el número ancla se achica según su longitud para no desbordar la caja
    n = len(num)
    fs = 64 if n <= 5 else (50 if n <= 8 else 38)
    return f"""
    <a class="lead" data-sec="{escape(a['seccion'])}" href="{escape(a['archivo'])}">
      <div class="lead-num" style="--sc:{sc}">
        <span class="ln-big" style="font-size:{fs}px">{escape(num)}</span>
        <span class="ln-lab">{escape(a.get('numero_label',''))}</span>
      </div>
      <div class="lead-body">
        <div class="kick" style="color:{sc}">{escape(a['seccion'])} <span>/ {escape(a.get('formato',''))}</span></div>
        <h2>{escape(a['titulo'])}</h2>
        <p>{escape(a['bajada'])}</p>
        <div class="meta">{chip_verif(a.get('verificacion',''))}<span class="dot"></span>{escape(a.get('lectura',''))}<span class="dot"></span>{fecha_bonita(a['fecha'])}</div>
      </div>
    </a>"""

# ---- agrupadores por PREGUNTA del lector (no por sección de redacción) ---
# La sección editorial interna (manifiestos) no cambia; cambia cómo se MUESTRA.
TU_PLATA_KW = [
    "salario", "sueldo", "inflación", "precios", "canasta", "crédito", "hipotec",
    "alquiler", "jubilad", "bono", "monotributo", "mora", "familias", "tarjeta",
    "plazo fijo", "consumo", "carne", "courier", "compras", "qr", "bolsillo", "cuotas",
]
GRUPOS = [
    {"id": "tu-plata", "label": "Tu plata", "sub": "sueldo · precios · ahorro · crédito", "color": "#0E7C86"},
    {"id": "el-pais", "label": "El país", "sub": "actividad · empleo · cuentas públicas · energía", "color": "#C4701F"},
    {"id": "los-mercados", "label": "Los mercados", "sub": "dólar · bonos · empresas · inversión", "color": "#0A5C63"},
    {"id": "tu-provincia", "label": "Tu provincia", "sub": "las economías del interior, en números", "color": "#2E8B6F"},
    {"id": "el-mundo", "label": "El mundo", "sub": "lo global que toca a la Argentina", "color": "#7A5CC4"},
    {"id": "deportes", "label": "Deportes", "sub": "la economía del deporte, en números", "color": "#C0392B"},
]
GRUPO_POR_ID = {g["id"]: g for g in GRUPOS}


# ---- paginas de seccion -------------------------------------------------
# Cada grupo tiene su propia pagina, paginada. Viven en la raiz como
# seccion-<id>.html para que las rutas relativas del resto del sitio
# (assets/, articulos/, aprender.html...) sigan valiendo sin cambios.
POR_PAGINA = 20

def url_seccion(gid, pag=1):
    return f"seccion-{gid}.html" if pag <= 1 else f"seccion-{gid}-{pag}.html"

def grupo_de(a):
    s = a["seccion"]
    if s == "MERCADOS":
        return "los-mercados"
    if s == "ECONOMÍA PROVINCIAL":
        return "tu-provincia"
    if s == "MUNDO":
        return "el-mundo"
    if s == "DEPORTES":
        return "deportes"
    texto = (a["titulo"] + " " + a.get("bajada", "") + " " + a.get("numero_label", "")).lower()
    return "tu-plata" if any(k in texto for k in TU_PLATA_KW) else "el-pais"

def card(a, con_kick=False):
    """Tarjeta clásica de diario: título primero; el dato como acento debajo."""
    g = GRUPO_POR_ID[grupo_de(a)]
    kick = f'<div class="kick" style="color:{g["color"]}">{escape(g["label"])}</div>' if con_kick else ""
    return f"""
    <a class="card" data-sec="{escape(a['seccion'])}" href="{escape(a['archivo'])}" style="--sc:{g['color']}">
      {kick}
      <h3>{escape(a['titulo'])}</h3>
      <div class="card-num"><b>{escape(a.get('numero',''))}</b> {escape(a.get('numero_label',''))}</div>
      <div class="meta">{chip_verif(a.get('verificacion',''))}<span class="dot"></span>{fecha_bonita(a['fecha'])}</div>
    </a>"""

def card_lider(a):
    """La nota líder de cada grupo: formato HISTORIA — título grande,
    bajada visible, el número como acento a la derecha."""
    g = GRUPO_POR_ID[grupo_de(a)]
    num = a.get("numero", "")
    n = len(num)
    fs = 42 if n <= 6 else (32 if n <= 9 else 24)
    return f"""
    <a class="lider" href="{escape(a['archivo'])}" style="--sc:{g['color']}">
      <div class="l-body">
        <div class="kick" style="color:{g['color']}">{escape(g['label'])} <span>/ {escape(a.get('formato',''))}</span></div>
        <h3>{escape(a['titulo'])}</h3>
        <p>{escape(a['bajada'])}</p>
        <div class="meta">{chip_verif(a.get('verificacion',''))}<span class="dot"></span>{escape(a.get('lectura',''))}<span class="dot"></span>{fecha_bonita(a['fecha'])}</div>
      </div>
      <div class="l-num"><span class="ln" style="font-size:{fs}px">{escape(num)}</span><span class="ll">{escape(a.get('numero_label',''))}</span></div>
    </a>"""

def fila(a):
    """Fila compacta de una línea: número + título + fecha."""
    g = GRUPO_POR_ID[grupo_de(a)]
    return f"""
    <a class="row" href="{escape(a['archivo'])}">
      <span class="r-num" style="color:{g['color']}">{escape(a.get('numero',''))}</span>
      <span class="r-tit">{escape(a['titulo'])}</span>
      <span class="r-fecha">{fecha_bonita(a['fecha'])}</span>
    </a>"""

# La nota PRINCIPAL es la marcada "destacada" (elección editorial); si no hay ninguna,
# es la primera de la lista. Después vienen 4 DESTACADAS (las más recientes) y el
# resto se agrupa POR SECCIÓN — portada curada, no un muro de notas.
lead = next((a for a in articulos if a.get("destacada")), None) or (articulos[0] if articulos else None)

resto = [a for a in articulos if a is not lead]
destacadas = resto[:4]
por_seccion = resto[4:]

destacadas_html = ""
if destacadas:
    destacadas_html = (
        '<div class="rail-head"><span class="rh-txt">Lo último</span><span class="rh-rule"></span></div>'
        '<div class="grid grid-2">' + "\n".join(card(a, con_kick=True) for a in destacadas) + "</div>"
    )

# ---- LINEA DE TIEMPO: la portada se ordena por dia, no por seccion --------
# Cada dia es un nodo de la linea. Dentro del dia hay jerarquia: la nota
# destacada va grande, dos en tarjeta y hasta tres en fila. Si el dia tiene
# mas, se enlaza al archivo, que esta agrupado por dia.
DIAS_LARGO = ["lunes","martes","miercoles","jueves","viernes","sabado","domingo"]
DIAS_LARGO = ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"]
MESES_LARGO = ["enero","febrero","marzo","abril","mayo","junio",
               "julio","agosto","septiembre","octubre","noviembre","diciembre"]
TOPE_DIA = 6
# La portada suma un dia por dia, asi que el detalle se degrada con la
# antiguedad: los primeros dias llevan tarjeta grande, los siguientes tarjetas
# normales y los mas viejos solo filas. Asi la linea de tiempo queda completa
# sin que la pagina crezca sin techo.
DIAS_DESTACADOS = 3   # con tarjeta grande
DIAS_CON_TARJETA = 7  # hasta aca, con tarjetas; despues solo filas

def titulo_dia(f, es_hoy=False):
    try:
        d = datetime.date.fromisoformat(f)
        t = f"{DIAS_LARGO[d.weekday()]} {d.day} de {MESES_LARGO[d.month-1]}"
        return ("HOY · " + t) if es_hoy else t
    except Exception:
        return f

_por_dia = {}
for a in articulos:
    _por_dia.setdefault(a["fecha"], []).append(a)
_dias = sorted(_por_dia, reverse=True)
_hoy = portal.get("actualizado", "")[:10]

# La portada admite variantes de maqueta para poder compararlas en el navegador
# antes de decidir:
#   lead      (default) la nota destacada del dia sale de la linea de tiempo y
#             sube arriba de todo, bajo el rotulo "La nota del dia", y el
#             semaforo va en franja de 5 columnas. Decision del editor
#             (31/08/2026): la portada tiene que decir cual es LA nota, y eso
#             pesa mas que mantener la lider dentro de su dia. Costo asumido:
#             el nodo de hoy dice "4 notas mas" en vez de "5 notas".
#   compacta  solo la franja del semaforo; la lider queda dentro de su dia.
#   actual    la portada previa, con el semaforo en 5 tarjetas grandes.
# Las no-default se piden con CI_VARIANTE y escriben en CI_SALIDA para no pisar
# index.html: CI_VARIANTE=lead CI_SALIDA=preview.html python scripts/build_portada.py
VARIANTE = os.environ.get("CI_VARIANTE", "lead")
SALIDA_PORTADA = os.environ.get("CI_SALIDA", "index.html")

# En la variante "lead" la nota destacada del dia mas reciente sale de la linea
# de tiempo y se muestra arriba, para que el primer titular entre en la primera
# pantalla sin tener que scrollear.
lead_portada = None
if VARIANTE == "lead" and _dias:
    _d0 = _por_dia[_dias[0]]
    lead_portada = next((a for a in _d0 if a.get("destacada")), _d0[0])

# ---- la pregunta del dia en la portada ----------------------------------
# El cascaron se genera vacio y lo llena assets/pregunta.js leyendo
# data/pregunta.json: asi la portada nunca muestra una pregunta vieja aunque
# pasen dias sin rehacer el build. La logica (respuesta correcta, racha) es la
# misma que usa pregunta.html, para que no puedan divergir.
pregunta_html = """
    <section class="pregunta-band" id="pregunta" hidden>
      <div class="pb-head">
        <span class="pb-kick">? La pregunta del d&iacute;a</span>
        <span class="pb-fecha" id="pbFecha"></span>
        <span class="pb-rule"></span>
        <span class="pb-racha" id="pbRacha"></span>
      </div>
      <p class="pb-q" id="pbQ"></p>
      <div class="pb-ops" id="pbOps"></div>
      <div class="pb-res" id="pbRes">
        <div class="pb-ver" id="pbVer"></div>
        <p class="pb-expl" id="pbExpl"></p>
        <div class="pb-links">
          <a href="pregunta.html" id="pbMas">Ver la explicaci&oacute;n completa &rarr;</a>
          <a href="#" id="pbNota" hidden>Leer la nota &rarr;</a>
        </div>
      </div>
    </section>"""

timeline_html = ""
subio_la_lider = False
for i, f in enumerate(_dias):
    del_dia = _por_dia[f]
    subio_la_lider = lead_portada is not None and i == 0
    if subio_la_lider:
        # ya se muestra arriba: el dia lista el resto, y si no queda nada el
        # nodo del dia no se dibuja (seria un dia vacio abajo de su propia nota)
        del_dia = [a for a in del_dia if a is not lead_portada]
        if not del_dia:
            continue
    # dentro del dia manda la marcada como destacada; si no, la primera
    dest = next((a for a in del_dia if a.get("destacada")), del_dia[0])
    resto = [a for a in del_dia if a is not dest]
    en_tarjeta = resto[:2]
    en_fila = resto[2:TOPE_DIA - 1]
    sobran = len(resto) - len(en_tarjeta) - len(en_fila)

    if i < DIAS_DESTACADOS:
        # dia reciente: tarjeta grande + tarjetas + filas
        cuerpo_d = card_lider(dest)
        if en_tarjeta:
            cuerpo_d += '<div class="grid">' + "".join(card(a, con_kick=True) for a in en_tarjeta) + "</div>"
        if en_fila:
            cuerpo_d += '<div class="rows">' + "".join(fila(a) for a in en_fila) + "</div>"
    elif i < DIAS_CON_TARJETA:
        # dia intermedio: todo en tarjetas normales, sin la grande
        cuerpo_d = ('<div class="grid">' + card(dest, con_kick=True)
                    + "".join(card(a, con_kick=True) for a in en_tarjeta) + "</div>")
        if en_fila:
            cuerpo_d += '<div class="rows">' + "".join(fila(a) for a in en_fila) + "</div>"
    else:
        # dia viejo: solo filas, que es lo que menos pesa
        cuerpo_d = ('<div class="rows">'
                    + "".join(fila(a) for a in [dest] + en_tarjeta + en_fila) + "</div>")
    if sobran > 0:
        cuerpo_d += (f'<a class="mas-dia" href="archivo.html#d-{f}">'
                     f'<span class="mm">&#8853;</span> ver las otras {sobran} notas del d\u00eda</a>')

    timeline_html += f"""
    <section class="dia" id="d-{f}">
      <div class="dia-head">
        <span class="dia-punto"></span>
        <h2>{escape(titulo_dia(f, f == _hoy))}</h2>
        <span class="dia-rule"></span>
        <span class="dia-count">{len(del_dia)} {'nota' if len(del_dia) == 1 else 'notas'}{' más' if subio_la_lider else ''}</span>
      </div>
      <div class="dia-body">{cuerpo_d}</div>
    </section>"""
    if i == 0:
        # despues de las noticias de hoy, no antes: primero el diario, despues
        # lo que el lector puede hacer con el
        timeline_html += pregunta_html

if not timeline_html:
    timeline_html = '<p class="empty small">La redacción publicará más notas en las próximas horas.</p>'
timeline_html = '<div class="timeline">' + timeline_html + '</div>'

lead_html = ""
sem_class = ""
if VARIANTE in ("lead", "compacta"):
    sem_class = ' class="sem-linea"'
if lead_portada is not None:
    lead_html = ('<div class="lead-dia">'
                 '<div class="lead-kick"><span class="lk-punto"></span>La nota del día'
                 '<span class="lk-fecha">' + escape(titulo_dia(_dias[0], _dias[0] == _hoy)) + '</span></div>'
                 + card_lider(lead_portada) + '</div>')

# ---- banda Modo Aprendizaje ---------------------------------------------
aprender_html = """
<section class="learn-band">
  <div class="lb-body">
    <div class="lb-kick">% Modo Aprendizaje · beta</div>
    <h2>Aprendé economía con la economía real de hoy</h2>
    <p>Rutas paso a paso, a tu ritmo: qué es la inflación, cómo cuidar tus ahorros, cuándo conviene el crédito, cómo dar el primer paso para invertir. Empezás sabiendo cero y terminás leyendo el diario de otra manera.</p>
  </div>
  <a class="lb-cta" href="aprender.html">Empezar una ruta &rarr;</a>
</section>"""

# ---- editor responsable --------------------------------------------------
_ed = portal.get("editor") or {}
if _ed.get("nombre"):
    _foto = f'<img class="ed-foto" src="{escape(_ed.get("foto",""))}" alt="{escape(_ed["nombre"])}">' if _ed.get("foto") else f'<span class="ed-foto ed-ini">{escape(_ed["nombre"][:1])}</span>'
    editor_html = f"""
      <div class="editor">
        {_foto}
        <div>
          <div class="ed-rol">Editor responsable</div>
          <div class="ed-nombre">{escape(_ed['nombre'])}</div>
          <div class="ed-bio">{escape(_ed.get('bio',''))} Aprueba cada nota antes de que se publique y responde por lo que acá se afirma.</div>
        </div>
      </div>"""
else:
    editor_html = """
      <div class="editor">
        <span class="ed-foto ed-ini">%</span>
        <div>
          <div class="ed-rol">Quién responde por esto</div>
          <div class="ed-nombre">Redacción de agentes de IA, edición humana</div>
          <div class="ed-bio">Ninguna nota se publica sola: una persona responsable revisa y aprueba cada publicación. <a href="como-trabajamos.html" style="color:var(--teal-deep)">Conocé el método &rarr;</a></div>
        </div>
      </div>"""

# cola panel
if borradores:
    filas = "\n".join(
        f"""<li><span class="q-sec">{escape(b.get('seccion',''))}</span>
        <span class="q-tit"><a href="cola/{escape(b['id'])}.html" style="color:inherit;text-decoration:none">{escape(b['titulo'])}</a></span>
        <a class="q-leer" href="cola/{escape(b['id'])}.html">Leer borrador &rarr;</a>
        <span class="q-badge">En revisión</span></li>""" for b in borradores)
    cola_html = f"""
    <section class="cola">
      <div class="cola-head"><span class="pulse"></span> Cola de revisión · {len(borradores)} borrador(es) esperando tu OK</div>
      <ul class="q-list">{filas}</ul>
      <p class="cola-foot">Los agentes ya investigaron y verificaron estas notas. Podés leer cada borrador completo desde acá; se publican recién cuando las aprobás.</p>
    </section>"""
else:
    cola_html = ""

# los chips del nav ahora apuntan a la pagina de cada seccion, no a un ancla
secciones_nav = "".join(
    f'<a class="sec-chip" href="{url_seccion(g["id"])}" style="--sc:{g["color"]}">{escape(g["label"])}</a>'
    for g in GRUPOS if any(grupo_de(a) == g["id"] for a in articulos))

# ---- hoja de estilo compartida por la portada y las paginas de seccion ----
# Se define una sola vez: si cambia el diseno, cambia en todas a la vez.
CSS = """<style>
  :root{
    --paper:#FAF8F4;--ink:#16130F;--ink-soft:#3C3833;--teal:#0E7C86;--teal-deep:#0A5C63;
    --amber:#C4701F;--red:#C0392B;--green:#2E8B6F;--muted:#6B6560;--faint:#8A847C;
    --grid:#E7E1D7;--rule:#DCD6CC;--card:#FFFFFF;--card-edge:#EAE4DA;
    --serif:"Source Serif 4",Georgia,serif;--sans:"Inter",system-ui,sans-serif;--mono:"IBM Plex Mono",monospace;
  }
  *{box-sizing:border-box} html{scroll-behavior:smooth}
  ::selection{background:var(--teal);color:#fff}
  body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);line-height:1.6;-webkit-font-smoothing:antialiased}
  .wrap{max-width:1080px;margin:0 auto;padding:0 24px}
  a{text-decoration:none;color:inherit}

  .masthead{border-bottom:2px solid var(--ink);position:sticky;top:0;background:var(--paper);z-index:70}
  .masthead .wrap{display:flex;align-items:center;justify-content:space-between;padding:10px 24px}
  .brand{font-family:var(--serif);font-weight:700;font-size:clamp(24px,2.6vw,31px);letter-spacing:-.025em;display:flex;align-items:center;gap:10px;color:var(--ink);cursor:pointer;font-optical-sizing:auto}
  .brand:hover .tri{color:var(--teal-deep)}
  .brand .tri{color:var(--teal);font-size:28px;transform:translateY(-2px)}
  .brand .tag{font-family:var(--mono);font-size:11px;color:var(--muted);letter-spacing:.14em;text-transform:uppercase;border-left:1px solid var(--rule);padding-left:10px;font-weight:500}
  .mh-right{text-align:right;font-family:var(--mono);font-size:11px;color:var(--muted);line-height:1.6}
  .mh-right b{color:var(--ink)}

  .concept{background:var(--ink);color:var(--paper)}
  .concept .wrap{display:flex;align-items:center;gap:18px;padding:11px 24px;flex-wrap:wrap;font-size:13px}
  .concept .k{font-family:var(--mono);font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:#4FC0A4;font-weight:600}
  .concept .item{color:#CFC9BF} .concept .item b{color:#fff;font-weight:600}
  .concept .sep{color:#3E3A34}

  /* top lo fija apilar() midiendo masthead + ticker. El default es 0 y no 96px
     a proposito: si el ticker no carga, la barra queda pegada al masthead en vez
     de dejar un hueco por el que se ve pasar el contenido. */
  .secnav{border-bottom:1px solid var(--rule);position:sticky;top:0;background:var(--paper);z-index:60;box-shadow:0 1px 0 rgba(22,19,15,.04)}
  .lema{border-bottom:1px solid var(--rule);background:var(--paper)}
  .lema .wrap{display:flex;align-items:baseline;gap:18px;flex-wrap:wrap;padding:16px 24px 15px}
  .lema .l1{font-family:var(--serif);font-size:clamp(19px,2.4vw,26px);font-weight:700;font-style:italic;color:var(--ink);letter-spacing:-.02em;font-optical-sizing:auto}
  .lema .l1 .fin{color:var(--teal)}
  .lema .l2{font-family:var(--mono);font-size:11px;color:var(--muted);letter-spacing:.04em}
  @media(max-width:600px){.lema .l1{font-size:18px}.lema .wrap{gap:6px;padding:12px 24px}}
  .secnav .wrap{display:flex;gap:8px;padding:12px 24px;flex-wrap:wrap}
  .sec-chip{font-family:var(--mono);font-size:11px;letter-spacing:.08em;color:var(--sc);background:var(--paper);border:1px solid var(--card-edge);padding:6px 13px;border-radius:999px;font-weight:600;cursor:pointer;transition:.15s}
  .sec-chip:hover{border-color:var(--sc)}
  .sec-chip.active{background:var(--sc);color:#fff;border-color:var(--sc)}
  .lead.is-hidden,.card.is-hidden{display:none}

  main{padding:clamp(28px,4vw,44px) 0 20px}
  .nav-extra{font-family:var(--mono);font-size:12px;color:var(--teal-deep);text-decoration:none;white-space:nowrap;font-weight:600;padding:6px 4px}
  .nav-extra:first-of-type{margin-left:auto}
  .nav-extra:hover{color:var(--teal)}
  .learn-link{font-family:var(--mono);font-size:12px;color:var(--teal-deep);text-decoration:none;display:flex;align-items:center;gap:7px;white-space:nowrap;font-weight:600}
  .learn-link b{background:var(--amber);color:#fff;font-size:9px;letter-spacing:.06em;text-transform:uppercase;padding:2px 6px;border-radius:999px;font-weight:600}
  .learn-link:hover{color:var(--teal)}
  @media(max-width:640px){
    .masthead .wrap{padding:8px 16px}
    .brand{white-space:nowrap}
    .brand .tag{display:none}
    .mh-right{display:none}
    .secnav .wrap{flex-wrap:nowrap;overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none;padding:10px 16px}
    .secnav .wrap::-webkit-scrollbar{display:none}
    .sec-chip,.nav-extra,.learn-link{flex:0 0 auto}
  }
  .empty{color:var(--muted);font-family:var(--mono);font-size:14px;padding:40px 0} .empty.small{padding:14px}

  .lead{display:grid;grid-template-columns:300px 1fr;gap:30px;border-bottom:1px solid var(--rule);padding-bottom:30px;margin-bottom:30px;align-items:center}
  .lead-num{background:var(--ink);border-radius:16px;padding:32px 26px;display:flex;flex-direction:column;justify-content:center;min-height:210px}
  .lead-num .ln-big{font-family:var(--mono);font-weight:600;font-size:64px;line-height:1;letter-spacing:-.045em;color:#fff;font-variant-numeric:tabular-nums}
  .lead-num .ln-lab{font-size:13px;color:#B9B3A9;margin-top:12px;line-height:1.45}
  .lead-num{border-top:4px solid var(--sc)}
  .lead-body .kick,.card .kick{font-family:var(--mono);font-size:12px;letter-spacing:.12em;text-transform:uppercase;font-weight:600;margin-bottom:12px}
  .lead-body .kick span{color:var(--faint)}
  .lead-body h2{font-family:var(--serif);font-weight:700;font-size:clamp(30px,4.4vw,50px);line-height:1.05;letter-spacing:-.028em;margin:0 0 16px;text-wrap:balance;font-optical-sizing:auto}
  .lead-body p{font-size:clamp(15px,1.5vw,18px);color:var(--ink-soft);margin:0 0 16px;max-width:58ch;text-wrap:pretty;line-height:1.62}
  .lead:hover h2{color:var(--teal-deep)}

  .grid{display:grid;grid-template-columns:repeat(3,1fr);gap:22px}
  .grid-2{grid-template-columns:repeat(2,1fr)}
  .grid-2 .card h3{font-size:19px}
  .rail-head,.sec-head{display:flex;align-items:center;gap:14px;margin:clamp(36px,5vw,54px) 0 20px}
  .rail-head .rh-txt{font-family:var(--mono);font-size:12px;letter-spacing:.14em;text-transform:uppercase;font-weight:600;color:var(--muted)}
  .rh-rule{flex:1;height:1px;background:var(--rule)}
  .sec-head h2{font-family:var(--mono);font-size:13px;letter-spacing:.14em;text-transform:uppercase;font-weight:600;margin:0}
  .sec-count{font-family:var(--mono);font-size:11px;color:var(--faint)}
  .sec-group,.dia,.dia-bloque,.mes-sep{scroll-margin-top:calc(var(--stack,150px) + 8px)}

  .learn-band{background:linear-gradient(120deg,#16130F,#0A5C63);border-radius:16px;padding:32px 34px;margin:40px 0 6px;display:flex;align-items:center;gap:28px;flex-wrap:wrap}
  .learn-band .lb-kick{font-family:var(--mono);font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:#E8833A;font-weight:600;margin-bottom:8px}
  .learn-band h2{font-family:var(--serif);font-size:27px;font-weight:700;color:#fff;margin:0 0 8px;line-height:1.2}
  .learn-band p{font-size:14px;color:#CDE4E1;margin:0;max-width:58ch;line-height:1.55}
  .learn-band .lb-body{flex:1 1 380px}
  .lb-cta{font-family:var(--sans);font-size:15px;font-weight:600;background:#fff;color:var(--ink);padding:13px 24px;border-radius:10px;white-space:nowrap;transition:.15s}
  .lb-cta:hover{background:#F3D9A8}

  .editor{display:flex;gap:16px;align-items:flex-start;margin-top:22px;padding-top:20px;border-top:1px dashed var(--rule);max-width:520px}
  .ed-foto{width:52px;height:52px;border-radius:50%;object-fit:cover;flex:0 0 auto}
  .ed-ini{background:var(--teal);color:#fff;display:flex;align-items:center;justify-content:center;font-family:var(--serif);font-size:24px;font-weight:700}
  .ed-rol{font-family:var(--mono);font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--amber);font-weight:600}
  .ed-nombre{font-family:var(--serif);font-size:17px;font-weight:700;margin:2px 0}
  .ed-bio{font-size:13px;color:var(--muted);line-height:1.55}
  .card{background:var(--card);border:1px solid var(--card-edge);border-radius:14px;padding:20px;display:flex;flex-direction:column;transition:.15s}
  .card:hover{transform:translateY(-2px);border-color:var(--sc)}
  .card h3{font-family:var(--serif);font-weight:600;font-size:19px;line-height:1.26;letter-spacing:-.012em;margin:0 0 14px;flex:1;color:var(--ink);text-wrap:balance}
  .card-num{font-family:var(--mono);font-size:12px;color:var(--muted);border-left:3px solid var(--sc);padding-left:10px;margin-bottom:14px;line-height:1.45;font-variant-numeric:tabular-nums}
  .card-num b{color:var(--ink);font-size:16px}
  .grid-2 .card h3{font-size:21px}
  .sec-sub{font-family:var(--mono);font-size:11px;color:var(--faint);letter-spacing:.02em}

  .lider{display:grid;grid-template-columns:1fr 250px;gap:26px;background:var(--card);border:1px solid var(--card-edge);border-left:4px solid var(--sc);border-radius:14px;padding:24px 26px;margin-bottom:20px;align-items:center;transition:.15s}
  .lider:hover{border-color:var(--sc);transform:translateY(-2px)}
  .lider h3{font-family:var(--serif);font-weight:700;font-size:clamp(21px,2.6vw,29px);line-height:1.12;letter-spacing:-.02em;margin:0 0 10px;color:var(--ink);text-wrap:balance;font-optical-sizing:auto}
  .lider p{font-size:14px;color:var(--ink-soft);margin:0 0 12px;line-height:1.6;text-wrap:pretty;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
  .l-num{border-left:1px solid var(--grid);padding-left:24px}
  .l-num .ln{font-family:var(--mono);font-weight:600;line-height:1;letter-spacing:-.02em;color:var(--sc);display:block}
  .l-num .ll{font-size:12px;color:var(--muted);line-height:1.4;display:block;margin-top:8px}
  .rows{display:flex;flex-direction:column;margin-top:14px}
  .row{display:flex;align-items:baseline;gap:14px;padding:10px 4px;border-top:1px dashed var(--rule);transition:.1s}
  .row:hover{background:var(--card)}
  .r-num{font-family:var(--mono);font-size:14px;font-weight:600;flex:0 0 110px;text-align:right;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .r-tit{font-family:var(--serif);font-size:15px;font-weight:600;color:var(--ink-soft);flex:1;line-height:1.35}
  .row:hover .r-tit{color:var(--teal-deep)}
  .r-fecha{font-family:var(--mono);font-size:11px;color:var(--faint);white-space:nowrap}
  .vermas{margin-top:6px}
  .vermas summary{list-style:none;cursor:pointer;font-family:var(--mono);font-size:12px;font-weight:600;color:var(--muted);padding:10px 4px;display:flex;align-items:center;gap:8px}
  .vermas summary::-webkit-details-marker{display:none}
  .vermas summary:hover{color:var(--teal-deep)}
  .vermas .plus{color:var(--teal);font-size:16px;transition:.2s}
  .vermas[open] .plus{transform:rotate(45deg)}
  @media(max-width:700px){.lider{grid-template-columns:1fr}.l-num{border-left:none;border-top:1px solid var(--grid);padding:14px 0 0}.r-num{flex-basis:84px;font-size:12px}.r-fecha{display:none}}

  .meta{display:flex;align-items:center;gap:10px;font-family:var(--mono);font-size:11px;color:var(--muted);flex-wrap:wrap;font-variant-numeric:tabular-nums}
  .meta .dot{width:3px;height:3px;border-radius:50%;background:var(--faint)}
  .verif{font-weight:600} .verif.ok{color:var(--green)} .verif.pend{color:var(--amber)}

  .cola{background:#F3EFE7;border:1px solid var(--card-edge);border-left:3px solid var(--amber);border-radius:12px;padding:20px 22px;margin:34px 0 10px}
  .cola-head{font-family:var(--mono);font-size:13px;font-weight:600;color:var(--ink);display:flex;align-items:center;gap:9px;margin-bottom:14px}
  .pulse{width:9px;height:9px;border-radius:50%;background:var(--amber);box-shadow:0 0 0 0 rgba(196,112,31,.5);animation:p 2s infinite}
  @keyframes p{70%{box-shadow:0 0 0 8px rgba(196,112,31,0)}100%{box-shadow:0 0 0 0 rgba(196,112,31,0)}}
  .q-list{list-style:none;margin:0;padding:0}
  .q-list li{display:flex;align-items:center;gap:12px;padding:11px 0;border-top:1px dashed var(--rule);font-size:15px}
  .q-sec{font-family:var(--mono);font-size:10px;letter-spacing:.08em;color:var(--amber);font-weight:600;flex:0 0 auto}
  .q-tit{flex:1;color:var(--ink-soft)}
  .q-badge{font-family:var(--mono);font-size:10px;background:var(--amber);color:#fff;padding:3px 9px;border-radius:999px;font-weight:600}
  .q-leer{font-family:var(--mono);font-size:11px;color:var(--teal-deep);font-weight:600;white-space:nowrap;border-bottom:1px solid var(--grid)}
  .q-leer:hover{color:var(--teal)}
  .cola-foot{font-size:12px;color:var(--muted);margin:12px 0 0}

  footer{border-top:2px solid var(--ink);margin-top:44px;padding:26px 0 60px}
  footer .wrap{display:flex;justify-content:space-between;gap:24px;flex-wrap:wrap}
  .f-brand{font-family:var(--serif);font-weight:700;font-size:20px} .f-brand .tri{color:var(--teal)}
  .f-desc{font-size:13px;color:var(--muted);max-width:480px;margin-top:6px;line-height:1.55}
  .f-meta{font-family:var(--mono);font-size:11px;color:var(--faint);text-align:right;line-height:1.8}

  @media(max-width:820px){
    .grid{grid-template-columns:1fr 1fr} .lead{grid-template-columns:1fr} .lead-num{min-height:150px}
    .lead-body h2{font-size:27px} .brand{font-size:28px}
  }
  @media(max-width:560px){ .grid{grid-template-columns:1fr} .concept .wrap{gap:8px 14px} }
  .vertodas{display:inline-flex;align-items:center;gap:8px;margin-top:14px;font-family:var(--mono);
    font-size:13px;color:var(--teal-deep);text-decoration:none;border:1px solid var(--rule);
    border-radius:999px;padding:9px 16px;transition:.15s;background:var(--card)}
  .vertodas:hover{border-color:var(--teal);background:#fff}
  .vertodas .fl{font-size:15px}
  .pager{display:flex;gap:8px;align-items:center;justify-content:center;margin:34px 0 10px;flex-wrap:wrap}
  .pager a,.pager span{font-family:var(--mono);font-size:13px;padding:8px 14px;border-radius:8px;
    border:1px solid var(--rule);text-decoration:none;color:var(--ink-soft);background:var(--card)}
  .pager a:hover{border-color:var(--teal);color:var(--teal-deep)}
  .pager .actual{background:var(--ink);color:var(--paper);border-color:var(--ink)}
  .pager .off{opacity:.4}
  .sec-hero{border-bottom:2px solid var(--ink);padding:26px 0 18px;margin-bottom:26px}
  .sec-hero h1{font-family:var(--serif);font-size:38px;font-weight:700;margin:0 0 6px;letter-spacing:-.015em}
  .sec-hero p{font-size:15px;color:var(--muted);margin:0}
  .sec-hero .volver{font-family:var(--mono);font-size:12px;color:var(--teal-deep);text-decoration:none;
    display:inline-block;margin-bottom:12px}
  .mes-sep{display:flex;align-items:center;gap:12px;margin:34px 0 20px -26px;padding-left:26px}
  .mes-sep h2{font-family:var(--serif);font-size:22px;font-weight:700;margin:0;text-transform:capitalize}
  .dia-bloque{margin-bottom:26px}
  /* ---------- linea de tiempo por dia ---------- */
  .timeline{position:relative;padding-left:26px;margin-top:26px}
  .timeline:before{content:"";position:absolute;left:5px;top:8px;bottom:8px;width:2px;
    background:linear-gradient(180deg,var(--ink) 0%,var(--rule) 92%,transparent 100%)}
  .dia{position:relative;margin-bottom:38px}
  .dia-head{display:flex;align-items:center;gap:12px;margin:0 0 16px -26px;padding-left:26px;position:relative}
  .dia-punto{position:absolute;left:0;top:50%;transform:translateY(-50%);width:12px;height:12px;
    border-radius:50%;background:var(--ink);box-shadow:0 0 0 4px var(--paper)}
  .dia:first-child .dia-punto{background:var(--amber);box-shadow:0 0 0 4px var(--paper),0 0 0 7px rgba(196,112,31,.25)}
  .dia-head h2{font-family:var(--mono);font-size:13px;font-weight:600;letter-spacing:.06em;
    text-transform:uppercase;color:var(--ink);margin:0;white-space:nowrap}
  .dia:first-child .dia-head h2{color:var(--amber)}
  .dia-rule{flex:1;height:1px;background:var(--rule)}
  .dia-count{font-family:var(--mono);font-size:11px;color:var(--faint);white-space:nowrap}
  .dia-body>*+*{margin-top:14px}
  .mas-dia{display:inline-flex;align-items:center;gap:8px;font-family:var(--mono);font-size:12.5px;
    color:var(--muted);text-decoration:none;border:1px dashed var(--rule);border-radius:999px;
    padding:8px 15px;transition:.15s}
  .mas-dia:hover{border-color:var(--teal);color:var(--teal-deep);border-style:solid}
  .mas-dia .mm{font-size:14px}
  @media(max-width:600px){
    .timeline{padding-left:18px}
    .timeline:before{left:3px}
    .dia-head{margin-left:-18px;padding-left:18px;gap:8px}
    .dia-head h2{font-size:11.5px;white-space:normal}
    .dia-punto{width:9px;height:9px}
  }
  /* ---------- variante: la nota del dia arriba de la linea ---------- */
  .lead-dia{margin:0 0 22px}
  .lead-kick{display:flex;align-items:center;gap:9px;font-family:var(--mono);font-size:11px;
    font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--amber);margin:0 0 11px}
  .lead-kick .lk-punto{width:8px;height:8px;border-radius:50%;background:var(--amber);flex:none}
  .lead-kick .lk-fecha{color:var(--faint);font-weight:400;letter-spacing:.04em}
  .lead-kick .lk-fecha:before{content:"·";margin-right:9px}
  .lead-dia .lider{border-left-width:5px}
  .lead-dia .lider h3{font-size:clamp(25px,3.6vw,36px);line-height:1.15}
  .lead-dia .lider p{font-size:16px}
  /* ---------- variante: semaforo comprimido a una franja ----------
     Gana por especificidad a los estilos que inyecta ticker.js, que van
     en un <style> agregado despues de este; por eso el prefijo .sem-linea. */
  .sem-linea{margin:0 0 20px}
  .sem-linea .ci-sem{display:grid;grid-template-columns:repeat(5,1fr);gap:0;margin:0;
    background:var(--card);border:1px solid var(--card-edge);border-radius:10px;overflow:hidden}
  .sem-linea .ci-sem-t{min-width:0;background:transparent;border:0;
    border-right:1px solid var(--grid);border-radius:0;padding:8px 13px}
  .sem-linea .ci-sem-t:last-child{border-right:0}
  .sem-linea .ci-sem-t:hover{transform:none;background:var(--paper);border-color:var(--grid)}
  .sem-linea .ci-sem-t .k{display:block;margin:0 0 1px;font-size:9px}
  .sem-linea .ci-sem-t .v{font-size:15px}
  .sem-linea .ci-sem-t .d{display:inline;margin:0 0 0 5px;font-size:10px;font-weight:500;
    white-space:nowrap}
  .sem-linea .ci-sem-cap{margin:7px 0 0;font-size:10px}
  @media(max-width:820px){
    .sem-linea .ci-sem{display:grid;grid-template-columns:repeat(2,1fr)}
    .sem-linea .ci-sem-t{border-bottom:1px solid var(--grid)}
  }
  /* ---------- la pregunta del dia, en la portada ---------- */
  .pregunta-band{background:var(--card);border:1px solid var(--card-edge);border-radius:14px;
    padding:20px 22px;margin:0 0 38px}
  .pregunta-band[hidden]{display:none}
  .pb-head{display:flex;align-items:center;gap:11px;margin-bottom:13px}
  .pb-kick{font-family:var(--mono);font-size:11px;font-weight:600;letter-spacing:.1em;
    text-transform:uppercase;color:var(--teal-deep);white-space:nowrap}
  .pb-fecha{font-family:var(--mono);font-size:10.5px;color:var(--faint);white-space:nowrap}
  .pb-fecha.vieja{color:var(--amber)}
  .pb-rule{flex:1;height:1px;background:var(--grid)}
  .pb-racha{font-family:var(--mono);font-size:11px;color:var(--amber);white-space:nowrap}
  .pb-q{font-family:var(--serif);font-size:18px;font-weight:600;line-height:1.35;
    margin:0 0 15px;color:var(--ink);text-wrap:balance}
  .pb-ops{display:flex;flex-direction:column;gap:9px}
  .pb-ops button{font-family:var(--sans);font-size:14px;line-height:1.45;text-align:left;
    background:var(--paper);border:1.5px solid var(--rule);border-radius:10px;padding:11px 14px;
    cursor:pointer;color:var(--ink-soft);transition:.15s}
  .pb-ops button:hover:enabled{border-color:var(--teal)}
  .pb-ops button:focus-visible{outline:2px solid var(--teal);outline-offset:2px}
  .pb-ops button:disabled{cursor:default}
  .pb-ops button.ok{background:#E7F4EE;border-color:var(--green);color:#1E6B4F;font-weight:600}
  .pb-ops button.mal{background:#FBEAE6;border-color:var(--red);color:#96291C}
  .pb-res{display:none;margin-top:15px}
  .pb-res.on{display:block}
  .pb-ver{font-family:var(--serif);font-size:17px;font-weight:700;margin-bottom:7px}
  .pb-ver.ok{color:var(--green)} .pb-ver.mal{color:var(--red)}
  .pb-expl{background:#F3EFE7;border-left:3px solid var(--teal);border-radius:9px;
    padding:13px 15px;font-size:14px;color:var(--ink-soft);line-height:1.55;margin:0}
  .pb-links{display:flex;gap:9px;flex-wrap:wrap;margin-top:12px}
  .pb-links a{font-family:var(--mono);font-size:11.5px;font-weight:600;text-decoration:none;
    color:var(--teal-deep);border:1px solid var(--rule);border-radius:999px;padding:7px 14px}
  .pb-links a:hover{border-color:var(--teal)}
  .pb-links a[hidden]{display:none}
  @media(max-width:600px){
    .pregunta-band{padding:16px 15px}
    .pb-q{font-size:16.5px}
    .pb-head{flex-wrap:wrap;gap:7px} .pb-rule{display:none}
  }
</style>"""

HTML = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="google-site-verification" content="EkVYODJUjsh6bYYbnDOTKdg_7uFxKj2wG-MCxCOwfhM" />
<title>{escape(portal['nombre'])} — {escape(portal['tagline'])}</title>
<meta name="description" content="{escape(portal['descripcion'])}">
<link rel="icon" type="image/svg+xml" href="assets/favicon.svg">
<link rel="alternate" type="application/rss+xml" title="Con Interés" href="/feed.xml">
<link rel="canonical" href="{SITE}/">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{escape(portal['nombre'])}">
<meta property="og:title" content="{escape(portal['nombre'])} — {escape(portal['tagline'])}">
<meta property="og:description" content="{escape(portal['descripcion'])}">
<meta property="og:url" content="{SITE}/">
<meta property="og:image" content="{SITE}/assets/og-delta.png">
<meta property="og:locale" content="es_AR">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{escape(portal['nombre'])} — {escape(portal['tagline'])}">
<meta name="twitter:description" content="{escape(portal['descripcion'])}">
<meta name="twitter:image" content="{SITE}/assets/og-delta.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;0,8..60,700&family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<script defer src="assets/ticker.js?v=4"></script>
<script defer src="assets/metrics.js?v=1"></script>
<script defer src="assets/pregunta.js?v=1"></script>
<script defer src="assets/portada-pregunta.js?v=1"></script>
{CSS}
</head>
<body>

<header class="masthead" id="inicio">
  <div class="wrap">
    <a class="brand" href="#inicio" aria-label="Volver al inicio de la portada"><span class="tri">%</span>{escape(portal['nombre'])}<span class="tag">Diario de economía en datos</span></a>
    <div class="mh-right">
      <div>{FECHA_MASTHEAD}</div>
    </div>
  </div>
</header>

<nav class="secnav"><div class="wrap">{secciones_nav}<a class="nav-extra" href="pregunta.html">? La pregunta</a><a class="nav-extra" href="hoy.html">&#10003; El cierre</a><a class="nav-extra" href="herramientas.html">&#8983; Herramientas</a><a class="nav-extra" href="archivo.html">&#9776; Archivo</a><a class="learn-link" href="aprender.html">% Modo Aprendizaje <b>beta</b> →</a></div></nav>

<div class="lema"><div class="wrap"><span class="l1">Entender no debería costarte nada<span class="fin">.</span></span><span class="l2">Datos verificados, explicados sin jerga, sin pedirte nada a cambio.</span></div></div>

<main class="wrap">
  {lead_html}
  <div id="ci-semaforo"{sem_class}></div>
  {timeline_html}
  {aprender_html}
  {cola_html}
</main>

<footer>
  <div class="wrap">
    <div>
      <div class="f-brand"><span class="tri">%</span> {escape(portal['nombre'])}</div>
      <div class="f-desc">{escape(portal['descripcion'])}</div>
      <div style="margin-top:10px"><a href="como-trabajamos.html" style="font-family:var(--mono);font-size:12px;color:var(--teal-deep);text-decoration:none;border-bottom:1px solid var(--grid)">% Cómo trabajamos — método, IA y ética →</a> · <a href="aprender.html" style="font-family:var(--mono);font-size:12px;color:var(--teal-deep);text-decoration:none;border-bottom:1px solid var(--grid)">Modo Aprendizaje →</a> · <a href="feed.xml" style="font-family:var(--mono);font-size:12px;color:var(--teal-deep);text-decoration:none;border-bottom:1px solid var(--grid)">RSS →</a></div>
      <div style="margin-top:8px;font-family:var(--mono);font-size:11px;color:var(--faint)"><a href="suscribirse.html" style="color:var(--teal-deep);text-decoration:none;font-weight:600">Suscribite por mail</a> &middot; <a href="legal.html" style="color:var(--muted);text-decoration:none">Aviso legal y correcciones</a> · <a href="privacidad.html" style="color:var(--muted);text-decoration:none">Política de privacidad</a> · El contenido de este sitio es informativo y educativo; no constituye asesoramiento financiero.</div>
      {editor_html}
    </div>
  </div>
</footer>

<script>
(function(){{
  // apila masthead + ticker + secciones como encabezado fijo, midiendo alturas reales
  var mast=document.querySelector('.masthead'), sn=document.querySelector('.secnav');
  function apilar(){{
    var tk=document.getElementById('ci-ticker');
    var h1=mast?mast.offsetHeight:0;
    var h2=tk?tk.offsetHeight:0;
    if(tk){{ tk.style.position='sticky'; tk.style.top=h1+'px'; tk.style.zIndex=65; }}
    if(sn) sn.style.top=(h1+h2)+'px';
    document.documentElement.style.setProperty('--stack',(h1+h2+(sn?sn.offsetHeight:0))+'px');
  }}
  apilar();
  window.addEventListener('resize', apilar);
  // el ticker se renderiza async: reintentar unos segundos hasta que aparezca
  var t=0, iv=setInterval(function(){{ apilar(); if(++t>10) clearInterval(iv); }}, 500);

  // clic en la marca = volver al inicio de la portada
  var brand=document.querySelector('.brand');
  if(brand) brand.addEventListener('click', function(e){{
    e.preventDefault();
    window.scrollTo({{top:0, behavior:'smooth'}});
  }});

  // resalta en la barra fija la sección visible mientras se scrollea
  var chips=[].slice.call(document.querySelectorAll('.sec-chip[href^="#"]'));
  var grupos=chips.map(function(c){{ return document.getElementById(c.getAttribute('href').slice(1)); }});
  function marcar(){{
    var actual=-1;
    for(var i=0;i<grupos.length;i++){{
      if(grupos[i] && grupos[i].getBoundingClientRect().top<140) actual=i;
    }}
    chips.forEach(function(c,i){{ c.classList.toggle('active', i===actual); }});
  }}
  window.addEventListener('scroll', marcar, {{passive:true}});
  marcar();
}})();
</script>

</body>
</html>"""

out = os.path.join(ROOT, SALIDA_PORTADA)
with open(out, "w", encoding="utf-8") as f:
    f.write(HTML)


# ---- generacion de las paginas de seccion -------------------------------
# Una pagina por grupo, paginada de a POR_PAGINA. La pagina 1 es
# seccion-<id>.html y las siguientes seccion-<id>-2.html, -3.html...
# Reutilizan el CSS y el chrome de la portada; las rutas relativas valen
# igual porque viven en la raiz.
paginas_seccion = []

def _pager(gid, pag, total):
    if total <= 1:
        return ""
    piezas = []
    piezas.append(f'<a href="{url_seccion(gid, pag-1)}">&larr; Anterior</a>'
                  if pag > 1 else '<span class="off">&larr; Anterior</span>')
    for n in range(1, total + 1):
        piezas.append(f'<span class="actual">{n}</span>' if n == pag
                      else f'<a href="{url_seccion(gid, n)}">{n}</a>')
    piezas.append(f'<a href="{url_seccion(gid, pag+1)}">Siguiente &rarr;</a>'
                  if pag < total else '<span class="off">Siguiente &rarr;</span>')
    return '<nav class="pager">' + "".join(piezas) + "</nav>"

for g in GRUPOS:
    notas_g = [a for a in articulos if grupo_de(a) == g["id"]]
    if not notas_g:
        continue
    total_pags = (len(notas_g) + POR_PAGINA - 1) // POR_PAGINA
    for pag in range(1, total_pags + 1):
        tanda = notas_g[(pag - 1) * POR_PAGINA: pag * POR_PAGINA]
        # la primera de la primera pagina va como lider; el resto, en grilla
        if pag == 1:
            cuerpo_s = card_lider(tanda[0])
            if tanda[1:]:
                cuerpo_s += '<div class="grid">' + "".join(card(a) for a in tanda[1:]) + "</div>"
        else:
            cuerpo_s = '<div class="grid">' + "".join(card(a) for a in tanda) + "</div>"

        desc_s = f"{g['label']}: {g['sub']}. {len(notas_g)} notas verificadas de {portal['nombre']}."
        titulo_s = f"{g['label']} — {portal['nombre']}"
        if pag > 1:
            titulo_s = f"{g['label']} (página {pag}) — {portal['nombre']}"
        canon = f"{SITE}/{url_seccion(g['id'], pag)}"

        rel = ""
        if pag > 1:
            rel += f'<link rel="prev" href="{SITE}/{url_seccion(g["id"], pag-1)}">\n'
        if pag < total_pags:
            rel += f'<link rel="next" href="{SITE}/{url_seccion(g["id"], pag+1)}">\n'

        PAG = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape(titulo_s)}</title>
<meta name="description" content="{escape(desc_s)}">
<link rel="icon" type="image/svg+xml" href="assets/favicon.svg">
<link rel="alternate" type="application/rss+xml" title="Con Interés" href="/feed.xml">
<link rel="canonical" href="{canon}">
{rel}<meta property="og:type" content="website">
<meta property="og:site_name" content="{escape(portal['nombre'])}">
<meta property="og:title" content="{escape(titulo_s)}">
<meta property="og:description" content="{escape(desc_s)}">
<meta property="og:url" content="{canon}">
<meta property="og:locale" content="es_AR">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;0,8..60,700;1,8..60,400&family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
{CSS}
</head>
<body>

<header class="masthead">
  <div class="wrap">
    <a class="brand" href="index.html"><span class="tri">%</span>{escape(portal['nombre'])}<span class="tag">Diario de economía en datos</span></a>
    <div class="mh-right"><div>{FECHA_MASTHEAD}</div></div>
  </div>
</header>

<nav class="secnav"><div class="wrap">{secciones_nav}<a class="nav-extra" href="pregunta.html">? La pregunta</a><a class="nav-extra" href="hoy.html">&#10003; El cierre</a><a class="nav-extra" href="herramientas.html">&#8983; Herramientas</a><a class="nav-extra" href="archivo.html">&#9776; Archivo</a><a class="learn-link" href="aprender.html">% Modo Aprendizaje <b>beta</b> &rarr;</a></div></nav>

<main class="wrap">
  <div class="sec-hero">
    <a class="volver" href="index.html">&larr; Portada</a>
    <h1 style="color:{g['color']}">{escape(g['label'])}</h1>
    <p>{escape(g['sub'])} &middot; {len(notas_g)} notas{'' if total_pags == 1 else f' &middot; página {pag} de {total_pags}'}</p>
  </div>
  {cuerpo_s}
  {_pager(g['id'], pag, total_pags)}
</main>

<footer>
  <div class="wrap">
    <div>
      <div class="f-brand"><span class="tri">%</span> {escape(portal['nombre'])}</div>
      <div class="f-desc">{escape(portal['descripcion'])}</div>
      <div style="margin-top:10px"><a href="como-trabajamos.html" style="font-family:var(--mono);font-size:12px;color:var(--teal-deep);text-decoration:none;border-bottom:1px solid var(--grid)">% Cómo trabajamos &rarr;</a> &middot; <a href="aprender.html" style="font-family:var(--mono);font-size:12px;color:var(--teal-deep);text-decoration:none;border-bottom:1px solid var(--grid)">Modo Aprendizaje &rarr;</a> &middot; <a href="feed.xml" style="font-family:var(--mono);font-size:12px;color:var(--teal-deep);text-decoration:none;border-bottom:1px solid var(--grid)">RSS &rarr;</a></div>
      <div style="margin-top:8px;font-family:var(--mono);font-size:11px;color:var(--faint)"><a href="suscribirse.html" style="color:var(--teal-deep);text-decoration:none;font-weight:600">Suscribite por mail</a> &middot; <a href="legal.html" style="color:var(--muted);text-decoration:none">Aviso legal y correcciones</a> &middot; <a href="privacidad.html" style="color:var(--muted);text-decoration:none">Política de privacidad</a> &middot; El contenido de este sitio es informativo y educativo; no constituye asesoramiento financiero.</div>
    </div>
  </div>
</footer>

<script>
(function(){{
  // 1) Apila masthead + ticker + barra de secciones como encabezado fijo,
  //    midiendo alturas reales. Sin esto la barra de secciones queda flotando
  //    sobre el contenido, porque el ticker se inyecta de forma asincrona.
  var mast=document.querySelector('.masthead'), sn=document.querySelector('.secnav');
  function apilar(){{
    var tk=document.getElementById('ci-ticker');
    var h1=mast?mast.offsetHeight:0;
    var h2=tk?tk.offsetHeight:0;
    if(tk){{ tk.style.position='sticky'; tk.style.top=h1+'px'; tk.style.zIndex=65; }}
    if(sn) sn.style.top=(h1+h2)+'px';
    document.documentElement.style.setProperty('--stack',(h1+h2+(sn?sn.offsetHeight:0))+'px');
  }}
  // 2) El mismo desplazamiento desfasa el salto al ancla que hace el
  //    navegador, asi que se rehace cuando la pagina termina de acomodarse.
  function irAlAncla(){{
    if(!location.hash) return;
    var el=document.getElementById(location.hash.slice(1));
    if(el) el.scrollIntoView({{block:"start"}});
  }}
  // Mientras el ticker termina de cargar el contenido se sigue moviendo, asi
  // que hay que rehacer el salto varias veces. Pero si el lector ya scrolleo,
  // se deja de corregir: nada peor que la pagina saltando sola.
  var libre = true;
  ['wheel','touchmove','keydown'].forEach(function(ev){{
    window.addEventListener(ev, function(){{ libre = false; }}, {{passive:true}});
  }});
  apilar();
  window.addEventListener('resize', apilar);
  window.addEventListener('load', function(){{ apilar(); if(libre) irAlAncla(); }});
  var t=0, iv=setInterval(function(){{
    apilar();
    if(libre) irAlAncla();
    if(++t>12) clearInterval(iv);
  }}, 300);
  window.addEventListener('hashchange', function(){{ libre = true; irAlAncla(); }});
}})();
</script>
<!-- CI-WIDGETS --><script defer src="assets/ticker.js?v=4"></script>
<script defer src="assets/metrics.js?v=1"></script>
</body>
</html>"""
        ruta = os.path.join(ROOT, url_seccion(g["id"], pag))
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(PAG)
        paginas_seccion.append(url_seccion(g["id"], pag))


# ---- archivo.html — todas las notas, por mes ---------------------------
# Una sola pagina, cronologica, sin paginar: es el indice completo del diario.
# Usa filas compactas, que pesan poco: 97 notas ocupan menos que una portada.
MESES_LARGO = ["enero","febrero","marzo","abril","mayo","junio",
               "julio","agosto","septiembre","octubre","noviembre","diciembre"]

# se agrupa por DIA, con un ancla id="d-AAAA-MM-DD" para que la portada
# pueda enlazar "ver las otras N notas del dia". El mes queda como separador.
_bloques = ""
_mes_actual = None
for f in sorted(_por_dia, reverse=True):
    y, m, _d = (int(x) for x in f.split("-"))
    if (y, m) != _mes_actual:
        _mes_actual = (y, m)
        _n_mes = sum(1 for a in articulos if a["fecha"].startswith(f"{y}-{m:02d}"))
        _bloques += f"""
    <div class="mes-sep"><h2>{MESES_LARGO[m-1]} de {y}</h2><span class="rh-rule"></span><span class="sec-count">{_n_mes} notas</span></div>"""
    notas_d = _por_dia[f]
    _bloques += f"""
    <section class="dia-bloque" id="d-{f}">
      <div class="dia-head"><span class="dia-punto"></span><h2>{escape(titulo_dia(f))}</h2><span class="dia-rule"></span><span class="dia-count">{len(notas_d)} {'nota' if len(notas_d)==1 else 'notas'}</span></div>
      <div class="rows">{"".join(fila(a) for a in notas_d)}</div>
    </section>"""

_desc_arch = f"Todas las notas de {portal['nombre']}, mes por mes: {len(articulos)} datos verificados de la economia argentina."
ARCHIVO = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Archivo — {escape(portal['nombre'])}</title>
<meta name="description" content="{escape(_desc_arch)}">
<link rel="icon" type="image/svg+xml" href="assets/favicon.svg">
<link rel="alternate" type="application/rss+xml" title="Con Interés" href="/feed.xml">
<link rel="canonical" href="{SITE}/archivo.html">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{escape(portal['nombre'])}">
<meta property="og:title" content="Archivo — {escape(portal['nombre'])}">
<meta property="og:description" content="{escape(_desc_arch)}">
<meta property="og:url" content="{SITE}/archivo.html">
<meta property="og:locale" content="es_AR">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;0,8..60,700;1,8..60,400&family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
{CSS}
</head>
<body>

<header class="masthead">
  <div class="wrap">
    <a class="brand" href="index.html"><span class="tri">%</span>{escape(portal['nombre'])}<span class="tag">Diario de economía en datos</span></a>
    <div class="mh-right"><div>{FECHA_MASTHEAD}</div></div>
  </div>
</header>

<nav class="secnav"><div class="wrap">{secciones_nav}<a class="nav-extra" href="pregunta.html">? La pregunta</a><a class="nav-extra" href="hoy.html">&#10003; El cierre</a><a class="nav-extra" href="herramientas.html">&#8983; Herramientas</a><a class="nav-extra" href="archivo.html">&#9776; Archivo</a><a class="learn-link" href="aprender.html">% Modo Aprendizaje <b>beta</b> &rarr;</a></div></nav>

<main class="wrap">
  <div class="sec-hero">
    <a class="volver" href="index.html">&larr; Portada</a>
    <h1>Archivo</h1>
    <p>Todas las notas publicadas, de la más nueva a la más vieja &middot; {len(articulos)} en total</p>
  </div>
  <div class="timeline">{_bloques}</div>
</main>

<footer>
  <div class="wrap">
    <div>
      <div class="f-brand"><span class="tri">%</span> {escape(portal['nombre'])}</div>
      <div class="f-desc">{escape(portal['descripcion'])}</div>
      <div style="margin-top:10px"><a href="como-trabajamos.html" style="font-family:var(--mono);font-size:12px;color:var(--teal-deep);text-decoration:none;border-bottom:1px solid var(--grid)">% Cómo trabajamos &rarr;</a> &middot; <a href="aprender.html" style="font-family:var(--mono);font-size:12px;color:var(--teal-deep);text-decoration:none;border-bottom:1px solid var(--grid)">Modo Aprendizaje &rarr;</a> &middot; <a href="feed.xml" style="font-family:var(--mono);font-size:12px;color:var(--teal-deep);text-decoration:none;border-bottom:1px solid var(--grid)">RSS &rarr;</a></div>
      <div style="margin-top:8px;font-family:var(--mono);font-size:11px;color:var(--faint)"><a href="suscribirse.html" style="color:var(--teal-deep);text-decoration:none;font-weight:600">Suscribite por mail</a> &middot; <a href="legal.html" style="color:var(--muted);text-decoration:none">Aviso legal y correcciones</a> &middot; <a href="privacidad.html" style="color:var(--muted);text-decoration:none">Política de privacidad</a> &middot; El contenido de este sitio es informativo y educativo; no constituye asesoramiento financiero.</div>
    </div>
  </div>
</footer>

<script>
(function(){{
  // 1) Apila masthead + ticker + barra de secciones como encabezado fijo,
  //    midiendo alturas reales. Sin esto la barra de secciones queda flotando
  //    sobre el contenido, porque el ticker se inyecta de forma asincrona.
  var mast=document.querySelector('.masthead'), sn=document.querySelector('.secnav');
  function apilar(){{
    var tk=document.getElementById('ci-ticker');
    var h1=mast?mast.offsetHeight:0;
    var h2=tk?tk.offsetHeight:0;
    if(tk){{ tk.style.position='sticky'; tk.style.top=h1+'px'; tk.style.zIndex=65; }}
    if(sn) sn.style.top=(h1+h2)+'px';
    document.documentElement.style.setProperty('--stack',(h1+h2+(sn?sn.offsetHeight:0))+'px');
  }}
  // 2) El mismo desplazamiento desfasa el salto al ancla que hace el
  //    navegador, asi que se rehace cuando la pagina termina de acomodarse.
  function irAlAncla(){{
    if(!location.hash) return;
    var el=document.getElementById(location.hash.slice(1));
    if(el) el.scrollIntoView({{block:"start"}});
  }}
  // Mientras el ticker termina de cargar el contenido se sigue moviendo, asi
  // que hay que rehacer el salto varias veces. Pero si el lector ya scrolleo,
  // se deja de corregir: nada peor que la pagina saltando sola.
  var libre = true;
  ['wheel','touchmove','keydown'].forEach(function(ev){{
    window.addEventListener(ev, function(){{ libre = false; }}, {{passive:true}});
  }});
  apilar();
  window.addEventListener('resize', apilar);
  window.addEventListener('load', function(){{ apilar(); if(libre) irAlAncla(); }});
  var t=0, iv=setInterval(function(){{
    apilar();
    if(libre) irAlAncla();
    if(++t>12) clearInterval(iv);
  }}, 300);
  window.addEventListener('hashchange', function(){{ libre = true; irAlAncla(); }});
}})();
</script>
<!-- CI-WIDGETS --><script defer src="assets/ticker.js?v=4"></script>
<script defer src="assets/metrics.js?v=1"></script>
</body>
</html>"""
with open(os.path.join(ROOT, "archivo.html"), "w", encoding="utf-8") as f:
    f.write(ARCHIVO)

# ---- hoy.html — "El cierre": los 5 datos del día, finito ----------------
_top5 = articulos[:5]
_cards_hoy = ""
for _i, _a in enumerate(_top5):
    _sc = SEC_COLOR.get(_a["seccion"], "#0E7C86")
    _cards_hoy += f"""
    <article class="c-card" data-paso="{_i+1}">
      <div class="c-head"><span class="c-n">{_i+1}</span><span class="c-sec" style="color:{_sc}">{escape(_a['seccion'])}</span><span class="c-check">&#10003;</span></div>
      <div class="c-num">{escape(_a.get('numero',''))} <span>{escape(_a.get('numero_label',''))}</span></div>
      <h2>{escape(_a['titulo'])}</h2>
      <p>{escape(_a['bajada'])}</p>
      <a class="c-link" href="{escape(_a['archivo'])}">Leer la nota completa &rarr;</a>
    </article>"""

HOY = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>El cierre — los 5 datos de hoy — {escape(portal['nombre'])}</title>
<meta name="description" content="La edición finita de Con Interés: los 5 datos verificados del día, 30 segundos cada uno. Terminás y estás al día. Sin publicidad, sin registro.">
<link rel="icon" type="image/svg+xml" href="assets/favicon.svg">
<link rel="alternate" type="application/rss+xml" title="Con Interés" href="/feed.xml">
<link rel="canonical" href="{SITE}/hoy.html">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;0,8..60,700&family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root{{
    --paper:#FAF8F4;--ink:#16130F;--ink-soft:#3C3833;--teal:#0E7C86;--teal-deep:#0A5C63;
    --amber:#C4701F;--green:#2E8B6F;--muted:#6B6560;--faint:#8A847C;
    --rule:#DCD6CC;--card:#FFFFFF;--card-edge:#EAE4DA;
    --serif:"Source Serif 4",Georgia,serif;--sans:"Inter",system-ui,sans-serif;--mono:"IBM Plex Mono",monospace;
  }}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);line-height:1.6;-webkit-font-smoothing:antialiased}}
  .wrap{{max-width:680px;margin:0 auto;padding:0 22px}}
  a{{color:var(--teal-deep)}}
  .masthead{{border-bottom:2px solid var(--ink);position:sticky;top:0;background:var(--paper);z-index:50}}
  .masthead .wrap{{display:flex;align-items:center;justify-content:space-between;height:56px;max-width:960px}}
  .brand{{font-family:var(--serif);font-weight:700;font-size:26px;display:flex;align-items:center;gap:8px;text-decoration:none;color:var(--ink)}}
  .brand .tri{{color:var(--teal)}}
  .brand .tag{{font-family:var(--mono);font-size:10px;color:var(--muted);letter-spacing:.14em;text-transform:uppercase;border-left:1px solid var(--rule);padding-left:8px;font-weight:500}}
  .mh-back{{font-family:var(--mono);font-size:12px;color:var(--teal-deep);text-decoration:none}}
  .barra{{position:sticky;top:56px;z-index:45;height:5px;background:var(--rule)}}
  .barra i{{display:block;height:100%;width:0;background:var(--teal);transition:width .2s}}
  .hero{{padding:36px 0 8px;text-align:center}}
  .kicker{{font-family:var(--mono);font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:var(--teal-deep);font-weight:600;margin-bottom:10px}}
  h1{{font-family:var(--serif);font-weight:700;font-size:40px;line-height:1.1;margin:0 0 10px}}
  .hero p{{font-size:16px;color:var(--muted);margin:0}}
  .c-card{{background:var(--card);border:1px solid var(--card-edge);border-radius:16px;padding:26px;margin:22px 0}}
  .c-head{{display:flex;align-items:center;gap:12px;margin-bottom:14px}}
  .c-n{{font-family:var(--mono);font-weight:600;font-size:14px;background:var(--ink);color:#fff;width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center}}
  .c-sec{{font-family:var(--mono);font-size:11px;letter-spacing:.12em;text-transform:uppercase;font-weight:600}}
  .c-check{{margin-left:auto;color:var(--rule);font-size:20px;font-weight:700;transition:color .3s}}
  .c-card.visto .c-check{{color:var(--green)}}
  .c-num{{font-family:var(--mono);font-size:26px;font-weight:600;color:var(--teal-deep);margin-bottom:10px;line-height:1.3}}
  .c-num span{{font-family:var(--sans);font-size:13px;color:var(--muted);font-weight:400}}
  .c-card h2{{font-family:var(--serif);font-size:23px;font-weight:700;line-height:1.2;margin:0 0 10px}}
  .c-card p{{font-size:15px;color:var(--ink-soft);margin:0 0 14px}}
  .c-link{{font-family:var(--mono);font-size:12px;font-weight:600;text-decoration:none}}
  .fin{{background:linear-gradient(120deg,#16130F,#0A5C63);border-radius:16px;color:#fff;text-align:center;padding:40px 28px;margin:30px 0}}
  .fin .sello{{font-size:44px;line-height:1}}
  .fin h2{{font-family:var(--serif);font-size:28px;font-weight:700;margin:12px 0 8px;color:#fff}}
  .fin p{{font-size:14px;color:#CDE4E1;margin:0 0 18px}}
  .fin a{{display:inline-block;font-family:var(--sans);font-size:14px;font-weight:600;background:#fff;color:var(--ink);padding:11px 22px;border-radius:10px;text-decoration:none}}
  .fin a:hover{{background:#F3D9A8}}
  footer{{border-top:2px solid var(--ink);margin-top:40px;padding:24px 0 60px}}
  footer .wrap{{font-family:var(--mono);font-size:12px;color:var(--muted)}}
  footer a{{text-decoration:none}}
  @media(max-width:600px){{h1{{font-size:31px}}.c-card{{padding:20px 18px}}}}
</style>
</head>
<body>

<header class="masthead">
  <div class="wrap">
    <a class="brand" href="index.html"><span class="tri">%</span>{escape(portal['nombre'])}<span class="tag">{escape(portal['tagline'])}</span></a>
    <a href="index.html" class="mh-back">← Portada</a>
  </div>
</header>
<div class="barra"><i id="prog"></i></div>

<div class="wrap">
  <div class="hero">
    <div class="kicker">&#10003; El cierre · {FECHA_MASTHEAD}</div>
    <h1>Los 5 datos de hoy</h1>
    <p>30 segundos cada uno. Cuando terminás, estás al día. Eso es todo — sin scroll infinito.</p>
  </div>
  {_cards_hoy}
  <div class="fin" id="fin">
    <div class="sello">&#10003;</div>
    <h2>Estás al día.</h2>
    <p>Eso era todo lo importante de hoy, verificado. Volvé mañana — o seguí explorando si te quedaste con ganas.</p>
    <a href="index.html">Ir a la portada completa &rarr;</a>
  </div>
</div>

<footer>
  <div class="wrap">
    <a href="index.html">Portada</a> · <a href="herramientas.html">Herramientas</a> · <a href="aprender.html">Modo Aprendizaje</a> · <a href="suscribirse.html">Suscribite</a> · <a href="legal.html">Aviso legal</a> · <a href="privacidad.html">Privacidad</a>
  </div>
</footer>

<script>
(function(){{
  var cards=[].slice.call(document.querySelectorAll('.c-card'));
  var prog=document.getElementById('prog');
  function tick(){{
    var vistos=0;
    cards.forEach(function(c){{
      var r=c.getBoundingClientRect();
      if(r.top < window.innerHeight*0.6) c.classList.add('visto');
      if(c.classList.contains('visto')) vistos++;
    }});
    prog.style.width=(vistos/cards.length*100)+'%';
  }}
  window.addEventListener('scroll',tick,{{passive:true}});
  tick();
}})();
</script>
<script>
(function(){{
  // 1) Apila masthead + ticker + barra de secciones como encabezado fijo,
  //    midiendo alturas reales. Sin esto la barra de secciones queda flotando
  //    sobre el contenido, porque el ticker se inyecta de forma asincrona.
  var mast=document.querySelector('.masthead'), sn=document.querySelector('.secnav');
  function apilar(){{
    var tk=document.getElementById('ci-ticker');
    var h1=mast?mast.offsetHeight:0;
    var h2=tk?tk.offsetHeight:0;
    if(tk){{ tk.style.position='sticky'; tk.style.top=h1+'px'; tk.style.zIndex=65; }}
    if(sn) sn.style.top=(h1+h2)+'px';
    document.documentElement.style.setProperty('--stack',(h1+h2+(sn?sn.offsetHeight:0))+'px');
  }}
  // 2) El mismo desplazamiento desfasa el salto al ancla que hace el
  //    navegador, asi que se rehace cuando la pagina termina de acomodarse.
  function irAlAncla(){{
    if(!location.hash) return;
    var el=document.getElementById(location.hash.slice(1));
    if(el) el.scrollIntoView({{block:"start"}});
  }}
  // Mientras el ticker termina de cargar el contenido se sigue moviendo, asi
  // que hay que rehacer el salto varias veces. Pero si el lector ya scrolleo,
  // se deja de corregir: nada peor que la pagina saltando sola.
  var libre = true;
  ['wheel','touchmove','keydown'].forEach(function(ev){{
    window.addEventListener(ev, function(){{ libre = false; }}, {{passive:true}});
  }});
  apilar();
  window.addEventListener('resize', apilar);
  window.addEventListener('load', function(){{ apilar(); if(libre) irAlAncla(); }});
  var t=0, iv=setInterval(function(){{
    apilar();
    if(libre) irAlAncla();
    if(++t>12) clearInterval(iv);
  }}, 300);
  window.addEventListener('hashchange', function(){{ libre = true; irAlAncla(); }});
}})();
</script>
<!-- CI-WIDGETS --><script defer src="assets/ticker.js?v=5"></script>
<script defer src="assets/metrics.js?v=1"></script>
</body>
</html>"""
with open(os.path.join(ROOT, "hoy.html"), "w", encoding="utf-8") as f:
    f.write(HOY)

# ---- sitemap.xml (para SEO) --------------------------------------------
urls = [f"  <url><loc>{SITE}/</loc><changefreq>hourly</changefreq><priority>1.0</priority></url>"]
urls.append(f"  <url><loc>{SITE}/hoy.html</loc><changefreq>hourly</changefreq><priority>0.9</priority></url>")
for pg in ("aprender.html", "como-trabajamos.html", "suscribirse.html", "legal.html", "privacidad.html", "herramientas.html", "pregunta.html", "archivo.html"):
    urls.append(f"  <url><loc>{SITE}/{pg}</loc><changefreq>weekly</changefreq><priority>0.7</priority></url>")
for ind in ("dolar-oficial", "dolar-blue", "dolar-mep", "riesgo-pais", "inflacion"):
    urls.append(f"  <url><loc>{SITE}/indicador/{ind}.html</loc><changefreq>daily</changefreq><priority>0.8</priority></url>")
# las paginas de seccion: si no entran aca, nacen sin indexar
for pg in paginas_seccion:
    urls.append(f"  <url><loc>{SITE}/{pg}</loc><changefreq>daily</changefreq><priority>0.8</priority></url>")
for a in articulos:
    urls.append(
        f"  <url><loc>{SITE}/{escape(a['archivo'])}</loc>"
        f"<lastmod>{a['fecha']}</lastmod><changefreq>monthly</changefreq><priority>0.8</priority></url>")
sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' \
          + "\n".join(urls) + "\n</urlset>\n"
with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as f:
    f.write(sitemap)

print(f"OK -> {out}  ({len(articulos)} notas, {len(borradores)} en cola)  + sitemap.xml")
