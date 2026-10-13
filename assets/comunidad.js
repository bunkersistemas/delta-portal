/* comunidad.js -- panel flotante "Preguntas de la comunidad" (editor, 13/10/2026).
   Historial de lo que preguntan los lectores (Instagram, Threads o el portal): solo lo
   que aprobo el editor, sin nombres ni usuarios. Una pregunta no es un pedido de
   investigacion: con todas juntas, cada semana se elige que investigar. El campo
   "Deja tu pregunta" no publica nada: la pregunta espera la aprobacion del editor.
   La pagina solo puede leer lo aprobado (preguntas_panel) y agregar una pregunta
   (pregunta_enviar); la tabla no la ve. */
(function () {
  var BASE = "https://tgjxivohobemoirrkwrq.supabase.co/rest/v1/rpc/";
  var LLAVE = "sb_publishable_nBxN5DKUcmBwVhkgqNfs8g_ILB1fplb";
  var DONDE = { instagram: "en Instagram", threads: "en Threads", web: "en el portal" };

  function rpc(nombre, cuerpo) {
    return fetch(BASE + nombre, {
      method: "POST",
      headers: { "apikey": LLAVE, "Content-Type": "application/json" },
      body: JSON.stringify(cuerpo || {})
    });
  }

  var css = "" +
    ".cm-tab{position:fixed;right:18px;bottom:18px;z-index:150;display:flex;align-items:center;gap:8px;background:#16130F;color:#FAF8F4;" +
    "border:0;border-radius:999px;padding:11px 16px;font:600 14px Inter,system-ui,sans-serif;cursor:pointer;box-shadow:0 6px 20px rgba(0,0,0,.18)}" +
    ".cm-tab:hover{background:#0A5C63}" +
    ".cm-panel{position:fixed;right:18px;bottom:76px;z-index:151;width:360px;max-width:calc(100vw - 32px);max-height:min(620px,calc(100vh - 110px));" +
    "display:none;flex-direction:column;background:#FAF8F4;color:#16130F;border:1px solid #EAE4DA;border-radius:14px;box-shadow:0 14px 40px rgba(0,0,0,.2);" +
    "font-family:Inter,system-ui,sans-serif;overflow:hidden}" +
    ".cm-panel.abierto{display:flex}" +
    ".cm-cab{display:flex;justify-content:space-between;align-items:center;padding:14px 16px 10px;border-bottom:1px solid #EAE4DA}" +
    ".cm-cab b{font:700 17px 'Source Serif 4',Georgia,serif}" +
    ".cm-sub{font-size:12.5px;color:#6B6560;padding:8px 16px 0;line-height:1.4}.cm-sub a{color:#0A5C63;font-weight:600}" +
    ".cm-x{background:none;border:0;font-size:22px;line-height:1;color:#6B6560;cursor:pointer;padding:2px 6px}" +
    ".cm-lista{overflow-y:auto;padding:6px 16px;flex:1}" +
    ".cm-item{padding:11px 0;border-bottom:1px solid #EAE4DA}" +
    ".cm-item:last-child{border-bottom:0}" +
    ".cm-de{font:600 10.5px 'IBM Plex Mono',monospace;letter-spacing:.08em;text-transform:uppercase;color:#6B6560;margin-bottom:4px}" +
    ".cm-txt{font-size:14.5px;line-height:1.45;margin:0 0 6px}" +
    ".cm-est{display:inline-block;font:600 11.5px Inter,system-ui,sans-serif;border-radius:999px;padding:3px 9px;background:#EFEAE1;color:#3C3833;text-decoration:none}" +
    ".cm-est.inv{background:#FCEFE1;color:#8A4A10}.cm-est.ok{background:#E3F2EC;color:#0A5C63}" +
    ".cm-vacio{color:#6B6560;font-size:14px;padding:14px 0}" +
    ".cm-form{border-top:1px solid #EAE4DA;padding:12px 16px 14px;background:#fff}" +
    ".cm-form label{display:block;font-weight:600;font-size:13.5px;margin-bottom:6px}" +
    ".cm-form textarea{width:100%;box-sizing:border-box;min-height:62px;resize:vertical;border:1px solid #DCD6CC;border-radius:9px;padding:9px 10px;font:14px Inter,system-ui,sans-serif;color:#16130F;background:#FAF8F4}" +
    ".cm-fila{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-top:8px}" +
    ".cm-nota{font-size:11.5px;color:#6B6560;line-height:1.35}.cm-nota a{color:#0A5C63}" +
    ".cm-env{background:#0E7C86;color:#fff;border:0;border-radius:9px;padding:9px 14px;font:600 13.5px Inter,system-ui,sans-serif;cursor:pointer;white-space:nowrap}" +
    ".cm-env:disabled{opacity:.6;cursor:default}" +
    ".cm-aviso{font-size:13px;margin-top:8px}.cm-aviso.ok{color:#0A5C63}.cm-aviso.mal{color:#A33}" +
    ".cm-trampa{position:absolute;left:-9999px;width:1px;height:1px;overflow:hidden}" +
    "@media(max-width:600px){.cm-tab{right:12px;bottom:12px;padding:10px 14px;font-size:13px}.cm-tab .cm-largo{display:none}" +
    ".cm-panel{right:12px;left:12px;width:auto;max-width:none;bottom:64px}}";

  function el(tag, cls, txt) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (txt != null) e.textContent = txt;
    return e;
  }

  function armar() {
    var st = el("style"); st.textContent = css; document.head.appendChild(st);

    var tab = el("button", "cm-tab");
    tab.type = "button";
    tab.setAttribute("aria-expanded", "false");
    tab.appendChild(el("span", null, "🙋"));
    tab.appendChild(el("span", "cm-largo", "Preguntas de la comunidad"));
    var corto = el("span", null, "Preguntas");
    corto.className = "cm-corto";
    tab.appendChild(corto);
    st.textContent += ".cm-corto{display:none}@media(max-width:600px){.cm-corto{display:inline}}";

    var panel = el("div", "cm-panel");
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", "Preguntas de la comunidad");
    var cab = el("div", "cm-cab");
    cab.appendChild(el("b", null, "Preguntas de la comunidad"));
    var x = el("button", "cm-x", "×"); x.type = "button"; x.setAttribute("aria-label", "Cerrar");
    cab.appendChild(x);
    var sub = el("div", "cm-sub", "Lo que nos preguntan los lectores. Con esto elegimos qué investigar cada semana. ");
    var todas = el("a", null, "Ver todas →"); todas.href = "investigacion.html";
    sub.appendChild(todas);
    var lista = el("div", "cm-lista");
    lista.appendChild(el("div", "cm-vacio", "Cargando…"));

    var form = el("form", "cm-form");
    form.noValidate = true;
    var lab = el("label", null, "Dejá tu pregunta");
    lab.htmlFor = "cm-q";
    var ta = el("textarea"); ta.id = "cm-q"; ta.maxLength = 300;
    ta.placeholder = "¿Qué te gustaría que investiguemos con datos?";
    var trampa = el("div", "cm-trampa"); trampa.setAttribute("aria-hidden", "true");
    var ti = el("input"); ti.type = "text"; ti.tabIndex = -1; ti.autocomplete = "off"; ti.name = "web";
    trampa.appendChild(ti);
    var fila = el("div", "cm-fila");
    var nota = el("div", "cm-nota");
    nota.appendChild(document.createTextNode("La leemos antes de mostrarla. Nunca publicamos nombres. "));
    var priv = el("a", null, "Privacidad"); priv.href = "privacidad.html";
    nota.appendChild(priv);
    var env = el("button", "cm-env", "Enviar"); env.type = "submit";
    fila.appendChild(nota); fila.appendChild(env);
    var aviso = el("div", "cm-aviso"); aviso.setAttribute("role", "status");
    form.appendChild(lab); form.appendChild(ta); form.appendChild(trampa); form.appendChild(fila); form.appendChild(aviso);

    panel.appendChild(cab); panel.appendChild(sub); panel.appendChild(lista); panel.appendChild(form);
    document.body.appendChild(panel);
    document.body.appendChild(tab);

    var cargado = false;
    function abrir(si) {
      panel.classList.toggle("abierto", si);
      tab.setAttribute("aria-expanded", si ? "true" : "false");
      if (si && !cargado) { cargado = true; cargar(lista); }
    }
    tab.addEventListener("click", function () { abrir(!panel.classList.contains("abierto")); });
    x.addEventListener("click", function () { abrir(false); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") abrir(false); });

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var t = ta.value.replace(/\s+/g, " ").trim();
      function decir(m, ok) { aviso.textContent = m; aviso.className = "cm-aviso " + (ok ? "ok" : "mal"); }
      if (t.length < 10) { decir("Escribí tu pregunta (al menos 10 letras).", false); ta.focus(); return; }
      env.disabled = true; env.textContent = "Enviando...";
      rpc("pregunta_enviar", { p_texto: t, p_trampa: ti.value || "" }).then(function (r) {
        if (r.ok) {
          decir("¡Gracias! La leemos y, si la aprobamos, aparece acá.", true);
          ta.value = "";
          return;
        }
        return r.json().catch(function () { return {}; }).then(function (j) {
          decir(j && j.message && /hora/.test(j.message) ? "Llegaron muchas preguntas en la última hora. Probá más tarde."
                                                         : "No pudimos guardar tu pregunta. Probá de nuevo en un rato.", false);
        });
      }).catch(function () {
        decir("No hay conexión. Probá de nuevo en un rato.", false);
      }).then(function () { env.disabled = false; env.textContent = "Enviar"; });
    });
  }

  function cargar(lista) {
    rpc("preguntas_panel").then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    }).then(function (filas) {
      lista.innerHTML = "";
      if (!filas || !filas.length) {
        lista.appendChild(el("div", "cm-vacio", "Todavía no hay preguntas publicadas. ¡Dejá la primera!"));
        return;
      }
      filas.forEach(function (p) {
        var it = el("div", "cm-item");
        it.appendChild(el("div", "cm-de", "Preguntaron " + (DONDE[p.origen] || "")));
        it.appendChild(el("p", "cm-txt", p.texto));
        if (p.estado === "respondida" && p.nota_url) {
          var b = el("a", "cm-est ok", "✅ Respondida → leer la nota");
          b.href = String(p.nota_url).replace("https://coninteres.com/", "");
          it.appendChild(b);
        }
        lista.appendChild(it);
      });
    }).catch(function () {
      lista.innerHTML = "";
      lista.appendChild(el("div", "cm-vacio", "No pudimos cargar las preguntas. Probá de nuevo en un rato."));
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", armar);
  else armar();
})();
