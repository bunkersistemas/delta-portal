# Contexto de trabajo - Con Interes (agente local)

> Este archivo es el manual del agente. Explica **que es este proyecto, que
> hacemos juntos y con que reglas**. El agente lo lee al empezar cada sesion.
>
> Los textos estan en ASCII (sin tildes) a proposito: evita problemas de
> codificacion cuando el agente genera archivos y comandos en Windows. **Las
> notas del sitio SI llevan tildes** - la regla ASCII es solo para los archivos
> de trabajo del agente (manual, misiones, scripts).

---

## 1. Que es esto y que hace el agente

**Con Interes** (coninteres.com) es un diario digital argentino de datos. Una
redaccion de agentes de IA rastrea las noticias, verifica cada cifra contra la
fuente primaria y escribe notas con profundidad. **Ninguna nota se publica sola:
Horacio revisa y aprueba cada una.**

El agente **asiste a Horacio**: rastrea, verifica, redacta, prepara y muestra.
**Horacio decide.** El agente nunca da por buena una cifra dudosa para "avanzar
mas rapido".

> **Regla madre:** Con Interes prefiere no publicar antes que publicar un dato
> falso. La confianza es el unico activo de un diario de datos. Ante la duda, se
> frena.

**El metodo editorial completo esta en `agente/NEWSROOM.md`.** Ese archivo manda
en todo lo que sea criterio periodistico: la linea de montaje de 6 agentes, el
protocolo de verificacion, el marco legal, el formato de las notas. Este manual
que estas leyendo cubre solo **como se opera desde la maquina de Horacio**.

### Por que existe la version local

Hasta agosto de 2026 la redaccion corria en sesiones en la nube, y ahi el `git
push` fallaba con `403`: el proxy del entorno no inyecta credencial para repos
que no esten autorizados en las *sources* de la sesion. Resultado: la nota se
escribia bien y despues habia que rescatarla con un `git bundle`.

**Corriendo desde esta maquina eso desaparece.** El push usa las credenciales de
git de Horacio y sale directo. Es la razon principal de que este agente exista.

---

## 2. La primera vez - hacelo en este orden

**Hace doble clic en `Agente.bat`** (esta en la raiz de esta carpeta). El script
chequea solo todo lo que hace falta y te dice, en castellano, que falta si falta
algo. No necesitas escribir ningun comando.

Lo que el script verifica antes de arrancar:

| # | Que | Como lo arregla si falta |
|---|---|---|
| **1** | **git** | Te manda a https://git-scm.com/download/win |
| **2** | **Python 3** | Te manda a https://www.python.org/downloads/ - **marca "Add Python to PATH"** en la instalacion |
| **3** | **Claude Code** | Te da el comando: `npm install -g @anthropic-ai/claude-code` |
| **4** | **El repo actualizado** | Corre `git pull` solo |

> **Si algo falla, el mensaje te dice que hacer.** Estan escritos para eso. Si
> igual no se entiende, copiaselo entero a Claude en una sesion de Cowork.

**La primera vez que corras Claude Code te va a pedir iniciar sesion.** Es una
sola vez: despues queda guardado en la maquina.

---

## 3. Las misiones

El menu de `Agente.bat` tiene seis opciones. Cada una carga una mision distinta
desde `agente/local/misiones/`. El agente lee el archivo de la mision y trabaja
sobre el.

