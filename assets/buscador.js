/* ============================================================
   Con Interés · buscador.js
   Buscador del portal. Corre ENTERO en el navegador del lector:
   baja data/articulos.json (el mismo archivo que arma la portada)
   y busca ahí. No envía lo que se escribe a ningún servidor, no
   guarda búsquedas y no usa servicios de terceros.

   Dos partes en un solo archivo:
   - el motor (CIBuscar): normaliza, tolera tildes, plurales,
     errores de tipeo y sinónimos, y ordena por relevancia;
   - la lupa del encabezado, que se pone sola en todas las páginas
     (ticker.js carga este archivo).
   ============================================================ */
(function (root) {
  "use strict";

  /* ---------- motor ---------- */
  var VACIAS = {};
  ("de la el los las un una unos unas y o u e en a por para con sin que es son se su sus al del lo me mi hay " +
   "ser esta este esto estos estas como cuanto cuanta cuantos cuantas cual cuales quien quienes donde cuando " +
   "si no mas muy ya fue sobre entre hasta desde nos les le").split(" ").forEach(function (w) { VACIAS[w] = 1; });

  // Grupos de palabras que en una búsqueda quieren decir lo mismo. Un grupo suma
  // a la consulta, con menos peso, las otras palabras: "cuánto cobra" encuentra "sueldo".
  var GRUPOS = [
    ["gana", "cobra", "sueldo", "salario", "paga", "remuneracion", "ingreso", "haberes"],
    ["jubilacion", "jubilado", "jubilaciones", "jubilados", "haber", "pension", "anses"],
    ["dolar", "dolares", "blue", "mep", "cambio", "divisa", "cotizacion"],
    ["inflacion", "ipc", "precios", "indec", "aumento"],
    ["plata", "dinero", "pesos", "ahorro", "ahorrar"],
    ["credito", "prestamo", "deuda", "cuota", "hipotecario", "uva"],
    ["trabajo", "empleo", "laboral", "desempleo", "desocupacion"],
    ["impuesto", "impuestos", "tributo", "arca", "afip", "iva", "ganancias"],
    ["alquiler", "alquileres", "inquilino", "vivienda"],
    ["inversion", "invertir", "bono", "bonos", "accion", "acciones", "plazo", "fijo"],
    ["ia", "inteligencia", "artificial", "algoritmo", "tecnologia"],
    ["futbol", "deporte", "deportista", "atleta", "seleccion", "beca"]
  ];

  function normalizar(s) {
    return String(s == null ? "" : s).toLowerCase()
      .normalize("NFD").replace(/[̀-ͯ]/g, "")
      .replace(/[^a-z0-9]+/g, " ").trim();
  }

  function tokens(s, quitarVacias) {
    var t = normalizar(s).split(" ").filter(Boolean);
    return quitarVacias ? t.filter(function (w) { return !VACIAS[w]; }) : t;
  }

  function prefijoComun(a, b) {
    var n = Math.min(a.length, b.length), i = 0;
    while (i < n && a.charCodeAt(i) === b.charCodeAt(i)) i++;
    return i;
  }

  // distancia de edición con tope (para errores de tipeo); devuelve > tope si se pasa
  function distancia(a, b, tope) {
    if (Math.abs(a.length - b.length) > tope) return tope + 1;
    var prev = [], i, j;
    for (j = 0; j <= b.length; j++) prev[j] = j;
    for (i = 1; i <= a.length; i++) {
      var cur = [i], minFila = i;
      for (j = 1; j <= b.length; j++) {
        var c = a.charCodeAt(i - 1) === b.charCodeAt(j - 1) ? 0 : 1;
        cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + c);
        if (cur[j] < minFila) minFila = cur[j];
      }
      if (minFila > tope) return tope + 1;
      prev = cur;
    }
    return prev[b.length];
  }

  // 1 = misma palabra, .8 = misma raíz / empieza igual, .55 = error de tipeo, 0 = nada
  function parecido(q, d) {
    if (q === d) return 1;
    var lq = q.length, ld = d.length, cp = prefijoComun(q, d);
    if (lq >= 3 && d.indexOf(q) === 0) return .85;               // escribiendo: "jubil" -> "jubilacion"
    var mn = Math.min(lq, ld);
    if (cp >= 4 && cp === mn) return .8;                                // plural, conjugación: dolar/dolares, gana/ganan
    if (cp >= 6 && cp >= mn - 3) return .8;                            // misma familia: jubilados/jubilaciones
    if (lq >= 5 && distancia(q, d, lq >= 9 ? 2 : 1) <= (lq >= 9 ? 2 : 1)) return .55;
    return 0;
  }

  var CAMPOS = [["titulo", 6], ["titulo_busqueda", 5], ["bajada", 2], ["seccion", 2], ["formato", 2], ["numero_label", 1.2]];

  // arma el índice una vez: por nota, las palabras únicas de cada campo
  function indexar(articulos) {
    return articulos.map(function (a) {
      var campos = CAMPOS.map(function (c) {
        var texto = a[c[0]];
        var seen = {}, lista = [];
        tokens(texto, true).forEach(function (w) { if (!seen[w]) { seen[w] = 1; lista.push(w); } });
        return { peso: c[1], palabras: lista };
      });
      return { a: a, campos: campos, tituloNorm: normalizar(a.titulo) + " " + normalizar(a.titulo_busqueda) };
    });
  }

  // palabras que en una búsqueda quieren decir lo mismo que `q` (sin incluirla)
  function sinonimos(q) {
    var extra = {};
    GRUPOS.forEach(function (g) {
      if (g.some(function (w) { return parecido(q, w) >= .8; })) g.forEach(function (w) { if (w !== q) extra[w] = 1; });
    });
    return Object.keys(extra);
  }

  function mejorEnDoc(q, doc) {
    var mejor = 0;
    doc.campos.forEach(function (c) {
      c.palabras.forEach(function (w) {
        var p = parecido(q, w);
        if (p) { var v = p * c.peso; if (v > mejor) mejor = v; }
      });
    });
    return mejor;
  }

  // Cada palabra de la consulta pesa según lo rara que es en el sitio: "leonas" (3 notas) manda
  // sobre "ganan" (decenas). Una palabra se da por cubierta si está, o si está un sinónimo (a 60%).
  function buscar(indice, consulta) {
    var qt = tokens(consulta, true);
    if (!qt.length) qt = tokens(consulta, false);
    if (!qt.length) return [];
    var N = indice.length, frase = normalizar(consulta);
    var sins = qt.map(sinonimos);
    var filas = indice.map(function (doc) {
      return qt.map(function (q, i) {
        var m = mejorEnDoc(q, doc);
        if (m > 0) return { m: m, directa: true };
        var s = 0;
        sins[i].forEach(function (w) { var v = mejorEnDoc(w, doc); if (v > s) s = v; });
        return s > 0 ? { m: s * .6, directa: false } : null;
      });
    });
    var idf = qt.map(function (q, i) {
      var df = filas.reduce(function (n, f) { return n + (f[i] && f[i].directa ? 1 : 0); }, 0);
      return Math.log(1 + N / (1 + df));
    });
    var total = idf.reduce(function (x, y) { return x + y; }, 0);
    var out = [];
    indice.forEach(function (doc, d) {
      var cub = 0, puntos = 0, directas = 0;
      filas[d].forEach(function (c, i) {
        if (!c) return;
        cub += idf[i]; puntos += c.m * idf[i]; if (c.directa) directas++;
      });
      if (!directas) return;                        // al menos una palabra tiene que estar tal cual
      var cobertura = cub / total;
      if (cobertura < .6) return;
      puntos *= 1 + cobertura;
      if (frase.length >= 6 && doc.tituloNorm.indexOf(frase) >= 0) puntos *= 1.6;
      out.push({ a: doc.a, puntos: puntos, cobertura: cobertura });
    });
    // si ya hay varias notas que cubren toda la consulta, las que cubren solo una parte sobran
    var completas = out.filter(function (r) { return r.cobertura >= .95; });
    if (completas.length >= 3 || (qt.length > 1 && completas.length >= 1)) out = completas;
    out.sort(function (x, y) {
      if (y.puntos !== x.puntos) return y.puntos - x.puntos;
      return String(y.a.fecha || "").localeCompare(String(x.a.fecha || ""));
    });
    return out;
  }

  var CIBuscar = { normalizar: normalizar, tokens: tokens, indexar: indexar, buscar: buscar, parecido: parecido };
  root.CIBuscar = CIBuscar;
  if (typeof module !== "undefined" && module.exports) module.exports = CIBuscar;

  /* ---------- la lupa del encabezado ---------- */
  function ponerLupa() {
    try {
      if (!root.document || document.getElementById("ci-lupa")) return;
      if (/(^|\/)buscar\.html$/.test(location.pathname)) return;
      var brand = document.querySelector(".masthead .brand");
      if (!brand) return;
      var href = (brand.getAttribute("href") || "index.html");
      if (href.charAt(0) === "#") href = "index.html";
      var destino = href.replace(/index\.html.*$/, "") + "buscar.html";
      var estilo = document.createElement("style");
      estilo.textContent =
        "#ci-lupa{margin-left:auto;margin-right:14px;display:inline-flex;align-items:center;gap:6px;" +
        "font:600 12px/1 'IBM Plex Mono',monospace;letter-spacing:.06em;text-transform:uppercase;" +
        "color:#0A5C63;text-decoration:none;padding:8px 10px;border:1px solid #DCD6CC;border-radius:999px;background:#fff;white-space:nowrap}" +
        "#ci-lupa:hover,#ci-lupa:focus-visible{border-color:#0E7C86;color:#16130F}" +
        "#ci-lupa svg{width:15px;height:15px}" +
        "@media(max-width:560px){#ci-lupa span{display:none}#ci-lupa{padding:8px;margin-right:8px}}";
      document.head.appendChild(estilo);
      var a = document.createElement("a");
      a.id = "ci-lupa"; a.href = destino; a.setAttribute("aria-label", "Buscar en el sitio");
      a.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true">' +
                    '<circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5 21 21"/></svg><span>Buscar</span>';
      brand.parentNode.insertBefore(a, brand.nextSibling);
    } catch (e) { /* la lupa es un extra: nunca rompe la página */ }
  }
  if (root.document) {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", ponerLupa);
    else ponerLupa();
  }
})(typeof window !== "undefined" ? window : this);
