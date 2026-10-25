# Mision: cobertura especial - segunda vuelta en Brasil (25/10/2026)

Pedido del editor (24/10/2026): cobertura durante el domingo 25/10 de la segunda
vuelta presidencial en Brasil, entre **Lula (PT)** y **Flavio Bolsonaro (PL)**.
Cuatro notas en el dia sobre **lo que dicen las fuentes oficiales**, y que esta en
juego con los dos modelos. La dispara `redaccion_programada.ps1` cuando
`cobertura_especial.py` dice que hay un turno debido. Cada corrida escribe **la nota
de UN turno**.

Manda `agente/NEWSROOM.md` (secciones 1, 2 bis y 3). Esta mision agrega reglas; no
baja ninguna.

## Reglas de la cobertura

1. **Equilibrio estricto.** Los dos candidatos con el mismo tratamiento: mismo
   espacio, mismo tipo de fuente, sin adjetivos y sin calificar propuestas. Con
   Interes no apoya ni critica a ninguno. Lo que propone cada uno se atribuye a
   su documento ("segun el programa de gobierno registrado ante el TSE").
2. **Solo fuentes oficiales para los hechos electorales.** TSE (resultados,
   estadisticas del electorado, programas de gobierno registrados, comunicados),
   Agencia Brasil y Senado Noticias como lectura oficial. Para la economia:
   IBGE, Banco Central do Brasil, INDEC, BCRA, Cancilleria. Medios: solo para
   detectar el tema, nunca como fuente del dato.
3. **Nada de encuestas ni bocas de urna como resultado.** Una encuesta no es un
   dato oficial: no entra como cifra ni como titulo. Antes de que el TSE lo
   informe, no se anuncia ganador ni se "proyecta" nada.
4. **Todo resultado parcial lleva corte.** Porcentaje de urnas escrutadas y hora
   del corte del TSE, en el titulo o en la bajada, y la palabra "parcial".
5. **La cifra ancla sigue la seccion 3.** El resultado del escrutinio se publica
   **atribuido al TSE** (Campillay, 2 bis punto 5), no en voz propia. La cifra
   ancla de la nota puede ser un dato economico verificable (comercio
   bilateral INDEC, indicadores IBGE/BCB) que llegue a CONFIRMADO por alguno de
   los dos caminos. Si no llega, la nota se FRENA como cualquier otra.
6. **No repetir.** Antes de escribir, lee en `data/articulos.json` las notas con
   `"cobertura": "brasil-2026-*"` ya publicadas hoy: la nota nueva avanza, no
   repite. Si un turno anterior no salio, esta nota toma lo esencial de el.
7. **Hora de Brasilia = hora de Buenos Aires** (UTC-3). Las urnas cierran a las
   17:00.

## Los cuatro turnos

### Turno 1 - 09:00 - Que esta en juego
Los dos modelos economicos frente a frente, desde los **programas de gobierno
registrados ante el TSE** (DivulgaCandContas): impuestos, gasto, rol del Estado,
comercio exterior, Mercosur. El punto de partida de Brasil con datos oficiales
(IBGE: PIB, desempleo, IPCA; BCB: Selic, tipo de cambio). Y el puente argentino:
cuanto pesa Brasil para la Argentina (INDEC, intercambio comercial por pais:
exportaciones, importaciones, saldo; los rubros que mas dependen de Brasil, como
autos). Una tabla de dos columnas, una por candidato, mismos renglones.

### Turno 2 - 13:00 - Como vota Brasil
Padron oficial (TSE, estadisticas del electorado), voto obligatorio y su
sancion, urna electronica, horario y cuando se esperan resultados. La primera
vuelta del 04/10 en datos oficiales del TSE: votos de cada uno, participacion y
abstencion. Lo que haya informado el TSE durante la manana (comunicados).

### Turno 3 - 18:30 - Primeros resultados oficiales
Escrutinio del TSE (resultados.tse.jus.br) con el porcentaje de urnas y la hora
del corte. Comparacion con la primera vuelta. Si con lo escrutado el TSE ya
declaro ganador o el resultado esta matematicamente definido segun el TSE, se
dice; si no, la nota es "parcial" y no anuncia ganador.

### Turno 4 - 22:30 - El resultado y que significa para la Argentina
Resultado oficial del TSE (si a esa hora sigue sin definirse, el ultimo corte
con su porcentaje). Declaraciones oficiales on the record, enlazables (gobierno
argentino, Cancilleria), si las hay. Que significa para la Argentina segun el
programa de quien gano: comercio y saldo bilateral (INDEC), Mercosur y acuerdo
con la Union Europea, autos, energia. Los mercados abren el lunes: no se
anticipa lo que van a hacer.

## En data/cola.json

- `"seccion": "MUNDO"`
- `"cobertura": "brasil-2026-<n>"` con el numero del turno (**obligatorio**: es
  lo que marca el turno como hecho; sin eso la corrida siguiente lo repite).
- El titulo arranca con el dato o el hecho; la pregunta como la buscaria la
  gente va en `"titulo_busqueda"`.
