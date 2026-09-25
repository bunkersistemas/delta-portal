#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_empresas.py - La agenda de empresas: que presentaron, y que anunciaron.

Por que existe
--------------
Hasta el 25/09/2026 la redaccion arrancaba siempre por el calendario del INDEC
y el BCRA, y con esa entrada lo macro ganaba siempre: es lo unico que llega con
fuente primaria asegurada y serie armada. De 136 notas publicadas, dos eran
sobre una empresa con nombre propio. Este script le da a los negocios una
entrada con el mismo peso: documentos que las empresas presentan ante sus
reguladores, con fecha y enlace.

De donde salen los datos - SIEMPRE de la fuente primaria
--------------------------------------------------------
  CNV  Hechos relevantes, solapa EMPRESAS:
       https://www.cnv.gov.ar/SitioWeb/HechosRelevantes
       La pagina muestra solo los ultimos 50 (unos cuatro dias), por eso este
       script ACUMULA en data/empresas.json: lo que no se baja se pierde.
  SEC  Presentaciones de las empresas argentinas que cotizan en EE.UU.
       (data.sec.gov/submissions). De ahi salen los ANUNCIOS de fecha de
       balance: la frase en la que la propia empresa dice cuando presenta.

No se estima NINGUNA fecha. Un anuncio entra solo si la empresa escribio la
fecha en un documento presentado; si no la escribio, no hay anuncio.

La clasificacion NO es dato
---------------------------
`tipo` (balance, hecho, financiamiento, judicial) es una preclasificacion con
listas de palabras, para no leer 50 filas por corrida. La nota se escribe
desde el documento, nunca desde la descripcion de una linea.

