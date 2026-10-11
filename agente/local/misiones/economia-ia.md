# Mision 6 - La economia de la IA (una nota por semana)

**Objetivo:** dejar UN borrador de la seccion IA en la cola. No publicar: si la
corrida la dispara la redaccion programada, publica el script.

Manda `agente/NEWSROOM.md`, en especial la seccion **2 quinquies** (la vara
para un estudio) y las lineas rojas de 2 bis. Esta mision solo ordena los
pasos. Decision del editor del 11/10/2026.

## Que buscamos

Como la inteligencia artificial esta cambiando la economia del mundo y, sobre
todo, la de la Argentina, contado desde **investigaciones serias**: lo que
encontraron universidades y centros de conocimiento, traducido a una pregunta
de plata que le importe a un lector argentino (mi trabajo, mi sueldo, lo que
exporta el pais, donde se invierte, quien gana y quien pierde).

## 1. Rastreo de investigaciones (siempre, y anotar donde se busco)

Buscar con WebSearch y leer con WebFetch lo publicado en los ultimos ~6 meses,
priorizando lo mas reciente:

- **Universidades y centros del mundo:** NBER (working papers), MIT (Work of
  the Future, Shaping the Future of Work), Stanford (HAI, AI Index, Digital
  Economy Lab), Harvard, Brookings, Federal Reserve (bancos regionales),
  BIS, Bruegel, IZA.
- **Organismos con area de investigacion:** FMI (working papers y SDN), OIT
  (working papers sobre exposicion a la IA generativa), Banco Mundial, OCDE
  (AI policy observatory, employment outlook), CEPAL, BID.
- **Argentina y la region:** CEDLAS (UNLP), UBA (FCE, IIEP), Universidad Di
  Tella, Universidad de San Andres, Universidad Austral, CONICET, Fundar,
  CIPPEC, Fundacion Sadosky, CEP XXI (Ministerio de Economia), BCRA
  (documentos de trabajo), Observatorio de la economia del conocimiento.
- **Para encontrar el tema (no para citar):** secciones de tecnologia de los
  diarios, newsletters de economia, lo que discute la gente.

## 2. Candidatas

Armar 5 a 8 candidatas. Cada una con: el estudio (autores, institucion, ano,
URL del original), el hallazgo en una linea, y **el puente a la Argentina**:
que dato local permite contar que significa aca. Ordenar por:

1. Que el hallazgo responda una pregunta que la gente se hace ("la IA me va a
   sacar el trabajo?", "quien gana plata con esto?", "cuanto pagan los
   trabajos que la usan?").
2. Que haya un cruce argentino con datos oficiales (EPH por ocupacion, SIPA,
   exportaciones de servicios basados en conocimiento del INDEC, inversion).
3. Que sea nuevo o poco contado en castellano.

Descartar lo que ya esta en `data/cubiertas.json` como publicada o en_cola sin
un angulo nuevo. Las notas IA anteriores (2026-07-20 oficios, 2026-10-05
energia) no se repiten.

## 3. Investigacion y verificacion

Tomar la primera candidata y aplicar las cinco condiciones de NEWSROOM 2
quinquies: atribuida, leida en el original (PDF o pagina del centro, con
cuadro o pagina), con metodo y limites, con otro estudio al lado, y con el
cruce argentino verificado con la vara de la seccion 3. Si no llega a
CONFIRMADO, FRENA: registrar el descarte en `data/cubiertas.json` y pasar a la
siguiente, hasta 4 candidatas en la misma corrida.

## 4. La nota

- Plantilla de siempre (`agente/plantilla.html`), con noindex en `cola/`.
- En `data/cola.json`: `"seccion": "IA"` (obligatorio: es lo que cuenta como
  la nota de la semana) y `"formato": "Investigacion"`.
- **Titulo:** arranca con el hallazgo o el dato, dice de quien es ("Un estudio
  de ... encontro que ..."), sin sensacionalismo ni futurologia. La pregunta
  como la buscaria la gente va en `titulo_busqueda`. Correr
  `python scripts/titulares.py "<titulo>"`.
- **Cuerpo:** que encontraron, como lo midieron, que significa para la
  Argentina (con el dato local), que dice el otro estudio, y que no se sabe
  todavia.
- **Como lo sabemos (bloque 4 de la plantilla):** el camino de la seccion 2 quinquies, el original
  enlazado, el metodo, los limites y el estudio de contraste.
- Registrar en `data/cubiertas.json` como en_cola y correr
  `python scripts/build_portada.py`.
- Antes de terminar, los tres chequeos del editor de cierre (URLs 200,
  superlativos con valor previo, coherencia copete-graficos-cuerpo-manifiesto).

## Prohibido

Correr aprobar.py o rechazar.py, usar git, tocar notas publicadas, kit social,
credenciales. Presentar una proyeccion como hecho. Citar un paper que no se
leyo.