| # | Mision | Que hace | Termina en |
|---|---|---|---|
| **1** | **Conversar** | La puerta de entrada. Te da el estado del dia en seis lineas, te propone dos o tres cosas concretas y espera. Le pedis lo que necesites en castellano y el rutea a la mision que corresponda | Lo que hayas pedido |
| **2** | **Corrida de redaccion** | La linea de montaje de NEWSROOM.md: rastrea, elige tema, investiga en fuentes primarias, verifica, escribe la nota | Un **borrador en `cola/`**. Solo la redaccion programada lo publica sola, y con controles (regla 1) |
| **3** | **Revisar y publicar** | Lista los borradores que esperan, te muestra el que elijas, y si aprobas corre `aprobar.py` | La nota **publicada** en el sitio |
| **4** | **Ficha de investigacion** | Le das un tema o un link y devuelve una ficha con datos verificados, fuentes, etiquetas y graficos | Un archivo en **`fichas/`** |
| **5** | **Cambios al sitio** | Modificaciones de fondo: plantilla, scripts de build, paginas nuevas | Cambios en el repo, para revisar |
| **6** | **Estado del sitio** | Que hay en la cola, ultimas notas, si el repo esta al dia | Solo informacion, no toca nada |

**La opcion 1 es la que vas a usar casi siempre.** Las otras son atajos para
cuando ya sabes exactamente que queres hacer y no tenes ganas de explicarlo.

---

## 4. Reglas que el agente NO rompe

Estas no son de estilo. Si el agente esta por hacer una de estas cosas, frena y
pregunta.

1. **No publica sin aprobacion, salvo la redaccion programada.** La corrida de
   redaccion deja el borrador en `cola/`, siempre. De ahi a `articulos/` hay
   dos caminos, y solo dos:
   - **Horacio aprueba** una nota de la cola (mision 3).
   - **La redaccion programada** (`agente/local/redaccion_programada.ps1`, cada
     hora, autorizada por el editor el 23/09/2026) la publica sola si el
     agente declaro APTA y el script confirma los controles mecanicos: entrada
     en `cola.json`, cifra ancla, `noindex`, fuentes que responden y ningun
     archivo tocado fuera del sitio. Cada publicacion le llega a Horacio por
     Gmail.
   En los dos casos el agente de redaccion nunca corre `aprobar.py` ni git por
   su cuenta. En una sesion interactiva, no se publica sin que Horacio diga que
   si. La vara de verificacion es la misma: la automatizacion no la baja.
2. **No commitea sin mostrar.** Antes de cualquier commit muestra `git status` y
   la lista de archivos tocados, y espera confirmacion.
3. **Nunca pone credenciales en la URL del remoto.** Ni un PAT, ni un token, ni
   en un comando ni en un archivo. Git ya tiene las credenciales de la maquina.
   (Esto viene de un incidente real: en agosto de 2026 hubo un PAT escrito en
   texto plano dentro del prompt de dos tareas programadas, legible por
   cualquier sesion que listara los triggers.)
4. **No edita `index.html` ni `hoy.html` a mano.** Se generan solos con
   `python scripts/build_portada.py` desde los manifiestos de `data/`.
5. **No inventa una cita.** Solo declaraciones on-the-record, enlazables, con
   fuente identificada. Ante la duda, no va.
6. **No usa imagenes de terceros.** Todos los graficos son SVG propios armados
   desde el dato crudo.
7. **No recomienda inversiones.** Informar y explicar, si. "Compra esto", jamas:
   el asesoramiento financiero esta reservado a agentes registrados ante la CNV.
8. **Si una cifra no llega a CONFIRMADO, no entra.** Y si la cifra ancla no
   llega, la nota se frena entera. Un dia sin nota nueva es mejor que una nota
   con un dato falso.

---

## 5. Donde vive cada cosa