Uso:  python scripts/build_empresas.py [--dias 30]
"""
import argparse
import datetime
import html
import io
import json
import os
import re
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(ROOT, "data", "empresas.json")

CNV_HR = "https://www.cnv.gov.ar/SitioWeb/HechosRelevantes"
SEC_SUB = "https://data.sec.gov/submissions/CIK%010d.json"
SEC_DOC = "https://www.sec.gov/Archives/edgar/data/%d/%s/%s"
SEC_IDX = "https://www.sec.gov/Archives/edgar/data/%d/%s/index.json"

UA = "Mozilla/5.0 (compatible; ConInteres/1.0; +https://coninteres.com)"
# La SEC exige un User-Agent con nombre y contacto; sin eso contesta 403.
UA_SEC = "ConInteres redaccion@coninteres.com"

# Empresas argentinas (o con negocio central en la Argentina) que presentan
# ante la SEC. CIK leido de sec.gov/files/company_tickers.json el 25/09/2026.
SEC_EMPRESAS = [
    ("YPF", 904851, "YPF"),
    ("GGAL", 1114700, "Grupo Financiero Galicia"),
    ("MELI", 1099590, "Mercado Libre"),
    ("PAM", 1469395, "Pampa Energia"),
    ("VIST", 1762506, "Vista Energy"),
    ("TEO", 932470, "Telecom Argentina"),
    ("LOMA", 1711375, "Loma Negra"),
    ("BMA", 1347426, "Banco Macro"),
    ("BBAR", 913059, "BBVA Argentina"),
    ("SUPV", 1517399, "Grupo Supervielle"),
    ("TGS", 931427, "Transportadora de Gas del Sur"),
    ("EDN", 1395213, "Edenor"),
    ("CEPU", 1717161, "Central Puerto"),
    ("CAAP", 1717393, "Corporacion America Airports"),
    ("GLOB", 1557860, "Globant"),
    ("IRS", 933267, "IRSA"),
    ("CRESY", 1034957, "Cresud"),
    ("BIOX", 1769484, "Bioceres"),
    ("TX", 1342874, "Ternium"),
]
SEC_FORMS = {"6-K", "8-K", "10-Q", "10-K", "20-F"}
# 8-K: el item dice de que se trata sin abrir el documento.
ITEMS_8K = {
    "1.01": "acuerdo relevante", "1.02": "fin de un acuerdo relevante",
    "2.01": "compra o venta de activos", "2.02": "RESULTADOS",
    "2.03": "nueva deuda", "5.02": "cambio de directivos",
    "7.01": "comunicado", "8.01": "otro hecho",
}

# --- preclasificacion editorial de la CNV (criterio, no dato) --------------
# Rutina que no es noticia: se descarta. Se mira antes que lo interesante,
# porque "HECHO RELEVANTE - CONVOCATORIA A ASAMBLEA" es rutina igual.
RUTINA = [
    "CONVOCATORIA", "CONVOCAR", "DELEGACION", "DELEGACI", "CEDEAR",
    "AVISO DE PAGO", "AVISOS DE PAGO", "INFORMACION DIARIA", "INFORMACIÓN DIARIA",
    "CALIFICACI", "VOTO ACUMULATIVO", "REPRESENTACION LEGAL",
    "REPRESENTACIÓN LEGAL", "ACTA DE DIRECTORIO", "NOMINA", "NÓMINA",
    "AUTORIDADES", "DOMICILIO", "RESPONSABLE DE RELACIONES",
]
# "INFORMACION FINANCIERA" a secas NO es balance: bajo ese rotulo la CNV
# publica calificaciones de riesgo y recompras de obligaciones (21/09/2026).
TIPOS = [
    ("balance", ["ESTADOS FINANCIEROS", "ESTADOS CONTABLES", "RESEÑA INFORMATIVA",
                 "RESULTADOS DEL"]),
    ("judicial", ["CONCURSO", "QUIEBRA", "INFORMACIÓN JUDICIAL", "SENTENCIA",
                  "ACUERDO PREVENTIVO", "INFORMACION JUDICIAL"]),
    ("financiamiento", ["RESULTADO DE COLOCACI", "RESULTADO DE LA COLOCACI",
                        "SUPLEMENTO DE PRECIO", "EMISIÓN DE OBLIGACIONES",
                        "OBLIGACIONES NEGOCIABLES"]),
    ("hecho", ["HECHO RELEVANTE", "ADQUISICI", "FUSI", "ESCISI", "VENTA DE",
               "ACUERDO", "INVERSI", "DIVIDENDO", "RECOMPRA", "OFERTA PÚBLICA DE ADQUISICI",
               "CONTRATO", "LICITACI", "CIERRE DE PLANTA", "SUSPENSI"]),
]

MESES = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
         "jul": 7, "ago": 8, "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12}
MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}
MESES_LARGOS = {m: i for i, m in enumerate(
    ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
     "septiembre", "octubre", "noviembre", "diciembre"], 1)}


def bajar(url, ua=UA, tope=None):
    pedido = urllib.request.Request(url, headers={"User-Agent": ua})
    with urllib.request.urlopen(pedido, timeout=60) as r:
        crudo = r.read(tope) if tope else r.read()
    return crudo.decode("utf-8", "replace")


def texto_plano(t):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", t, flags=re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t))).strip()


def tipo_cnv(desc):
    d = desc.upper()
    for tipo, claves in TIPOS[:2]:
        # balance y judicial ganan aunque la linea diga "convocatoria"
        if any(k in d for k in claves):
            return tipo
    if any(k in d for k in RUTINA):
        return None
    for tipo, claves in TIPOS[2:]:
        if any(k in d for k in claves):
            return tipo
    return None


def fecha_cnv(s):
    """'24 sep. 2026 22:19' -> '2026-09-24T22:19'."""
    m = re.match(r"(\d{1,2}) (\w{3})\.? (\d{4}) (\d{1,2}):(\d{2})", s.strip())
    if not m or m.group(2).lower() not in MESES:
        return None
    d = datetime.datetime(int(m.group(3)), MESES[m.group(2).lower()], int(m.group(1)),
                          int(m.group(4)), int(m.group(5)))
    return d.strftime("%Y-%m-%dT%H:%M")


def cnv():
    t = bajar(CNV_HR)
    a = t.find('id="1a"')  # solapa EMPRESAS
    if a < 0:
        raise RuntimeError("no encontre la solapa EMPRESAS (id=1a): cambio la pagina")
    b = t.find('class="tab-pane', a + 10)
    seg = t[a:b if b > 0 else None]
    filas = re.findall(
        r"<tr>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>.*?href=\"(.*?)\"",
        seg, re.S)
    if not filas:
        raise RuntimeError("la solapa EMPRESAS vino sin filas: cambio la pagina")
    out, rutina = [], 0
    for fecha, entidad, desc, doc, url in filas:
        desc = texto_plano(desc)
        tipo = tipo_cnv(desc)
        f = fecha_cnv(texto_plano(fecha))
        if not tipo or not f:
            rutina += 1
            continue
        out.append({
            "id": "cnv-" + texto_plano(doc),
            "fuente": "CNV",
            "fecha": f,
            "entidad": texto_plano(entidad).rstrip(".").strip(),
            "tipo": tipo,
            "descripcion": desc,
            "url": html.unescape(url),
        })
    return out, len(filas), rutina


# --- SEC ---------------------------------------------------------------------
RX_EN = re.compile(r"(january|february|march|april|may|june|july|august|september|"
                   r"october|november|december)\s+(\d{1,2}),?\s+(\d{4})", re.I)
RX_ES = re.compile(r"(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|"
                   r"agosto|septiembre|octubre|noviembre|diciembre)\s+(?:de\s+)?(\d{4})", re.I)
# Amplio a proposito: Vista anuncio su balance del 3T (23/09/2026) diciendo
# "consolidated financial statements" y "webcast", sin "earnings". Lo que
# evita el falso positivo es la fecha FUTURA, no la palabra.
RX_ANUNCIO = re.compile(r"(earnings|results|financial statements|conference call|webcast|"
                        r"resultados|estados financieros|estados contables)", re.I)


HORIZONTE_ANUNCIO = 120  # dias
CABEZA_ANUNCIO = 4000    # caracteres


def anuncios_en(texto, presentado):
    """Frases donde la empresa escribe una fecha FUTURA junto a resultados o
    conferencia. Solo lo que esta escrito: nada se infiere.

    Se busca en el comienzo del documento y hasta 120 dias adelante: un
    balance entero esta lleno de fechas futuras que no son anuncios (en el de
    Loma Negra, el vencimiento de una concesion en 2032)."""
    out = []
    texto = texto[:CABEZA_ANUNCIO]
    tope = presentado + datetime.timedelta(days=HORIZONTE_ANUNCIO)
    for m in list(RX_EN.finditer(texto)) + list(RX_ES.finditer(texto)):
        try:
            if m.re is RX_EN:
                f = datetime.date(int(m.group(3)), MONTHS[m.group(1).lower()], int(m.group(2)))
            else:
                f = datetime.date(int(m.group(3)), MESES_LARGOS[m.group(2).lower()], int(m.group(1)))
        except ValueError:
            continue
        if f <= presentado or f > tope:
            continue
        ventana = texto[max(0, m.start() - 220): m.end() + 80]
        if not RX_ANUNCIO.search(ventana):
            continue
        out.append((f.isoformat(), ventana.strip()))
    return out


RX_BALANCE = re.compile(r"(quarter|annual|trimestr|semestr|anual)\w*.{0,60}(earnings|results|resultados)"
                        r"|financial statements|estados financieros|estados contables", re.I)


def cuerpo_6k(portada):
    """Lo que viene despues de la caratula del formulario (los tildes de
    'Form 20-F / Form 40-F'), que es donde empieza lo que la empresa dice."""
    cab = portada[:5000]
    i = cab.rfind("Form 40-F")
    if i < 0:
        return portada
    return portada[i + len("Form 40-F"):].lstrip(" .:_X☐☒()").strip()


def asunto_6k(portada, anexos):
    """El asunto de un 6-K. Por orden: la referencia de la carta a la CNV
    ('Ref.: ...'), el 'ITEM 1' de la portada (YPF), el comienzo del cuerpo, y
    si la portada esta vacia (Galicia) el comienzo del primer anexo."""
    for marca in ("Ref.:", "Ref:", "REF.:", "ITEM 1", "Item 1"):
        i = portada.find(marca)
        if i >= 0:
            return portada[i + len(marca): i + len(marca) + 180].strip(" .:-")
    cuerpo = cuerpo_6k(portada)
    if len(cuerpo) > 60 and not cuerpo.lower().startswith(("signature", "pursuant", "indicate")):
        return cuerpo[:180]
    for t in anexos:
        if len(t) > 40:
            return t[:180]
    return ""


def anexos_6k(cik, acc, principal):
    """Texto de los anexos .htm de un 6-K (hasta dos), leidos del indice."""
    base = acc.replace("-", "")
    idx = json.loads(bajar(SEC_IDX % (cik, base), UA_SEC))
    nombres = [it["name"] for it in idx["directory"]["item"]
               if it["name"].lower().endswith((".htm", ".html")) and it["name"] != principal
               and "index" not in it["name"].lower() and it.get("size", "").isdigit()
               and int(it["size"]) < 3000000]
    textos = []
    for n in nombres[:2]:
        time.sleep(0.2)
        textos.append(texto_plano(bajar(SEC_DOC % (cik, base, n), UA_SEC, 400000)))
    return textos, 1 + len(nombres[:2])


def sec(dias, conocidos):
    """Devuelve (hechos, anuncios, pedidos, vistos). `vistos` son las
    presentaciones ya leidas que no son noticia: se guardan para no volver a
    bajarlas en cada corrida, que es lo que cuesta."""
    hoy = datetime.date.today()
    desde = hoy - datetime.timedelta(days=dias)
    hechos, anuncios, pedidos, vistos = [], [], 0, {}
    for ticker, cik, nombre in SEC_EMPRESAS:
        sub = json.loads(bajar(SEC_SUB % cik, UA_SEC))
        pedidos += 1
        r = sub["filings"]["recent"]
        for i in range(len(r["form"])):
            form = r["form"][i]
            presentado = datetime.date.fromisoformat(r["filingDate"][i])
            if presentado < desde:
                break  # vienen de la mas nueva a la mas vieja
            if form not in SEC_FORMS:
                continue
            acc = r["accessionNumber"][i]
            hid = "sec-" + acc
            url = SEC_DOC % (cik, acc.replace("-", ""), r["primaryDocument"][i])
            if hid in conocidos:
                continue  # ya bajado en una corrida anterior
            items = [x.strip() for x in (r.get("items", [""] * (i + 1))[i] or "").split(",") if x.strip()]
            asunto, tipo = "", "hecho"
            relevante = True
            if form in ("10-Q", "10-K", "20-F"):
                tipo, asunto = "balance", {"10-Q": "balance trimestral", "10-K": "balance anual",
                                           "20-F": "memoria y balance anual"}[form]
            else:
                # 6-K y 8-K son cortos: se abre la portada para el asunto y
                # para buscar una fecha anunciada de balance.
                time.sleep(0.2)  # la SEC pide no pasar de 10 pedidos por segundo
                txt = texto_plano(bajar(url, UA_SEC, 400000))
                pedidos += 1
                if form == "8-K":
                    asunto = "; ".join(ITEMS_8K.get(x, "item " + x) for x in items if x != "9.01")
                    if "2.02" in items:
                        tipo = "balance"
                else:
                    anexos, n = anexos_6k(cik, acc, r["primaryDocument"][i])
                    pedidos += n
                    asunto = asunto_6k(txt, anexos)
                    # el anuncio puede estar en la portada o en el primer anexo
                    txt = " ".join([cuerpo_6k(txt)[:CABEZA_ANUNCIO // 2]] + [a[:CABEZA_ANUNCIO // 2] for a in anexos[:1]])
                    # Se clasifica por el ASUNTO, no por el cuerpo: casi toda
                    # carta a la CNV menciona "financial statements" de pasada
                    # (Central Puerto, recompra de acciones, 01/09/2026).
                    if RX_BALANCE.search(asunto):
                        tipo = "balance"
                    else:
                        # un 6-K que no es balance casi siempre es la traduccion
                        # de algo que ya esta en la CNV, con descripcion en
                        # castellano: la agenda lo toma de ahi.
                        relevante = False
                for f, frase in anuncios_en(txt, presentado):
                    anuncios.append({"id": "%s-%s" % (hid, f), "fuente": "SEC", "fecha": f,
                                     "entidad": nombre, "ticker": ticker, "frase": frase,
                                     "url": url, "presentado": presentado.isoformat()})
            if not relevante:
                vistos[hid] = r["filingDate"][i]
                continue
            hechos.append({"id": hid, "fuente": "SEC", "fecha": r["filingDate"][i],
                           "entidad": nombre, "ticker": ticker, "tipo": tipo,
                           "descripcion": ("%s %s" % (form, asunto)).strip(), "url": url})
        time.sleep(0.2)
    return hechos, anuncios, pedidos, vistos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dias", type=int, default=30, help="cuanto se guarda hacia atras")
    args = ap.parse_args()

    previo = {}
    if os.path.exists(SALIDA):
        previo = json.load(io.open(SALIDA, encoding="utf-8"))
    hechos = {h["id"]: h for h in previo.get("hechos", [])}
    anuncios = {a["id"]: a for a in previo.get("anuncios", [])}
    vistos = dict(previo.get("sec_vistos", {}))
    incompleto = []

    try:
        nuevos, en_pagina, rutina = cnv()
        n0 = len(hechos)
        for h in nuevos:
            hechos[h["id"]] = h
        print("CNV: %d filas en la pagina, %d rutina descartada, %d nuevas guardadas"
              % (en_pagina, rutina, len(hechos) - n0))
    except Exception as e:
        incompleto.append("CNV: %s" % e)
        print("CNV: FALLA -", e, file=sys.stderr)

    try:
        nuevos, anun, pedidos, v = sec(args.dias, set(hechos) | set(vistos))
        vistos.update(v)
        for h in nuevos:
            hechos[h["id"]] = h
        for a in anun:
            anuncios[a["id"]] = a
        print("SEC: %d empresas, %d pedidos, %d presentaciones nuevas utiles, %d leidas y "
              "descartadas, %d anuncios de fecha nuevos"
              % (len(SEC_EMPRESAS), pedidos, len(nuevos), len(v), len(anun)))
    except Exception as e:
        incompleto.append("SEC: %s" % e)
        print("SEC: FALLA -", e, file=sys.stderr)

    hoy = datetime.date.today()
    corte = (hoy - datetime.timedelta(days=args.dias)).isoformat()
    lista_h = sorted((h for h in hechos.values() if h["fecha"][:10] >= corte),
                     key=lambda h: h["fecha"], reverse=True)
    corte_a = (hoy - datetime.timedelta(days=7)).isoformat()
    lista_a = sorted((a for a in anuncios.values() if a["fecha"] >= corte_a),
                     key=lambda a: a["fecha"])

    # Si fallaron las dos fuentes no se pisa lo que habia: un archivo vacio
    # diria "no paso nada" cuando en realidad no se pudo mirar.
    if len(incompleto) == 2 and previo:
        print("Las dos fuentes fallaron: data/empresas.json queda como estaba.", file=sys.stderr)
        return 1

    salida = {
        "generado": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M"),
        "fuentes": [CNV_HR, "https://data.sec.gov/submissions/"],
        "incompleto": incompleto,
        "hechos": lista_h,
        "anuncios": lista_a,
        "sec_vistos": {k: f for k, f in sorted(vistos.items()) if f >= corte},
    }
    with io.open(SALIDA, "w", encoding="utf-8", newline="\n") as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("data/empresas.json: %d hechos (%d dias), %d anuncios de fecha"
          % (len(lista_h), args.dias, len(lista_a)))
    return 1 if incompleto else 0


if __name__ == "__main__":
    sys.exit(main())
