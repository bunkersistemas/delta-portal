# Mision 7 - La plata de los deportistas (serie en prueba)

**Objetivo:** dejar UN borrador de la serie en la cola. No publicar: si la
corrida la dispara la redaccion programada, publica el script.

Prueba aprobada por el editor el 11/10/2026: 4 notas en 2 semanas (12 al
25/10/2026), dos por semana. Manda `agente/NEWSROOM.md` (vara de la seccion 3 y
lineas rojas de 2 bis), sin excepciones: esta serie NO tiene una vara propia.

## Que es y que no es

Los diarios deportivos cuentan quien gano. Esta serie cuenta **la plata de las
personas que compiten**: cuanto cobra un deportista, cuanto le cuesta competir y
quien le paga. Es lo que trajo lectores: las becas del ENARD para Las Leonas y
cuanto cobra un campeon suramericano. Los premios que cobra un club, el
presupuesto general del deporte o la recaudacion de un partido NO son esta serie
(no los leyo nadie): el protagonista es una persona o un grupo de deportistas.

Ejemplos de preguntas:
- cuanto le cuesta a un atleta sin sponsor ir a un Mundial o a un Panamericano;
- cuanto cobra una jugadora o un jugador de primera division en un deporte
  amateur o semiprofesional (hockey, voley, basquet femenino, rugby);
- cuanto paga la beca del ENARD o de la Secretaria de Deportes a cada nivel, y
  cuanto compra hoy contra la inflacion;
- cuanto cobra un arbitro, un entrenador de seleccion juvenil, un deportista
  paralimpico;
- quien paga el viaje de una seleccion: la federacion, el Estado, los propios
  atletas (colectas).

## Pasos

1. Lee `data/cubiertas.json`: no repitas lo publicado (Leonas 30/08, campeon
   suramericano 25/09, presupuesto del deporte 10/10) sin un angulo nuevo.
2. Rastrea la agenda deportiva de la semana (torneos, convocatorias, viajes,
   reclamos de deportistas) y busca la pregunta de plata detras.
3. Arma 4 a 6 candidatas con su fuente primaria posible: resoluciones de becas
   (Boletin Oficial, ENARD, Secretaria de Deportes), presupuesto (Presupuesto
   Abierto), convenios colectivos o reglamentos de federaciones, balances de
   federaciones y de la AFA cuando esten publicados, reglamentos de premios
   olimpicos y panamericanos.
4. Toma la primera e investiga con la vara de la seccion 3: la cifra ancla
   CONFIRMADO por uno de los dos caminos. Lo que diga un deportista en una
   entrevista sirve como contexto atribuido, nunca como cifra ancla.
5. Si FRENA, registra el descarte y pasa a la siguiente (hasta 4).

## La nota

- `"seccion": "DEPORTES"` y **`"serie": "plata-deportistas"`** en
  `data/cola.json` (la serie es lo que cuenta el cupo y lo que mide el memo).
- Titulo: arranca con la persona y la cifra; la pregunta como la buscaria la
  gente va en `titulo_busqueda`. Correr `python scripts/titulares.py "<titulo>"`.
- Si la cifra es un monto en pesos, decir cuanto compra (contra la inflacion, la
  canasta o el salario minimo), como en la nota de Las Leonas.
- Registrar en `data/cubiertas.json` como en_cola y correr
  `python scripts/build_portada.py`. Los tres chequeos del editor de cierre.

## Prohibido

Correr aprobar.py o rechazar.py, usar git, tocar notas publicadas, kit social,
credenciales. Publicar sueldos o datos personales de una persona que no sean
publicos (un sueldo individual solo si sale de una norma o un documento
publico; si no, se cuenta la escala o el promedio).