```
index.html              portada: LINEA DE TIEMPO por dia (GENERADA - no editar
                        a mano). Cada dia es un nodo; dentro del dia manda la
                        nota con "destacada": true y si no la primera. El
                        detalle se degrada con la antiguedad: 3 dias con
                        tarjeta grande, hasta 7 con tarjetas, el resto solo
                        filas. Tope de 6 notas por dia; el resto enlaza a
                        archivo.html#d-AAAA-MM-DD. Arriba de todo va LA NOTA
                        DEL DIA: la destacada del dia mas reciente sale de la
                        linea y encabeza la portada con su rotulo; el nodo de
                        hoy lista el resto y dice "N notas mas". Debajo, el
                        semaforo economico en franja de 5 columnas. Debajo
                        del bloque de hoy va LA PREGUNTA DEL DIA, que hasta el
                        31/08/2026 solo se alcanzaba por el nav y casi nadie
                        veia. La logica (respuesta correcta, racha) esta en
                        assets/pregunta.js, compartida con pregunta.html para
                        que no puedan divergir; la racha vive solo en el
                        navegador del lector.
                        build_portada.py acepta CI_VARIANTE (lead / compacta /
                        actual) para generar maquetas sin pisar index.html.
hoy.html                "El cierre" (GENERADA - no editar a mano)
seccion-<id>.html       una pagina por seccion, paginada de a 20 (GENERADAS)
                        seccion-tu-plata.html, -2.html, -3.html... Las notas
                        viejas ya no se pliegan en la portada: viven aca.
                        Grupos: tu-plata, el-pais, los-mercados, tu-provincia,
                        el-mundo y deportes.
feed.xml                RSS 2.0 de las ultimas 30 notas (GENERADO por
                        scripts/build_feed.py). Cada item lleva la tarjeta de
                        la nota como enclosure y su cifra ancla en <ci:numero>.
                        Es lo que permite automatizar la distribucion en redes
                        SIN escribir un bot y SIN poner credenciales en ningun
                        lado: se enchufa a un programador de posteos y queda un
                        paso de revision humana antes de publicar.
herramientas.html       calculadoras del bolsillo. La primera, "tu canasta",
                        repondera el IPC con el gasto del lector y le devuelve
                        SU inflacion. Es co-creacion: el lector no espera una
                        investigacion, obtiene un numero propio al instante.
                        Todo corre en el navegador; no se guarda nada.
archivo.html            todas las notas por DIA, cronologico (GENERADA). Es
                        el destino de los enlaces "ver las otras N del dia".
articulos/              notas publicadas
cola/                   borradores esperando aprobacion
fichas/                 fichas de investigacion (mision 4, no se publican)
lecciones/              Modo Aprendizaje
data/                   manifiestos JSON - la fuente de verdad
  articulos.json          notas publicadas
  cola.json               borradores en cola
  cubiertas.json          memoria de temas (anti-duplicados)
  pregunta.json           la pregunta del dia
  pedidos.json            PEDIDOS DE LECTORES - SUSPENDIDO (01/09/2026). El
                          mecanismo esta completo pero sin canal de entrada:
                          falta una casilla propia del medio o un formulario.
                          pedidos.html se dio de baja y el link salio del nav.
                          Ver NEWSROOM.md seccion 2 ter para reactivarlo. Un
                          pedido es un CANDIDATO, nunca una orden. Archivo
                          publico y versionado: NO se guarda contacto de nadie.
  calendario.json         QUE PUBLICAN INDEC Y BCRA en los proximos 120 dias,
                          con fecha y hora oficiales. GENERADO por
                          scripts/build_calendario.py desde los calendarios de
                          difusion de cada organismo. Ninguna fecha se estima.
  empresas.json           LO QUE PRESENTARON LAS EMPRESAS ante la CNV (hechos
                          relevantes) y la SEC (argentinas que cotizan en
                          EE.UU.), mas las fechas de balance que ellas mismas
                          anunciaron. GENERADO por scripts/build_empresas.py,
                          que ACUMULA: la pagina de la CNV muestra solo los
                          ultimos 50. Es la segunda agenda, desde el
                          25/09/2026 (NEWSROOM.md 2 quater).
  eventos.json            anotaciones de las fichas de indicador
  ipc-divisiones.json     las DOCE DIVISIONES del IPC nacional (indice mensual)
                          mas sus ponderadores nacionales. GENERADO por
                          scripts/build_ipc_divisiones.py. Alimenta la
                          calculadora "tu canasta" de herramientas.html.
                          Rehacerlo cuando sale el IPC (dia 10 y pico).
agente/NEWSROOM.md      el runbook editorial - MANDA en criterio
agente/plantilla.html   plantilla de nota (estructura de 6 capas)
agente/local/           el agente local: script, misiones, LEEME
scripts/                build_portada.py, aprobar.py, rechazar.py, ...
  build_tarjetas.py       una tarjeta de compartir por nota (1200x630) con su
                          CIFRA ANCLA, en assets/tarjetas/<id>.png. Es la imagen
                          con la que la nota circula en X y WhatsApp. La genera
                          aprobar.py sola al publicar; para rehacer todo el
                          archivo: python scripts/build_tarjetas.py --forzar
  build_calendario.py     rehace data/calendario.json desde INDEC y BCRA
  agenda.py               que sale en los proximos dias + nuestra ultima nota
                          de esa misma serie, y el bloque EMPRESAS. Es el
                          paso 0 de toda corrida.
  build_empresas.py       rehace data/empresas.json desde la CNV y la SEC
negocio/                tablero de crecimiento y metricas
```

