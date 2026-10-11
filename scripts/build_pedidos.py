#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_pedidos.py - Genera pedidos.html desde data/pedidos.json.

La pagina publica del mecanismo de co-creacion: el lector manda una afirmacion
que no le cierra y la redaccion la verifica. La salida de un pedido atendido es
una ficha publica; si ademas tiene serie y contexto, una nota.

NO editar pedidos.html a mano: se regenera.

El canal, en orden de preferencia:
  1. FORM_EMBED - un formulario externo embebido (Google Forms, Tally...). Es lo
     mejor: el sitio es estatico y no tiene backend, y asi no se publica ninguna
     direccion.
  2. CORREO - una casilla PROPIA DEL MEDIO (pedidos@coninteres.com o similar).
     NUNCA la direccion personal del editor: esta pagina esta pensada para traer
     volumen y publicar ahi un correo personal es servirselo a los scrapers.
     Que la direccion figure en legal.html es otra cosa: ahi es el contacto
     legal obligatorio, no una llamada a la accion.
  3. Ninguno de los dos - la pagina muestra que el canal esta por abrir y manda
     a legal.html, que es donde vive el contacto formal.

Uso:  python scripts/build_pedidos.py
"""
import datetime
import io
import json
import os
from html import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Pegar aca la URL de embed del formulario (Tally, Formspree, Google Forms...).
# Vacio = la pagina usa el fallback por correo.
FORM_EMBED = ""

CORREO = "redaccion@coninteres.com"

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def en_castellano(iso):
    try:
        d = datetime.date.fromisoformat(iso)
    except (ValueError, TypeError):
        return iso or ""
    return "%d de %s de %d" % (d.day, MESES[d.month - 1], d.year)


def bloque_formulario():
    if FORM_EMBED:
        return ('<iframe class="formu" src="%s" loading="lazy" '
                'title="Formulario para pedir un chequeo"></iframe>' % escape(FORM_EMBED))
    asunto = "Pedido%20de%20chequeo"
    return """<div class="fallback">
    <p><b>Mandalo por correo, a
    <a href="mailto:{correo}?subject={asunto}">{correo}</a>.</b></p>
    <p>Con que pongas la afirmación tal cual la escuchaste alcanza. Si sabés de dónde salió
    —un programa, un diario, un posteo, un audio que te reenviaron— agregalo: nos ahorra la
    mitad del trabajo. Y decinos si querés que te acreditemos con tu nombre de pila y tu
    provincia, o si preferís que no aparezca nada.</p>
  </div>""".format(correo=CORREO, asunto=asunto)


def bloque_respondidos(pedidos):
    hechos = [p for p in pedidos if p.get("estado") == "respondido" and p.get("salida")]
    if not hechos:
        # Vacio a proposito: un contador en cero grita "sitio muerto". Cuando
        # haya el primero respondido, esta seccion aparece sola.
        return ""
    hechos.sort(key=lambda p: p.get("recibido", ""), reverse=True)
    filas = []
    for p in hechos:
        credito = ""
        if p.get("credito"):
            credito = '<span class="cred">Lo pidió %s</span>' % escape(p["credito"])
        filas.append(
            '<li><a class="ped-q" href="{salida}">{af}</a>'
            '<span class="ped-meta">{fecha}{sep}{cred}</span></li>'.format(
                salida=escape(p["salida"]),
                af=escape(p["afirmacion"]),
                fecha=en_castellano(p.get("recibido", "")),
                sep=" &#183; " if credito else "",
                cred=credito))
    return """
  <h2>Lo que ya chequeamos porque alguien lo pidió</h2>
  <ul class="pedidos">
    %s
  </ul>
