#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agenda.py - Que sale, cuando, y que escribimos la ultima vez sobre eso.

Lee data/calendario.json (lo genera build_calendario.py desde los calendarios
oficiales del INDEC y del BCRA) y lo cruza con data/articulos.json para que la
corrida de redaccion no arranque en una pagina en blanco: para cada dato que
esta por salir muestra la nota anterior de esa misma serie, que es la que hay
que actualizar y contra la que hay que comparar.

Es la diferencia entre "a ver que encuentro hoy" y "el jueves a las 16 sale el
IPC de agosto, la ultima que escribimos fue esta, y el dato a superar es este".

Ademas lee data/empresas.json (lo genera build_empresas.py desde la CNV y la
SEC): los balances y hechos relevantes que las empresas presentaron en los
ultimos dias, y las fechas de balance que ellas mismas anunciaron. Sin esa
entrada lo macro gana siempre, porque es lo unico que llega con fuente
primaria asegurada (de 136 notas al 25/09/2026, dos eran de una empresa).

Y lee data/pedidos.json y lista lo que pidieron los lectores. Son las
entradas del paso 0: lo que va a salir (el calendario), lo que presentaron
las empresas, y lo que alguien quiere saber (los pedidos). Un pedido es un CANDIDATO para el Editor, nunca una orden:
ver agente/NEWSROOM.md, seccion 2 ter.

Uso:
  python scripts/agenda.py                # los proximos 14 dias
  python scripts/agenda.py --dias 30
  python scripts/agenda.py --alta         # solo prioridad alta
  python scripts/agenda.py --dias-empresas 5