**Los manifiestos de `data/` son sagrados.** Cada corrida en la nube era una
sesion sin memoria, y lo unico que quedaba entre corridas era lo escrito ahi.
Se leen al empezar y se actualizan al terminar.

---

## 6. Lo que esta pendiente (contexto util para el agente)

- **La medicion del sitio no esta instalada.** `negocio/tablero.md` lo dice:
  Cloudflare Web Analytics no tiene beacon en ninguna pagina y
  `assets/metrics.js` sigue con `ENDPOINT=null`. Por eso todo el tablero de
  trafico esta en `s/d`. Es gratis de arreglar y es lo primero que conviene
  hacer antes de invitar a nadie a escribir en el sitio.
- **El kit social esta suspendido** por decision del editor (22/07/2026). No
  generar `kits/<id>.md` en las corridas.
- **`data/pregunta.json` se toca una sola vez por dia**, en la primera corrida.
- **El flujo de notas es a rafagas, no constante.** Entre el 18/07 y el
  31/08/2026 hubo notas en 14 de 45 dias: el 69% del periodo no publico nada,
  con un apagon de 24 dias en agosto. No es falta de capacidad (el mejor dia
  produjo 23 notas) sino falta de disparador y de colchon: nada arranca si
  Horacio no hace doble clic, y la cola esta siempre en cero. El calendario de
  publicaciones oficiales (`data/calendario.json`, 31/08/2026) ataca la mitad
  del problema: la corrida ya no arranca en blanco. La otra mitad, el
  disparador, es la redaccion programada (23/09/2026, ver abajo).
- **La redaccion automatica en la nube esta suspendida** desde el 31/08/2026:
  la tarea que corria cada 2 horas ya no genera borradores. La unica redaccion
  activa es la de esta maquina, asi que ya no hay riesgo de dos borradores del
  mismo dia compitiendo por el mismo tema. Sigue en pie la auditoria de los
  lunes a las 7, que no genera notas.
- **La redaccion programada corre en esta maquina** desde el 23/09/2026: la
  tarea "Con Interes - Redaccion programada" dispara
  `agente/local/redaccion_programada.ps1` cada hora, con una corrida a las
  16:30 de Buenos Aires (media hora despues de INDEC y BCRA). Se activa con
  `ACTIVAR_REDACCION.ps1` y se apaga con
  `Disable-ScheduledTask -TaskName 'Con Interes - Redaccion programada'`.
  No corre si hay cambios sin commitear o borradores en la cola, asi que no
  pisa el trabajo de una sesion interactiva. Log en
  `%USERPROFILE%\coninteres-logs\redaccion_<fecha>.log`. La mayoria de las
  corridas deberian terminar sin nota: es lo esperado.

---

*Con Interes - La economia, con interes. Este manual evoluciona: cada vez que
cambie el modo de trabajo local, se actualiza aca.*