""" % "\n    ".join(filas)


PLANTILLA = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pedí un chequeo — Con Interés</title>
<meta name="description" content="¿Escuchaste un número que no te cierra? Mandanoslo y lo verificamos contra la fuente primaria. Vos ponés la pregunta, nosotros el chequeo.">
<link rel="icon" type="image/svg+xml" href="assets/favicon.svg">
<link rel="canonical" href="https://coninteres.com/pedidos.html">
<meta name="robots" content="index,follow">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;0,8..60,700&family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root{{
    --paper:#FAF8F4;--ink:#16130F;--ink-soft:#3C3833;--teal:#0E7C86;--teal-deep:#0A5C63;
    --amber:#C4701F;--red:#C0392B;--muted:#6B6560;--faint:#8A847C;--rule:#DCD6CC;--grid:#E7E1D7;
    --card:#FFFFFF;--card-edge:#EAE4DA;
    --serif:"Source Serif 4",Georgia,serif;--sans:"Inter",system-ui,sans-serif;--mono:"IBM Plex Mono",monospace;
  }}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);line-height:1.65;-webkit-font-smoothing:antialiased}}
  .wrap{{max-width:720px;margin:0 auto;padding:0 22px}}
  a{{color:var(--teal-deep)}}
  .masthead{{border-bottom:2px solid var(--ink)}}
  .masthead .wrap{{display:flex;align-items:center;justify-content:space-between;height:56px;max-width:960px}}
  .brand{{font-family:var(--serif);font-weight:700;font-size:26px;display:flex;align-items:center;gap:8px;text-decoration:none;color:var(--ink)}}
  .brand .tri{{color:var(--teal)}}
  .brand .tag{{font-family:var(--mono);font-size:10px;color:var(--muted);letter-spacing:.14em;text-transform:uppercase;border-left:1px solid var(--rule);padding-left:8px;font-weight:500}}
  .mh-back{{font-family:var(--mono);font-size:12px;color:var(--teal-deep);text-decoration:none}}
  .kicker{{font-family:var(--mono);font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:var(--teal-deep);font-weight:600;margin:40px 0 14px}}
  h1{{font-family:var(--serif);font-weight:700;font-size:36px;line-height:1.15;margin:0 0 10px}}
  .sub{{font-family:var(--serif);font-size:19px;line-height:1.5;color:var(--ink-soft);margin:0 0 26px}}
  h2{{font-family:var(--serif);font-weight:700;font-size:22px;margin:38px 0 12px}}
  p,li{{font-size:16px;color:var(--ink-soft)}}
  ul{{padding-left:22px}}
  .caja{{background:var(--card);border:1px solid var(--card-edge);border-left:3px solid var(--teal);
    border-radius:10px;padding:20px 22px;margin:22px 0}}
  .caja h3{{font-family:var(--mono);font-size:11px;letter-spacing:.12em;text-transform:uppercase;
    color:var(--teal-deep);margin:0 0 10px;font-weight:600}}
  .caja p{{margin:0 0 10px;font-size:15.5px}}
  .caja p:last-child{{margin-bottom:0}}
  .fallback p{{font-size:16px}}
  .formu{{width:100%;min-height:520px;border:0;display:block}}
  .reglas{{background:#F3EFE7;border:1px solid var(--card-edge);border-left:3px solid var(--amber);
    border-radius:10px;padding:18px 22px;margin:24px 0}}
  .reglas h3{{font-family:var(--mono);font-size:11px;letter-spacing:.12em;text-transform:uppercase;
    color:var(--amber);margin:0 0 10px;font-weight:600}}
  .reglas li{{font-size:15px;margin-bottom:8px}}
  .reglas li:last-child{{margin-bottom:0}}
  .pasos{{list-style:none;padding:0;margin:18px 0 0;counter-reset:p}}
  .pasos li{{position:relative;padding-left:40px;margin-bottom:16px;font-size:15.5px}}
  .pasos li::before{{counter-increment:p;content:counter(p);position:absolute;left:0;top:1px;
    width:26px;height:26px;border-radius:50%;background:var(--teal);color:var(--paper);
    font-family:var(--mono);font-size:13px;font-weight:600;display:flex;align-items:center;justify-content:center}}
  .pedidos{{list-style:none;padding:0;margin:0}}
  .pedidos li{{border-top:1px solid var(--grid);padding:14px 0}}
  .pedidos li:last-child{{border-bottom:1px solid var(--grid)}}
  .ped-q{{display:block;font-family:var(--serif);font-size:18px;line-height:1.35;text-decoration:none;color:var(--ink)}}
  .ped-q:hover{{color:var(--teal-deep)}}
  .ped-meta{{display:block;font-family:var(--mono);font-size:11.5px;color:var(--faint);margin-top:5px}}
  .cred{{color:var(--teal-deep)}}
  footer{{border-top:2px solid var(--ink);margin-top:50px;padding:24px 0 60px}}
  footer .wrap{{font-family:var(--mono);font-size:12px;color:var(--muted)}}
  footer a{{text-decoration:none}}
  @media(max-width:600px){{ h1{{font-size:29px}} .sub{{font-size:17px}} }}
</style>
</head>
<body>

<header class="masthead">
  <div class="wrap">
    <a class="brand" href="index.html"><span class="tri">%</span>Con Interés<span class="tag">La economía, con interés</span></a>
    <a href="index.html" class="mh-back">← Portada</a>
  </div>
</header>

<div class="wrap">
  <div class="kicker">Con vos</div>
  <h1>Pedí un chequeo</h1>
  <p class="sub">¿Escuchaste un número que no te cierra? Mandanoslo. Vos ponés la pregunta,
  nosotros vamos a la fuente primaria y publicamos lo que encontramos — incluso cuando no
  nos gusta el resultado.</p>

  <div class="caja">
    <h3>&#9651; Qué mandar</h3>
    {formulario}
  </div>

  <h2>Cómo sigue tu pedido</h2>
  <ol class="pasos">
    <li>Tu pedido entra a la lista de temas que la redacción mira al empezar cada corrida,
    al lado del calendario del INDEC y del BCRA.</li>
    <li>Si tiene un dato duro atrás, sale una <b>ficha</b>: la afirmación de un lado, lo que
    dicen las fuentes del otro, con la tabla de datos completa y una sección de
    &laquo;lo que no cerró&raquo; donde va todo lo que no pudimos sostener.</li>
    <li>Si además tiene serie histórica y contexto, sale una <b>nota</b>.</li>
    <li>Si no llega, también te lo decimos: el pedido queda registrado como descartado, con
    el motivo escrito.</li>
  </ol>

  <div class="reglas">
    <h3>&#9651; Las reglas, para que no haya sorpresas</h3>
    <ul>
      <li><b>Publicamos el chequeo, no el pedido.</b> Tu pregunta nos dice qué mirar; qué se
      publica lo decide la redacción con los mismos criterios de siempre. Un pedido es un
      candidato, nunca una orden.</li>
      <li><b>No chequeamos personas, chequeamos números.</b> Nada sobre particulares que no
      sean figuras públicas, y ninguna acusación penal sin sentencia.</li>
      <li><b>No guardamos tus datos.</b> La lista de pedidos es pública y versionada, y ahí
      va solo la afirmación. Tu correo queda en la casilla del editor y no se publica.
      Tu nombre aparece únicamente si nos autorizás, y como nombre de pila y provincia.</li>
      <li><b>No respondemos todos.</b> Leemos todos; publicamos los que tienen dato duro
      atrás. Si la única fuente disponible es dudosa, se frena: preferimos no publicar antes
      que publicar un dato falso.</li>
      <li><b>Esto no es asesoramiento financiero ni médico.</b> Informamos y contextualizamos.
      No decimos qué comprar, qué vender ni qué invertir.</li>
    </ul>
  </div>
{respondidos}
  <h2>¿Encontraste un error en una nota?</h2>
  <p>Eso va por otro lado y es igual de bienvenido: está en
  <a href="legal.html">Aviso legal y correcciones</a>. Si el error se confirma, la nota se
  corrige y la corrección queda visible en la propia nota, con fecha — y con tu nombre, si
  querés que lo pongamos.</p>
</div>

<footer><div class="wrap">
  <div><a href="index.html">Portada</a> &#183; <a href="como-trabajamos.html">Cómo trabajamos</a>
  &#183; <a href="legal.html">Legal y correcciones</a> &#183; <a href="privacidad.html">Privacidad</a></div>
  <div style="margin-top:8px">Última actualización: {hoy}</div>
</div></footer>

</body>
</html>
"""


def main():
    ruta = os.path.join(ROOT, "data", "pedidos.json")
    datos = json.load(io.open(ruta, encoding="utf-8"))
    pedidos = datos.get("pedidos", [])

    html = PLANTILLA.format(
        formulario=bloque_formulario(),
        respondidos=bloque_respondidos(pedidos),
        hoy=en_castellano(datetime.date.today().isoformat()),
    )
    salida = os.path.join(ROOT, "pedidos.html")
    io.open(salida, "w", encoding="utf-8").write(html)

    por_estado = {}
    for p in pedidos:
        por_estado[p.get("estado", "?")] = por_estado.get(p.get("estado", "?"), 0) + 1
    detalle = ", ".join("%s %d" % (k, v) for k, v in sorted(por_estado.items())) or "sin pedidos"
    print("OK -> %s  (%d pedidos: %s)%s"
          % (salida, len(pedidos), detalle,
             "" if FORM_EMBED else "\n     [aviso] FORM_EMBED vacio: la pagina usa el fallback por correo."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