"""
import argparse
import datetime
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Palabras que no distinguen una serie de otra: no sirven para emparejar.
VACIAS = set("""
de del la el los las y en a al por para con sobre un una unos unas su sus
segundo primer primera tercer cuarto trimestre mes mensual anual año años
argentina argentino nacional cobertura indice índice informe indicador
indicadores sistema valorizacion valorización datos dato total totales
enero febrero marzo abril mayo junio julio agosto septiembre octubre
noviembre diciembre bienes evolucion evolución avance nivel
""".split())

# Emparejar por palabras sueltas no alcanza: el IPC del INDEC y nuestra nota
# titulada "inflación" no comparten ninguna, y en cambio "precios mayoristas"
# engancha cualquier nota que diga "precios". Este mapa dice, para cada serie
# oficial, con que terminos la nombramos nosotros. Se amplia a mano cuando
# aparece una serie nueva; lo que no este aca cae al emparejado por palabras,
# que es mas laxo y por eso exige mas coincidencias.
SERIES = [
    (["precios al consumidor", "ipc"],          ["inflacion", "ipc", "precios"]),
    (["canasta basica", "canasta básica"],      ["canasta", "pobreza", "indigencia"]),
    (["canasta de crianza"],                    ["crianza", "canasta"]),
    (["pobreza"],                               ["pobreza", "indigencia"]),
    (["mercado de trabajo"],                    ["desempleo", "empleo", "trabajo"]),
    (["actividad economica", "emae"],           ["emae", "actividad"]),
    (["produccion industrial manufacturero",
      "producción industrial manufacturero"],   ["industria", "manufacturer", "fabril"]),
    (["actividad de la construccion",
      "actividad de la construcción", "isac"],  ["construccion", "cemento", "corralones"]),
    (["costo de la construccion",
      "costo de la construcción", "icc"],       ["construccion", "corralones"]),
    (["capacidad instalada"],                   ["capacidad instalada", "ociosa"]),
    (["precios mayoristas", "sipm"],            ["mayorista"]),
    (["intercambio comercial", "ica"],          ["comercio exterior", "exportacion",
                                                 "importacion", "superavit comercial",
                                                 "balanza"]),
    (["balanza de pagos", "cuentas internacionales"], ["cuenta corriente", "balanza",
                                                        "deuda externa"]),
    (["deuda externa"],                         ["deuda externa"]),
    (["industrial minero"],                     ["mineria", "litio", "minero"]),
    (["industrial pesquero"],                   ["pesca", "pesquero"]),
    (["servicios publicos", "servicios públicos", "issp"], ["servicios"]),
    (["supermercados", "autoservicios"],        ["supermercado", "shopping", "consumo"]),
    (["turismo"],                               ["turismo", "turista", "pasajeros"]),
    (["expectativas de mercado", "rem"],        ["rem", "expectativas", "proyeccion"]),
    (["monetario mensual"],                     ["monetario", "base monetaria", "pesos"]),
    (["mercado de cambios"],                    ["cambiario", "dolares", "mercado de cambios",
                                                 "reservas"]),
    (["sobre bancos"],                          ["bancos", "credito", "mora", "deposito"]),
    (["estabilidad financiera"],                ["bancos", "financiero", "riesgo"]),
    (["politica monetaria", "política monetaria", "ipom"], ["monetario", "tasa"]),
    (["inversion extranjera", "inversión extranjera"],     ["inversion extranjera", "ied"]),
    (["condiciones crediticias"],               ["credito", "hipotecario"]),
    (["pagos minoristas"],                      ["pagos", "transferencias", "qr"]),
    (["origen provincial"],                     ["provincial", "provincia"]),
    (["accesos a internet"],                    ["internet", "conectividad"]),
    (["farmaceutica", "farmacéutica"],          ["farmac", "medicamento", "prepaga"]),
]


def _rx(termino, cerrado):
    """Regex anclada a comienzo de palabra; cerrada tambien al final si el
    termino es corto. Sin esto 'ica' (por intercambio comercial) matchea dentro
    de 'publica' y el calendario emparejaba la dotacion de personal de la
    administracion publica con una nota de comercio exterior."""
    fin = r"\b" if cerrado or len(termino) <= 4 else ""
    return re.compile(r"\b" + re.escape(termino) + fin)


def terminos_de(publicacion):
    """Los terminos con los que NOSOTROS nombramos esta serie, si la conocemos."""
    t = sin_tildes(publicacion)
    for patrones, nuestros in SERIES:
        if any(_rx(sin_tildes(p), True).search(t) for p in patrones):
            return nuestros
    return None


def sin_tildes(t):
    t = t.lower()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ñ", "n")):
        t = t.replace(a, b)
    return t


def palabras(t):
    return {w for w in re.findall(r"[a-z]{4,}", sin_tildes(t)) if w not in VACIAS}


def cargar(nombre):
    p = os.path.join(ROOT, "data", nombre)
    if not os.path.exists(p):
        return None
    return json.load(io.open(p, encoding="utf-8"))


def pedidos_registrados():
    """Todos los pedidos del manifiesto, en cualquier estado."""
    datos = cargar("pedidos.json")
    return (datos or {}).get("pedidos", [])


def pedidos_pendientes():
    """Lo que pidieron los lectores y todavia no tiene respuesta."""
    return [p for p in pedidos_registrados()
            if p.get("estado") in ("recibido", "en_ficha")]


def imprimir_pedidos(pend):
    """La segunda entrada del paso 0.

    Mientras el canal de pedidos este suspendido (ver NEWSROOM.md 2 ter) el
    manifiesto esta vacio y este bloque no imprime nada: no tiene sentido
    ensuciar cada corrida con una seccion en cero de algo que todavia no
    esta abierto. Reaparece solo cuando entra el primer pedido."""
    if not pedidos_registrados():
        return
    print()
    print("=" * 78)
    print("PEDIDOS DE LECTORES  (%d sin responder)" % len(pend))
    print("=" * 78)
    if not pend:
        print("  No hay pedidos pendientes.")
        print("  Entran por pedidos.html y se registran en data/pedidos.json.")
        return
    for p in sorted(pend, key=lambda x: x.get("recibido", "")):
        en_ficha = p.get("estado") == "en_ficha"
        print("  %s [%s] %s  %s" % (" * " if en_ficha else "   ",
                                    p.get("id", "?"),
                                    p.get("recibido", ""),
                                    p.get("afirmacion", "")[:58]))
        if p.get("de_donde"):
            print("        el lector dice que salio de: %s" % p["de_donde"][:58])
        if en_ficha:
            print("        YA EN FICHA - no volver a empezarlo")
    print()
    print("  Un pedido es un candidato para el Editor, no una orden: se elige")
    print("  con los mismos criterios (riqueza de datos, relevancia, no repetir)")
    print("  y se verifica con el mismo protocolo. Ver NEWSROOM.md, seccion 2 ter.")


# Palabras del nombre de una empresa que no la identifican.
VACIAS_EMPRESA = set("""
sa s a sau saic sab cv inc corp corporation grupo group banco bank compania
compañia compañía sociedad anonima anónima argentina argentino
energia energía de del la el y
""".split())


def claves_empresa(nombre):
    return [w for w in re.findall(r"[a-z]{3,}", sin_tildes(nombre))
            if w not in VACIAS_EMPRESA]


def ultima_nuestra(nombre, idx):
    """Nuestra ultima nota que nombra a esta empresa en el titulo o el slug."""
    claves = claves_empresa(nombre)[:2]
    if not claves:
        return None
    rx = [_rx(c, False) for c in claves]
    for _, crudo, a in idx:  # de la mas nueva a la mas vieja
        if all(r.search(crudo) for r in rx):
            return a
    return None


def imprimir_empresas(arts, idx, hoy, dias_hechos, dias_anuncios):
    emp = cargar("empresas.json")
    print()
    print("=" * 78)
    print("EMPRESAS  (CNV y SEC: lo que las empresas presentaron)")
    print("=" * 78)
    if not emp:
        print("  Falta data/empresas.json. Corre:  python scripts/build_empresas.py")
        return
    gen = emp.get("generado", "")
    print("  generado %s%s" % (gen, "" if not emp.get("incompleto")
                               else "   OJO incompleto: " + "; ".join(emp["incompleto"])))

    notas_emp = sorted((a for a in arts if a.get("seccion") == "EMPRESAS"),
                       key=lambda a: a.get("fecha", ""), reverse=True)
    if notas_emp:
        ult = notas_emp[0]
        hace = (hoy - datetime.date.fromisoformat(ult["fecha"])).days
        print("  ultima nota EMPRESAS: %s (hace %d dias) - %s"
              % (ult["fecha"], hace, ult["titulo"][:48]))
        cupo = hace >= 1
    else:
        print("  ultima nota EMPRESAS: ninguna todavia")
        cupo = True
    if cupo:
        print("  -> HOY NO HAY NOTA DE EMPRESAS: una candidata de aca compite con la")
        print("     misma ventaja que el dato del calendario (ver NEWSROOM.md 2 quater).")

    hasta = hoy + datetime.timedelta(days=dias_anuncios)
    anun = [a for a in emp.get("anuncios", [])
            if hoy <= datetime.date.fromisoformat(a["fecha"]) <= hasta]
    print()
    print("  Fechas de balance ANUNCIADAS por la empresa (proximos %d dias): %d"
          % (dias_anuncios, len(anun)))
    for a in anun:
        print("    %s  %-22s %s" % (a["fecha"], a["entidad"][:22], a["url"]))
        print("        \"...%s\"" % a["frase"][-110:])

    desde = (hoy - datetime.timedelta(days=dias_hechos)).isoformat()
    hechos = [h for h in emp.get("hechos", []) if h["fecha"][:10] >= desde]
    orden = {"balance": 0, "judicial": 1, "hecho": 2, "financiamiento": 3}
    hechos.sort(key=lambda h: h["fecha"], reverse=True)
    hechos.sort(key=lambda h: orden.get(h["tipo"], 9))  # estable: dentro del tipo, la mas nueva primero
    print()
    print("  Presentado en los ultimos %d dias: %d (balances primero)" % (dias_hechos, len(hechos)))
    for h in hechos:
        print("    %s %-4s %-14s %s" % (h["fecha"][:10], h["fuente"], h["tipo"], h["entidad"][:40]))
        print("        %s" % h["descripcion"][:100])
        print("        %s" % h["url"])
        prev = ultima_nuestra(h["entidad"], idx)
        if prev:
            print("        ultima nuestra: %s (%s)" % (prev["titulo"][:56], prev["fecha"]))
    print()
    print("  La linea de arriba es el TEMA, no el dato: la nota se escribe desde el")
    print("  documento enlazado. El tipo es preclasificacion, no dato de la fuente.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dias", type=int, default=14)
    ap.add_argument("--alta", action="store_true", help="solo prioridad alta")
    ap.add_argument("--dias-empresas", type=int, default=4,
                    help="cuantos dias hacia atras de presentaciones de empresas")
    args = ap.parse_args()

    cal = cargar("calendario.json")
    if not cal:
        print("Falta data/calendario.json. Corre:  python scripts/build_calendario.py",
              file=sys.stderr)
        return 1

    arts = (cargar("articulos.json") or {}).get("articulos", [])
    # Se empareja contra el TITULO y el slug del archivo, no contra la bajada:
    # la bajada menciona de pasada "pobreza" o "pesos" para comparar, y con eso
    # el calendario terminaba diciendo que la nota anterior del IPC era una de
    # hockey. El titulo es de lo que la nota trata.
    idx = []
    for a in arts:
        crudo = " ".join([a.get("titulo", ""), a.get("archivo", "").replace("-", " ")])
        idx.append((palabras(crudo), sin_tildes(crudo), a))
    idx.sort(key=lambda x: x[2].get("fecha", ""), reverse=True)  # la mas nueva primero

    hoy = datetime.date.today()
    hasta = hoy + datetime.timedelta(days=args.dias)

    gen = cal.get("generado", "")[:10]
    if gen and (hoy - datetime.date.fromisoformat(gen)).days > 20:
        print("OJO: el calendario se genero el %s. Convendria rehacerlo.\n" % gen)
    if cal.get("incompleto"):
        print("OJO: calendario incompleto ->", "; ".join(cal["incompleto"]), "\n")

    filas = [p for p in cal["publicaciones"]
             if hoy <= datetime.date.fromisoformat(p["fecha"]) <= hasta
             and (not args.alta or p["prioridad"] == "alta")]

    if not filas:
        print("No hay publicaciones en la ventana pedida.")
        imprimir_empresas(arts, idx, hoy, args.dias_empresas, args.dias)
        imprimir_pedidos(pedidos_pendientes())
        return 0

    print("AGENDA - %s al %s   (%d publicaciones%s)"
          % (hoy, hasta, len(filas), ", solo alta" if args.alta else ""))
    print("=" * 78)

    dia_actual = None
    for p in filas:
        f = datetime.date.fromisoformat(p["fecha"])
        if p["fecha"] != dia_actual:
            dia_actual = p["fecha"]
            faltan = (f - hoy).days
            cuando = "HOY" if faltan == 0 else ("manana" if faltan == 1 else "en %d dias" % faltan)
            print("\n%s  %s  (%s)" % (p["fecha"], f.strftime("%A"), cuando))
            print("-" * 78)

        marca = {"alta": "***", "media": " * ", "baja": "   "}[p["prioridad"]]
        hora = p["hora"] or "  -  "
        print("  %s %s %-5s %s" % (marca, hora, p["organismo"], p["publicacion"]))

        # La nota anterior de la misma serie: contra esa se compara el dato
        # nuevo. Primero por el mapa SERIES, que es explicito; si la serie no
        # esta mapeada, por palabras, exigiendo 3 coincidencias para no
        # emparejar cualquier cosa que comparta la palabra "precios".
        mejor, como = None, ""
        nuestros = terminos_de(p["publicacion"])
        if nuestros:
            # Anclado a comienzo de palabra: buscar "rem" como subcadena
            # engancha "premios", y "pesos" engancha cualquier cosa. El sufijo
            # libre si conviene: "inflacion" tiene que encontrar "inflacionario".
            rx = [_rx(t, False) for t in nuestros]
            # Gana la que pega mas terminos distintos; entre iguales, la mas
            # nueva (idx ya viene ordenado de nueva a vieja).
            punt = 0
            for _, crudo, a in idx:
                n = sum(1 for r in rx if r.search(crudo))
                if n > punt:
                    mejor, punt = a, n
        if mejor is None:
            pw = palabras(p["publicacion"])
            punt = 0
            for aw, _, a in idx:
                n = len(pw & aw)
                if n > punt:
                    mejor, punt = a, n
            if punt < 3:
                mejor = None
            else:
                como = "  (emparejado por palabras: confirmar)"

        if mejor:
            print("        ultima nuestra: %s (%s)%s"
                  % (mejor["titulo"][:58], mejor["fecha"], como))
            print("        %s" % mejor["archivo"])
        else:
            print("        sin nota previa -> serie nueva")

    print("\n" + "=" * 78)
    print("*** prioridad alta   * media   |  fuentes:", ", ".join(cal["fuentes"]))
    print("La prioridad es preclasificacion editorial, no dato de la fuente.")

    imprimir_empresas(arts, idx, hoy, args.dias_empresas, args.dias)
    imprimir_pedidos(pedidos_pendientes())
    return 0


if __name__ == "__main__":
    sys.exit(main())
