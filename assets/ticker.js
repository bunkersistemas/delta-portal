/* ============================================================
   Con Interés · ticker.js
   Ticker de indicadores (dólar oficial/blue/MEP, riesgo país,
   inflación mensual) con PANEL HISTÓRICO: clic en un indicador
   despliega su serie de 6 / 12 / 18 / 24 meses, con gráfico
   propio (SVG) y tooltip. Datos de APIs públicas.
   Se incluye con:  <script defer src="assets/ticker.js"></script>

   NOTA: el sitio NO tiene newsletter ni captura de emails por
   decisión editorial (cero fricción para el lector).
   ============================================================ */
(function () {
  "use strict";

  var TICKER_CACHE_KEY = "ci_ticker_v2";
  var TICKER_TTL_MS = 10 * 60 * 1000; // 10 minutos
  var HIST_TTL_MS = 60 * 60 * 1000;   // 1 hora para series históricas

  /* ---------- catálogo de series ---------- */
  var SERIES = {
    oficial:   { label: "Dólar oficial", tipo: "linea", unidad: "$",
                 hist: "https://api.argentinadatos.com/v1/cotizaciones/dolares/oficial",
                 sub: "venta, en pesos por dólar" },
    blue:      { label: "Dólar blue", tipo: "linea", unidad: "$",
                 hist: "https://api.argentinadatos.com/v1/cotizaciones/dolares/blue",
                 sub: "venta, en pesos por dólar" },
    mep:       { label: "Dólar MEP", tipo: "linea", unidad: "$",
                 hist: "https://api.argentinadatos.com/v1/cotizaciones/dolares/bolsa",
                 sub: "venta, en pesos por dólar" },
    riesgo:    { label: "Riesgo país", tipo: "linea", unidad: "pb",
                 hist: "https://api.argentinadatos.com/v1/finanzas/indices/riesgo-pais",
                 sub: "EMBI+ Argentina, en puntos básicos" },
    inflacion: { label: "Inflación mensual", tipo: "barras", unidad: "%",
                 hist: "https://api.argentinadatos.com/v1/finanzas/indices/inflacion",
                 sub: "variación mensual del IPC (INDEC), en %" }
  };
  var MES = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"];
  var FICHA = { oficial: "dolar-oficial", blue: "dolar-blue", mep: "dolar-mep", riesgo: "riesgo-pais", inflacion: "inflacion" };

  // raíz del sitio, derivada de la URL de este script (portada, /articulos,
  // /lecciones e /indicador por igual)
  var SITE_BASE = (function () {
    try {
      var s = document.querySelector('script[src*="ticker.js"]');
      return s ? s.src.replace(/assets\/ticker\.js.*$/, "") : "";
    } catch (e) { return ""; }
  })();

  /* ---------- estilos (autocontenidos) ---------- */
  var css = ""
    + ".ci-ticker{background:#16130F;border-bottom:1px solid #2E2A25;overflow:hidden}"
    + ".ci-ticker .ci-tk-in{max-width:1080px;margin:0 auto;padding:8px 24px;display:flex;gap:14px;align-items:center;flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch}"
    + ".ci-ticker .ci-tk-in::-webkit-scrollbar{display:none}"
    + ".ci-tk-item{display:flex;align-items:baseline;gap:7px;font-family:'IBM Plex Mono',ui-monospace,monospace;font-size:12px;white-space:nowrap;flex:0 0 auto;background:none;border:1px solid #3E3A34;padding:4px 11px;cursor:pointer;border-radius:999px;transition:.15s}"
    + ".ci-tk-item:hover{background:#2E2A25;border-color:#4FC0A4}"
    + ".ci-tk-item .k{color:#A39D93;letter-spacing:.04em}"
    + ".ci-tk-item .v{color:#fff;font-weight:600}"
    + ".ci-tk-item .caret{color:#8A847C;font-size:9px;transform:translateY(-1px)}"
    + ".ci-tk-item.open{background:#2E2A25;border-color:#4FC0A4}.ci-tk-item.open .caret{color:#4FC0A4}"
    + ".ci-tk-btn{margin-left:auto;flex:0 0 auto;position:sticky;right:0;display:flex;align-items:center;gap:7px;font-family:'IBM Plex Mono',ui-monospace,monospace;font-size:12px;font-weight:600;letter-spacing:.03em;background:#C4701F;color:#fff;border:none;border-radius:999px;padding:6px 14px;cursor:pointer;transition:background .15s;white-space:nowrap;box-shadow:-14px 0 14px rgba(22,19,15,.85)}"
    + ".ci-tk-btn:hover{background:#E8833A}"
    + ".ci-tk-btn .caret{font-size:9px}"
    /* panel histórico */
    + ".ci-hist{background:#FAF8F4;border-bottom:2px solid #16130F;display:none}"
    + ".ci-hist.abierto{display:block}"
    + ".ci-hist .ci-h-in{max-width:1080px;margin:0 auto;padding:18px 24px 20px}"
    + ".ci-h-top{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;margin-bottom:4px}"
    + ".ci-h-tit{font-family:'Source Serif 4',Georgia,serif;font-size:20px;font-weight:700;color:#16130F}"
    + ".ci-h-last{font-family:'IBM Plex Mono',monospace;font-size:16px;font-weight:600;color:#0A5C63}"
    + ".ci-h-var{font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600}"
    + ".ci-h-var.up{color:#C0392B}.ci-h-var.dn{color:#2E8B6F}"
    + ".ci-h-cerrar{margin-left:auto;background:none;border:1px solid #DCD6CC;border-radius:999px;font-family:'IBM Plex Mono',monospace;font-size:11px;color:#6B6560;padding:4px 12px;cursor:pointer}"
    + ".ci-h-cerrar:hover{border-color:#16130F;color:#16130F}"
    + ".ci-h-sub{font-size:12px;color:#6B6560;margin:0 0 12px;font-family:'IBM Plex Mono',monospace}"
    + ".ci-h-rangos{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap}"
    + ".ci-h-rango{font-family:'IBM Plex Mono',monospace;font-size:11px;font-weight:600;letter-spacing:.05em;background:#fff;border:1px solid #EAE4DA;color:#6B6560;border-radius:999px;padding:5px 13px;cursor:pointer;transition:.15s}"
    + ".ci-h-rango:hover{border-color:#0E7C86}"
    + ".ci-h-rango.activo{background:#16130F;color:#fff;border-color:#16130F}"
    + ".ci-h-chart{background:#fff;border:1px solid #EAE4DA;border-radius:12px;padding:14px 12px 8px}"
    + ".ci-h-chart svg{width:100%;height:auto;display:block;overflow:visible}"
    + ".ci-h-fuente{font-family:'IBM Plex Mono',monospace;font-size:10px;color:#8A847C;margin-top:8px}"
    + ".ci-h-estado{font-family:'IBM Plex Mono',monospace;font-size:12px;color:#6B6560;padding:30px 0;text-align:center}"
    + ".ci-h-tt{position:fixed;pointer-events:none;background:#16130F;color:#fff;font-family:'IBM Plex Mono',monospace;font-size:12px;padding:6px 10px;border-radius:7px;opacity:0;transition:opacity .1s;z-index:200;white-space:nowrap;line-height:1.5}"
    + ".ci-h-tt b{color:#4FC0A4}"
    + ".ci-h-ficha{font-family:'IBM Plex Mono',monospace;font-size:11px;font-weight:600;color:#0A5C63;text-decoration:none;border:1px solid #DCD6CC;border-radius:999px;padding:4px 12px}"
    + ".ci-h-ficha:hover{border-color:#0E7C86}"
    /* semáforo económico (portada) */
    + "#ci-semaforo{margin:0 0 6px}"
    + ".ci-sem{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:0 0 26px}"
    + ".ci-sem-t{background:#fff;border:1px solid #EAE4DA;border-radius:12px;padding:12px 14px;text-decoration:none;display:block;transition:.15s}"
    + ".ci-sem-t:hover{border-color:#0E7C86;transform:translateY(-2px)}"
    + ".ci-sem-t .k{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:#6B6560;font-weight:600;display:block;margin-bottom:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}"
    + ".ci-sem-t .v{font-family:'IBM Plex Mono',monospace;font-size:19px;font-weight:600;color:#16130F}"
    + ".ci-sem-t .d{font-family:'IBM Plex Mono',monospace;font-size:11px;font-weight:600;display:block;margin-top:3px}"
    + ".ci-sem-t .d.up{color:#C0392B}.ci-sem-t .d.dn{color:#2E8B6F}.ci-sem-t .d.eq{color:#8A847C}"
    + ".ci-sem-cap{font-family:'IBM Plex Mono',monospace;font-size:10px;color:#8A847C;margin:-18px 0 26px}"
    + "@media(max-width:820px){.ci-sem{grid-template-columns:repeat(2,1fr)}}"
    + "@media(max-width:600px){.ci-hist .ci-h-in{padding:14px 16px 16px}.ci-h-tit{font-size:17px}}";

  var style = document.createElement("style");
  style.textContent = css;
  document.head.appendChild(style);

  /* ---------- utilidades ---------- */
  function fmtV(key, n) {
    var s = SERIES[key];
    var num;
    if (key === "inflacion") num = String(Math.round(n * 10) / 10).replace(".", ",");
    else num = Number(n).toLocaleString("es-AR", { maximumFractionDigits: 0 });
    if (s.unidad === "$") return "$" + num;
    if (s.unidad === "%") return num + "%";
    return num + " " + s.unidad;
  }
  function fmtF(iso, conAnio) {
    try {
      var p = iso.split("-");
      var lab = p[2] ? (+p[2] + " " + MES[+p[1] - 1]) : MES[+p[1] - 1];
      return conAnio ? lab + " " + p[0].slice(2) : lab;
    } catch (e) { return iso; }
  }
  function cacheGet(k, ttl) {
    try {
      var c = JSON.parse(sessionStorage.getItem(k) || "null");
      if (c && Date.now() - c.t < ttl) return c.d;
    } catch (e) {}
    return null;
  }
  function cacheSet(k, d) {
    try { sessionStorage.setItem(k, JSON.stringify({ t: Date.now(), d: d })); } catch (e) {}
  }

  /* ---------- datos del ticker (últimos valores) ---------- */
  function tickerData() {
    var c = cacheGet(TICKER_CACHE_KEY, TICKER_TTL_MS);
    if (c) return Promise.resolve(c);
    var items = [];
    var pDolar = fetch("https://dolarapi.com/v1/dolares")
      .then(function (r) { return r.json(); })
      .then(function (ds) {
        var find = function (casa) {
          for (var i = 0; i < ds.length; i++) if (ds[i].casa === casa) return ds[i];
          return null;
        };
        var of_ = find("oficial"), bl = find("blue"), mep = find("bolsa");
        if (of_) items.push({ key: "oficial", k: "Dólar oficial", v: fmtV("oficial", of_.venta) });
        if (bl) items.push({ key: "blue", k: "Blue", v: fmtV("blue", bl.venta) });
        if (mep) items.push({ key: "mep", k: "MEP", v: fmtV("mep", mep.venta) });
      }).catch(function () {});
    var pRiesgo = fetch("https://api.argentinadatos.com/v1/finanzas/indices/riesgo-pais/ultimo")
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d && d.valor != null) items.push({ key: "riesgo", k: "Riesgo país", v: fmtV("riesgo", d.valor) });
      }).catch(function () {});
    var pInf = fetch("https://api.argentinadatos.com/v1/finanzas/indices/inflacion")
      .then(function (r) { return r.json(); })
      .then(function (serie) {
        if (serie && serie.length) {
          var u = serie[serie.length - 1];
          var mes = "";
          try { mes = " (" + MES[+u.fecha.split("-")[1] - 1] + ")"; } catch (e) {}
          items.push({ key: "inflacion", k: "Inflación mensual" + mes, v: fmtV("inflacion", u.valor) });
        }
      }).catch(function () {});
    return Promise.all([pDolar, pRiesgo, pInf]).then(function () {
      cacheSet(TICKER_CACHE_KEY, items);
      return items;
    });
  }

  /* ---------- serie histórica (últimos 24 meses, normalizada) ---------- */
  function histData(key) {
    var ck = "ci_hist_" + key;
    var c = cacheGet(ck, HIST_TTL_MS);
    if (c) return Promise.resolve(c);
    return fetch(SERIES[key].hist)
      .then(function (r) { return r.json(); })
      .then(function (raw) {
        var corte = new Date();
        corte.setMonth(corte.getMonth() - 24);
        var lim = corte.toISOString().slice(0, 10);
        var pts = [];
        for (var i = 0; i < raw.length; i++) {
          var d = raw[i];
          var v = (d.venta != null) ? +d.venta : +d.valor;
          if (d.fecha >= lim && isFinite(v)) pts.push({ f: d.fecha, v: v });
        }
        pts.sort(function (a, b) { return a.f < b.f ? -1 : 1; });
        cacheSet(ck, pts);
        return pts;
      });
  }

  /* ---------- gráfico SVG ---------- */
  var NS = "http://www.w3.org/2000/svg";
  function mk(n, a) { var e = document.createElementNS(NS, n); for (var k in a) e.setAttribute(k, a[k]); return e; }
  var tt = null;
  function ensureTT() {
    if (!tt) { tt = document.createElement("div"); tt.className = "ci-h-tt"; document.body.appendChild(tt); }
    return tt;
  }
  function showTT(html, x, y) { var t = ensureTT(); t.innerHTML = html; t.style.opacity = 1; t.style.left = (x + 14) + "px"; t.style.top = (y - 12) + "px"; }
  function hideTT() { if (tt) tt.style.opacity = 0; }

  function dibujar(cont, key, pts, meses) {
    var s = SERIES[key];
    cont.innerHTML = "";
    var corte = new Date(); corte.setMonth(corte.getMonth() - meses);
    var lim = corte.toISOString().slice(0, 10);
    var serie = pts.filter(function (p) { return p.f >= lim; });
    if (serie.length < 2) { cont.innerHTML = '<div class="ci-h-estado">No hay datos suficientes para este rango.</div>'; return; }
    // muestreo: máx ~240 puntos para que el SVG quede liviano
    if (s.tipo === "linea" && serie.length > 240) {
      var paso = Math.ceil(serie.length / 240), m = [];
      for (var i = 0; i < serie.length; i += paso) m.push(serie[i]);
      if (m[m.length - 1].f !== serie[serie.length - 1].f) m.push(serie[serie.length - 1]);
      serie = m;
    }
    var W = 680, H = 240, mg = { t: 14, r: 58, b: 26, l: 8 };
    var iw = W - mg.l - mg.r, ih = H - mg.t - mg.b;
    var vs = serie.map(function (p) { return p.v; });
    var vMinD = Math.min.apply(null, vs), vMaxD = Math.max.apply(null, vs);
    var vMin = vMinD, vMax = vMaxD;
    if (s.tipo === "barras") vMin = Math.min(0, vMin);
    var span = (vMax - vMin) || 1; vMin -= span * 0.06; vMax += span * 0.06;
    var X = function (i) { return mg.l + (i / (serie.length - 1)) * iw; };
    var Y = function (v) { return mg.t + ih - ((v - vMin) / (vMax - vMin)) * ih; };
    var svg = mk("svg", { viewBox: "0 0 " + W + " " + H, role: "img",
      "aria-label": s.label + ", últimos " + meses + " meses. Mínimo " + fmtV(key, vMinD) + ", máximo " + fmtV(key, vMaxD) + "." });

    // grilla horizontal recesiva + etiquetas a la derecha
    for (var g = 0; g <= 3; g++) {
      var gv = vMin + (vMax - vMin) * (g / 3), gy = Y(gv);
      svg.appendChild(mk("line", { x1: mg.l, y1: gy, x2: mg.l + iw, y2: gy, stroke: "#E7E1D7", "stroke-width": 1 }));
      var lab = mk("text", { x: W - mg.r + 6, y: gy + 4, "font-family": "IBM Plex Mono, monospace", "font-size": 10, fill: "#8A847C" });
      lab.textContent = fmtV(key, gv); svg.appendChild(lab);
    }
    // etiquetas de tiempo (~5)
    var nx = Math.min(5, serie.length);
    for (var x = 0; x < nx; x++) {
      var ix = Math.round(x * (serie.length - 1) / (nx - 1));
      var xl = mk("text", { x: X(ix), y: H - 6, "text-anchor": x === 0 ? "start" : (x === nx - 1 ? "end" : "middle"),
        "font-family": "IBM Plex Mono, monospace", "font-size": 10, fill: "#8A847C" });
      xl.textContent = fmtF(serie[ix].f, true); svg.appendChild(xl);
    }

    if (s.tipo === "barras") {
      var bw = Math.max(4, Math.min(34, iw / serie.length - 4));
      // las barras quedan íntegras dentro del área de dibujo (no pisan etiquetas)
      var Xb = function (i) { return serie.length === 1 ? mg.l + iw / 2 : mg.l + bw / 2 + (i / (serie.length - 1)) * (iw - bw); };
      serie.forEach(function (p) {
        var i = serie.indexOf(p);
        var cx = Xb(i), y0 = Y(Math.max(0, p.v)), h = Math.abs(Y(p.v) - Y(0)) || 2;
        var r = mk("rect", { x: cx - bw / 2, y: y0, width: bw, height: h, rx: 3, fill: "#0E7C86" });
        svg.appendChild(r);
        r.addEventListener("mousemove", function (e) { r.setAttribute("opacity", .8); showTT("<b>" + fmtF(p.f, true) + "</b> · " + fmtV(key, p.v), e.clientX, e.clientY); });
        r.addEventListener("mouseleave", function () { r.setAttribute("opacity", 1); hideTT(); });
      });
    } else {
      var path = "";
      serie.forEach(function (p, i) { path += (i ? "L" : "M") + X(i).toFixed(1) + " " + Y(p.v).toFixed(1); });
      svg.appendChild(mk("path", { d: path, fill: "none", stroke: "#0E7C86", "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }));
      var ult = serie[serie.length - 1];
      svg.appendChild(mk("circle", { cx: X(serie.length - 1), cy: Y(ult.v), r: 3.5, fill: "#0E7C86", stroke: "#fff", "stroke-width": 2 }));
      // capa de hover: crosshair + punto más cercano
      var cross = mk("line", { y1: mg.t, y2: mg.t + ih, stroke: "#B9B3A9", "stroke-width": 1, "stroke-dasharray": "3 3", opacity: 0 });
      var dot = mk("circle", { r: 4, fill: "#0E7C86", stroke: "#fff", "stroke-width": 2, opacity: 0 });
      var captura = mk("rect", { x: mg.l, y: mg.t, width: iw, height: ih, fill: "transparent" });
      svg.appendChild(cross); svg.appendChild(dot); svg.appendChild(captura);
      captura.addEventListener("mousemove", function (e) {
        var box = svg.getBoundingClientRect();
        var fx = (e.clientX - box.left) / box.width * W;
        var i = Math.round((fx - mg.l) / iw * (serie.length - 1));
        i = Math.max(0, Math.min(serie.length - 1, i));
        var p = serie[i];
        cross.setAttribute("x1", X(i)); cross.setAttribute("x2", X(i)); cross.setAttribute("opacity", 1);
        dot.setAttribute("cx", X(i)); dot.setAttribute("cy", Y(p.v)); dot.setAttribute("opacity", 1);
        showTT("<b>" + fmtF(p.f, true) + "</b> · " + fmtV(key, p.v), e.clientX, e.clientY);
      });
      captura.addEventListener("mouseleave", function () { cross.setAttribute("opacity", 0); dot.setAttribute("opacity", 0); hideTT(); });
    }
    cont.appendChild(svg);
  }

  /* ---------- panel ---------- */
  var panel = null, abiertoKey = null;
  function armarPanel(tickerEl) {
    if (panel) return panel;
    panel = document.createElement("div");
    panel.className = "ci-hist";
    panel.innerHTML = '<div class="ci-h-in">'
      + '<div class="ci-h-top"><span class="ci-h-tit"></span><span class="ci-h-last"></span><span class="ci-h-var"></span><a class="ci-h-ficha" href="#">Ficha completa &rarr;</a><button class="ci-h-cerrar" type="button">Cerrar ✕</button></div>'
      + '<p class="ci-h-sub"></p>'
      + '<div class="ci-h-rangos">'
      + [6, 12, 18, 24].map(function (m) { return '<button type="button" class="ci-h-rango' + (m === 12 ? " activo" : "") + '" data-m="' + m + '">' + m + ' meses</button>'; }).join("")
      + "</div>"
      + '<div class="ci-h-chart"><div class="ci-h-estado">Cargando la serie…</div></div>'
      + '<div class="ci-h-fuente"></div>'
      + "</div>";
    tickerEl.parentNode.insertBefore(panel, tickerEl.nextSibling);
    panel.querySelector(".ci-h-cerrar").addEventListener("click", cerrar);
    return panel;
  }
  function cerrar() {
    if (panel) panel.classList.remove("abierto");
    abiertoKey = null;
    document.querySelectorAll(".ci-tk-item.open").forEach(function (b) { b.classList.remove("open"); });
    hideTT();
  }
  function actualizarCabecera(key, pts, meses) {
    var corte = new Date(); corte.setMonth(corte.getMonth() - meses);
    var lim = corte.toISOString().slice(0, 10);
    var serie = pts.filter(function (p) { return p.f >= lim; });
    var vEl = panel.querySelector(".ci-h-var");
    if (serie.length < 2) { vEl.textContent = ""; return; }
    var a = serie[0].v, b = serie[serie.length - 1].v;
    panel.querySelector(".ci-h-last").textContent = fmtV(key, b) + " hoy";
    if (key === "inflacion" || !a) { vEl.textContent = ""; vEl.className = "ci-h-var"; return; }
    var pct = (b - a) / a * 100;
    var sube = pct >= 0;
    vEl.textContent = (sube ? "+" : "−") + Math.abs(pct).toFixed(1).replace(".", ",") + "% en " + meses + " meses";
    vEl.className = "ci-h-var " + (sube ? "up" : "dn");
  }
  function abrir(key, btn, tickerEl) {
    armarPanel(tickerEl);
    if (abiertoKey === key) { cerrar(); return; }
    cerrar();
    abiertoKey = key;
    btn.classList.add("open");
    var s = SERIES[key];
    panel.querySelector(".ci-h-ficha").href = SITE_BASE + "indicador/" + FICHA[key] + ".html";
    panel.querySelector(".ci-h-tit").textContent = s.label + " — historial";
    panel.querySelector(".ci-h-sub").textContent = s.sub;
    panel.querySelector(".ci-h-last").textContent = "";
    var vEl = panel.querySelector(".ci-h-var"); vEl.textContent = ""; vEl.className = "ci-h-var";
    panel.querySelector(".ci-h-fuente").textContent = "Fuente: argentinadatos.com · Elaboración propia de Con Interés · Tocá otro indicador de la barra para cambiar de serie";
    var chart = panel.querySelector(".ci-h-chart");
    chart.innerHTML = '<div class="ci-h-estado">Cargando la serie…</div>';
    panel.classList.add("abierto");
    // si el lector está scrolleado, llevarlo hasta el panel (queda bajo el
    // encabezado fijo: masthead + ticker)
    setTimeout(function () {
      var mh = document.querySelector(".masthead");
      var tk = document.getElementById("ci-ticker");
      var off = ((mh && getComputedStyle(mh).position === "sticky") ? mh.offsetHeight : 0) + (tk ? tk.offsetHeight : 0);
      var r = panel.getBoundingClientRect();
      if (r.top < off - 4 || r.top > window.innerHeight * 0.6) {
        window.scrollTo({ top: r.top + window.pageYOffset - off, behavior: "smooth" });
      }
    }, 60);
    histData(key).then(function (pts) {
      if (abiertoKey !== key) return;
      var rangos = panel.querySelectorAll(".ci-h-rango");
      function pintar(meses) { dibujar(chart, key, pts, meses); actualizarCabecera(key, pts, meses); }
      rangos.forEach(function (r) {
        r.onclick = function () {
          rangos.forEach(function (x) { x.classList.remove("activo"); });
          r.classList.add("activo");
          pintar(+r.getAttribute("data-m"));
        };
      });
      var act = panel.querySelector(".ci-h-rango.activo");
      pintar(act ? +act.getAttribute("data-m") : 12);
    }).catch(function () {
      chart.innerHTML = '<div class="ci-h-estado">No se pudo cargar el historial en este momento. Probá de nuevo en unos minutos.</div>';
    });
  }

  /* ---------- render del ticker ---------- */
  function renderTicker() {
    var mount = document.getElementById("ci-ticker");
    if (!mount) {
      var mast = document.querySelector(".masthead");
      if (!mast) return;
      mount = document.createElement("div");
      mount.id = "ci-ticker";
      mast.parentNode.insertBefore(mount, mast.nextSibling);
    }
    tickerData().then(function (items) {
      if (!items || !items.length) { mount.remove(); return; }
      var wrap = document.createElement("div"); wrap.className = "ci-ticker";
      var inner = document.createElement("div"); inner.className = "ci-tk-in";
      var botones = {};
      items.forEach(function (it) {
        var b = document.createElement("button");
        b.type = "button"; b.className = "ci-tk-item";
        b.setAttribute("aria-label", it.k + ": " + it.v + ". Ver historial.");
        b.innerHTML = '<span class="k">' + it.k + '</span><span class="v">' + it.v + '</span><span class="caret">&#9660;</span>';
        b.addEventListener("click", function () { abrir(it.key, b, mount); });
        botones[it.key] = b;
        inner.appendChild(b);
      });
      // botón explícito: abre el historial del primer indicador
      var cta = document.createElement("button");
      cta.type = "button"; cta.className = "ci-tk-btn";
      cta.innerHTML = 'Ver hist&oacute;ricos <span class="caret">&#9660;</span>';
      cta.setAttribute("aria-label", "Ver el historial de los indicadores");
      cta.addEventListener("click", function () {
        var k = items[0].key;
        abrir(abiertoKey ? abiertoKey : k, botones[abiertoKey ? abiertoKey : k], mount);
      });
      inner.appendChild(cta);
      wrap.appendChild(inner);
      mount.innerHTML = "";
      mount.appendChild(wrap);
    });
  }

  /* ============================================================
     SEMÁFORO ECONÓMICO (solo si la página tiene #ci-semaforo)
     La foto del país en 10 segundos: valor de hoy + variación
     de 30 días (para inflación: vs. el mes anterior, en puntos).
     ============================================================ */
  function renderSemaforo() {
    var mount = document.getElementById("ci-semaforo");
    if (!mount) return;
    var DEFS = [
      { key: "oficial", label: "Dólar oficial" },
      { key: "blue", label: "Dólar blue" },
      { key: "mep", label: "Dólar MEP" },
      { key: "riesgo", label: "Riesgo país" },
      { key: "inflacion", label: "Inflación" }
    ];
    Promise.all(DEFS.map(function (d) {
      return histData(d.key).then(function (pts) { return { def: d, pts: pts }; }).catch(function () { return null; });
    })).then(function (rs) {
      rs = rs.filter(Boolean).filter(function (r) { return r.pts && r.pts.length > 1; });
      if (!rs.length) return;
      var h = '<div class="ci-sem">';
      rs.forEach(function (r) {
        var pts = r.pts, ult = pts[pts.length - 1], delta, sufijo;
        if (r.def.key === "inflacion") {
          var prev = pts[pts.length - 2];
          delta = ult.v - prev.v; sufijo = " pp vs mes anterior";
        } else {
          var corte = new Date(); corte.setDate(corte.getDate() - 30);
          var lim = corte.toISOString().slice(0, 10), base = pts[0];
          for (var i = 0; i < pts.length; i++) { if (pts[i].f <= lim) base = pts[i]; }
          delta = (ult.v / base.v - 1) * 100; sufijo = "% en 30 días";
        }
        var cls = Math.abs(delta) < 0.05 ? "eq" : (delta > 0 ? "up" : "dn");
        var flecha = cls === "eq" ? "→" : (delta > 0 ? "▲" : "▼");
        h += '<a class="ci-sem-t" href="' + SITE_BASE + "indicador/" + FICHA[r.def.key] + '.html">'
          + '<span class="k">' + r.def.label + '</span>'
          + '<span class="v">' + fmtV(r.def.key, ult.v) + "</span>"
          + '<span class="d ' + cls + '">' + flecha + " " + Math.abs(delta).toFixed(1).replace(".", ",") + sufijo + "</span>"
          + "</a>";
      });
      h += "</div>"
        + '<p class="ci-sem-cap">Semáforo económico · rojo = subió, verde = bajó · tocá un indicador para ver su ficha completa</p>';
      mount.innerHTML = h;
    });
  }

  // La lupa del buscador va en el encabezado de todas las paginas: como ticker.js ya esta en
  // todas, lo carga desde aca (un solo archivo que tocar en vez de cientos de paginas).
  function cargarBuscador() {
    try {
      if (window.CIBuscar || document.getElementById("ci-buscador-js")) return;
      var src = (document.currentScript && document.currentScript.src) ||
                (document.querySelector('script[src*="assets/ticker.js"]') || {}).src || "";
      if (!src) return;
      var s = document.createElement("script");
      s.id = "ci-buscador-js"; s.async = true;
      s.src = src.replace(/ticker\.js.*$/, "buscador.js?v=1");
      document.head.appendChild(s);
    } catch (e) {}
  }
  cargarBuscador();

  function init() { renderTicker(); setTimeout(renderSemaforo, 400); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
