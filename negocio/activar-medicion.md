> **ACTUALIZADO 24/09/2026: el sitio SI mide.** Cloudflare Web Analytics esta activo hace
> ~2 meses con inyeccion automatica desde el proxy (RUM, *Automatic setup*): no hizo falta
> tocar `metrics.js`. Se ve en dash.cloudflare.com -> Web Analytics, con *Exclude bots*.
> Primer corte, 30 dias: 540 visitas, 300 desde Google, 61% a una sola nota (Leonas/ENARD).
> Los numeros vienen muestreados (terminan en 0): leerlos como orden de magnitud.

# Activar la medicion del sitio

> Estado al 31/08/2026: el sitio **no mide nada**. Los includes ya estan puestos
> en las 110 paginas, asi que no hay que volver a tocar archivos: falta la
> cuenta con el proveedor, que la tiene que abrir Horacio.

Sin esto, todo el tablero de crecimiento esta en `s/d` y cualquier cosa que
agreguemos para que la audiencia participe es invisible: no vamos a saber si
funciono.

---

## Lo que ya esta hecho

- `assets/metrics.js` incluido en las 97 notas, las lecciones y las 12 paginas
  generadas. **Hoy no envia nada**: mientras `ENDPOINT` sea `null` se corta en
  la primera linea y no hace ninguna llamada de red.
- `scripts/inject_widgets.py` lo pone solo en cada nota nueva, sin duplicar.

## Lo que falta, y la trampa que hay que evitar

`metrics.js` manda un **POST con un JSON** (`{p, e, t}`) por `navigator.sendBeacon`.
El comentario dentro del archivo sugiere apuntarlo a GoatCounter
(`https://coninteres.goatcounter.com/count`), y **eso no funciona**: GoatCounter
espera un GET con parametros en la URL, no un POST con JSON. Descartaria en
silencio todo lo que le mandemos, y el tablero mostraria ceros que parecerian
datos. Lo mismo con Plausible y Cloudflare, que tienen cada uno su formato.

Hay dos caminos y conviene hacerlos en este orden.

---

## Camino A - volumen, 5 minutos, sin escribir codigo

Responde *cuanta gente llega, de donde y que lee*. Es la seccion 1 del tablero.

1. Entrar a Cloudflare (cuenta gratuita) → **Web Analytics** → *Add a site* →
   `coninteres.com`.
2. Copiar el snippet que da, que termina en un `token` de 32 caracteres.
3. Pasarme el token. Yo lo agrego al `<body>` de las plantillas de
   `build_portada.py` y a `inject_widgets.py`, y queda en todas las paginas.

No usa cookies, no necesita banner de consentimiento y no identifica a nadie:
es coherente con lo que dice `privacidad.html`.

**Lo que NO da:** scroll, tiempo de lectura, clicks al Modo Aprendizaje. Para
eso es el camino B.

---

## Camino B - interes, media hora, un Worker

Responde *si el contenido gusta*: es la seccion 2 del tablero, la que de verdad
distingue a un diario que se lee de uno que se abre y se cierra. Es lo que
`metrics.js` ya sabe medir y hoy no tiene a donde mandar.

Necesita un receptor que acepte el POST con JSON. Lo mas barato es un Cloudflare
Worker (plan gratis: 100.000 pedidos por dia, de sobra):

1. Horacio crea el Worker en el panel de Cloudflare y me pasa la URL
   (`https://<algo>.workers.dev`).
2. Yo escribo el Worker (unas 20 lineas: valida el origen, descarta lo que no
   sea de coninteres.com, y acumula) y pongo esa URL en `ENDPOINT`.
3. Decidir donde se guarda. Lo mas simple y lo mas barato es **no guardar nada
   crudo**: contadores agregados por dia y por evento en KV. Sin IP, sin
   user-agent, sin nada que identifique a una persona. Si guardamos menos,
   tampoco hay que explicar mas en `privacidad.html`.

> Ojo con el orden: **no** tiene sentido hacer B sin A. B mide el
> comportamiento de los que ya llegaron; A dice cuantos son. Con B solo, un
> numero alto de scroll al 75% puede ser una sola persona muy interesada.

---

## Lo que hay que actualizar cuando se active

- `negocio/tablero.md`: pasar de `s/d` a valores reales y marcarlos **[DATO]**.
- `privacidad.html`: decir que se mide, con que proveedor y que no hay cookies.
  Hoy la pagina promete que no medimos; si empezamos a medir, se corrige ahi
  antes de encender nada.
- El comentario enganoso de `assets/metrics.js` que menciona GoatCounter.

---

*Con Interes - este documento se borra el dia que la medicion este andando y el
tablero tenga numeros de verdad.*
