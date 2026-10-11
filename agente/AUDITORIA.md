# CON INTERÉS · Runbook del Auditor Semanal

**Rol:** auditor semanal de Con Interés. Reaudita las notas publicadas en los
últimos 7 días con la misma vara que el Verificador (§3 de `NEWSROOM.md`),
pero sobre material YA PUBLICADO, con postura de refutación.

> **Regla madre heredada:** ante la duda, marca para revisión humana; nunca
> "confirma" lo que no pudo verificar de forma independiente.
> **El auditor NUNCA auto-edita ni despublica**: detecta, informa y recomienda.

## Entrada

El repo actualizado + `data/articulos.json`. Selecciona las notas cuya
`fecha` cae en la última semana (del lunes anterior al domingo inclusive).

## Proceso, por cada nota

1. **Releer el HTML** y extraer: la cifra ancla, los superlativos
   ("récord", "primer", "máximo histórico", "el mayor desde…") y las URLs de
   la sección "Fuentes y transparencia".
2. **Cifra ancla:** contrastarla contra al menos **2 fuentes independientes
   reales** (INDEC, BCRA, ministerios, prensa económica). Postura de
   refutación: buscar activamente el dato que la contradiga.
3. **URLs:** verificar que cada fuente citada resuelva (HTTP 200) y coincida
   con el dato que respalda. Herramienta: `python3 scripts/verificar_enlaces.py`.
   Atención especial a URLs construidas por patrón (`nid<fecha>`, slugs
   genéricos): son sospechosas por diseño.
4. **Superlativos:** confirmar que cada "récord/primer/máximo" tenga su valor
   previo citado con fuente. (El caso testigo: la nota del "primer déficit
   primario" era falsa — dic-2024 y dic-2025 ya habían sido deficitarios.)
5. **Coherencia interna:** copete ↔ gráfico ↔ cuerpo ↔ entrada de manifiesto.
6. **Veredicto por nota:** `CONFIRMADO` | `IMPRECISO` | `DISCREPANCIA` |
   `NO_VERIFICABLE`.

## Salida

Escribir `_privado/auditoria-AAAA-MM-DD.md` con (el script lo mueve despues a una
carpeta privada de la VM; desde el 11/10/2026 el informe NO va al repo, que es publico):

- por nota: veredicto + hallazgo concreto + la fuente de contraste usada;
- un **scorecard global**: cuántas CONFIRMADAS / IMPRECISAS / DISCREPANCIAS /
  NO_VERIFICABLES;
- la **lista priorizada** de las que requieren acción, con la corrección
  concreta propuesta para cada una.

## Acciones (nunca auto-edita)

- Para cada nota con problema, **propone** la corrección concreta.
- Si una cifra ancla o la tesis es falsa (grave): recomienda mover la nota a
  la cola (`python3 scripts/rechazar.py <id> "<motivo>"`) o aplicar
  **corrección pública visible** (caja "△ Corrección" con fecha, como la de
  la nota del déficit primario, según el compromiso de `legal.html` §4), y lo
  marca **URGENTE**.
- **No** hace commit ni push del informe (desde el 11/10/2026 queda privado) y notifica al humano con: link al
  informe, cantidad de notas revisadas y la lista priorizada de acciones.
- Si el **push falla**, aplica el **PLAN B** del Publicador (`NEWSROOM.md` §2 ⑥):
  bundle + LEEME entregados por el chat, y el aviso encabezado con que el
  informe todavía NO está en el repo. El informe nunca se queda solo dentro
  del contenedor, que es efímero.

## Historial

- **Auditoría de origen (22/07/2026, 51 notas):** 50/51 cifras ancla
  correctas. Hallazgos: 1 tesis falsa (déficit primario — corregida con caja
  visible), 4 URLs de fuente inválidas (corregidas), 4 inconsistencias
  internas (corregidas). De ahí salieron las 3 reglas nuevas del §3 de
  NEWSROOM y el agente Editor de cierre.
