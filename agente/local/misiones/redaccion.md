# Mision 1 - Corrida de redaccion

**Objetivo:** dejar UN borrador nuevo en la cola de revision. No publicar.
(Si la corrida la dispara la redaccion programada, el que publica es el script
y no vos; ver CLAUDE.md, regla 1.)

El metodo completo esta en `agente/NEWSROOM.md`. Leelo antes de arrancar: manda
en todo lo que sea criterio. Esta mision solo ordena los pasos.

## Antes de empezar

0. **Corre `python scripts/agenda.py`.** Es lo primero, y por eso la corrida ya
   no arranca en una pagina en blanco:
   - **El calendario oficial:** que publican el INDEC y el BCRA en los proximos
     dias, con fecha y hora, y cual fue nuestra ultima nota de esa misma serie.
     Si hay algo que sale HOY o MANANA con prioridad alta, ese es el candidato
     obvio: fuente primaria garantizada y serie previa para comparar.
     Si el calendario avisa que tiene mas de 20 dias, rehacelo antes:
     `python scripts/build_calendario.py`.
   - **Los pedidos de lectores (SUSPENDIDO, 01/09/2026):** el canal esta
     cerrado hasta que haya una casilla propia del medio o un formulario, asi
     que por ahora esta seccion no aparece. Cuando se reactive:
     **Un pedido es un candidato, nunca una orden** (NEWSROOM.md seccion 2 ter):
     lo elige el Editor con los mismos criterios y lo verifica el Verificador
     con el mismo protocolo. Su salida natural es una ficha; si tiene serie y
     contexto, una nota. Si lo tomas, marcalo `en_ficha` en `data/pedidos.json`
     para no volver a empezarlo, y al terminar dejalo `respondido` con la ruta
     en `salida` o `descartado` con el motivo escrito. Despues corre
     `python scripts/build_pedidos.py`.
1. Lee `data/cubiertas.json`. Es la memoria de temas: nada que figure ahi como
   `publicada` o `en_cola` se repite, salvo que tengas un angulo de datos
   genuinamente nuevo (y entonces explicas cual es la diferencia).
2. Lee `data/cola.json`. **Si ya hay un borrador esperando, avisale a Horacio y
   preguntale si quiere otro igual.** Acumular borradores sin revisar no ayuda.
3. Fijate la fecha. Si es la primera corrida del dia, al final vas a tener que
   actualizar `data/pregunta.json` (ver NEWSROOM.md seccion 4).

## La linea de montaje

Corre los seis agentes en cadena. La salida de cada uno es la entrada del que
sigue:

1. **Rastreador** - primero la agenda del paso 0: lo que sale del calendario
   oficial entra como candidato con ventaja. Despues releva lo mas destacado
   del momento en infobae, lanacion, clarin, ambito, iprofesional, cronista, tn
   y pagina12, priorizando lo que aparece repetido en varias portadas. Salida:
   8-12 candidatas, marcando cuales vienen del calendario.
2. **Editor** - elige UNA. Criterios en orden: riqueza de datos, relevancia para
   el lector argentino hoy, no repetir.
3. **Investigador** - va a las fuentes PRIMARIAS (INDEC, BCRA, Ministerio de
   Economia, Boletin Oficial, balances, bases internacionales), no a la nota que
   reboto el dato. Arma la ficha: cada numero con su URL exacta, su fecha, su
   unidad y si es definitivo, preliminar o estimado.
4. **Verificador** - intenta REFUTAR cada cifra, no confirmarla. Doble fuente
   independiente para la cifra ancla; un medio que reproduce el dato oficial no
   cuenta como segunda fuente. Etiqueta cada dato CONFIRMADO / ESTIMACION /
   NO_VERIFICADO y da un veredicto: APTA o FRENAR.
5. **Redactor** - escribe con la estructura de 6 capas sobre
   `agente/plantilla.html`. Graficos SVG propios desde el dato crudo. Cero
   imagenes de terceros.
6. **Editor de cierre** - antes de la cola, los tres chequeos: cada URL resuelve
   y respalda su dato; cada superlativo tiene su valor previo documentado;
   copete, grafico, cuerpo y manifiesto cierran entre si.

**Si el veredicto es FRENAR, la corrida termina sin nota.** Registralo en
`data/cubiertas.json` como descartada y decile a Horacio por que. Un dia sin
nota nueva es un buen dia si la alternativa era publicar algo flojo.

## Para cerrar

1. Escribi la nota en `cola/<AAAA-MM-DD-tema-en-kebab>.html`, con
   `<meta name="robots" content="noindex">` en el `<head>`.
2. Agrega la entrada a `data/cola.json` y registra el tema en
   `data/cubiertas.json` como `en_cola`.
3. Corre `python scripts/build_portada.py`.
4. Si la nota explica un movimiento del dolar, el riesgo pais o la inflacion,
   agrega la entrada en `data/eventos.json`.
5. Si es la primera corrida del dia, actualiza `data/pregunta.json`.
6. **NO generes kit social.** Esta suspendido por decision del editor.
7. Mostrale a Horacio: el titulo, la cifra ancla con su fuente, y la ruta del
   borrador para que lo lea. Una vez subido queda en
   `https://coninteres.com/cola/<id>.html`.

**No hagas el commit vos.** El script se encarga: al terminar te muestra que
cambio y le pregunta a Horacio si sube.
