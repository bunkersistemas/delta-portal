#!/usr/bin/env python3
"""
aplicar_narrativa.py -- aplica (o descarta) la salida del editor de narrativa sobre un borrador de la cola.
Lo llama redaccion_programada.ps1 despues de correr la mision agente/local/misiones/narrativa.md.

Lee:    cola/<id>.html                              (el borrador, tal como lo dejo la redaccion)
        _privado/narrativa/<id>.html                (la version del editor de narrativa)
        _privado/narrativa/<id>.narrativa.json      (su informe: tesis, cambios, afirmaciones_nuevas)
Hace:   corre controlar_narrativa.py (cifras, citas, links, graficos, estructura, afirmaciones nuevas) y
        - si pasa: guarda el borrador original en _privado/narrativa/<id>.original.html, pone la version nueva
          en cola/<id>.html y sincroniza la bajada (cola.json y metadatos del <head>) con el copete nuevo;
        - si NO pasa (o falta algo): deja el borrador como estaba. La nota sale con la redaccion original:
          el editor de narrativa NUNCA frena una nota ni la publica con un hecho que el control no admite.
Imprime una linea: APLICADA | DESCARTADA <motivo> | SIN_SALIDA ; exit 0 siempre que el borrador quede sano.
Uso: python agente/local/aplicar_narrativa.py <id> [--raiz DIR]
Archivo en ASCII puro.
"""
import html, io, json, os, re, shutil, sys, time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import controlar_narrativa as cn


def escribir(ruta, texto):
    tmp = ruta + ".tmp"
    io.open(tmp, "w", encoding="utf-8", newline="").write(texto)
    os.replace(tmp, ruta)


def standfirst(t):
    m = re.search(r'(?s)<p class="standfirst">(.*?)</p>', t)
    return html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print("uso: aplicar_narrativa.py <id> [--raiz DIR]")
        return 2
    id_ = args[0]
    raiz = os.path.dirname(os.path.dirname(AQUI))
    if "--raiz" in sys.argv:
        raiz = sys.argv[sys.argv.index("--raiz") + 1]
    carpeta = os.path.join(raiz, "_privado", "narrativa")
    p_cola = os.path.join(raiz, "cola", id_ + ".html")
    p_new = os.path.join(carpeta, id_ + ".html")
    p_inf = os.path.join(carpeta, id_ + ".narrativa.json")
    p_json = os.path.join(raiz, "data", "cola.json")
    reg = os.path.join(carpeta, "registro.jsonl")

    def registrar(resultado, motivo=""):
        try:
            io.open(reg, "a", encoding="utf-8").write(json.dumps(
                {"id": id_, "cuando": time.strftime("%Y-%m-%d %H:%M"), "resultado": resultado, "motivo": motivo},
                ensure_ascii=False) + "\n")
        except Exception:
            pass

    if not (os.path.exists(p_cola) and os.path.exists(p_new) and os.path.exists(p_inf)):
        registrar("SIN_SALIDA", "falta el borrador, la version nueva o el informe")
        print("SIN_SALIDA el editor de narrativa no dejo version o informe: sale la redaccion original")
        return 0
    o, n = cn.leer(p_cola), cn.leer(p_new)
    try:
        informe = json.load(io.open(p_inf, encoding="utf-8"))
    except Exception as e:
        registrar("DESCARTADA", "informe ilegible: %s" % e)
        print("DESCARTADA informe ilegible: %s" % e)
        return 0
    errs = cn.revisar(o, n, informe)
    # En el pipeline el titulo no cambia: la redaccion ya lo paso por titulares.py y el pedido de un lector
    # lo trae como pregunta; cambiarlo obligaria a sincronizar cola.json, metadatos y tarjetas.
    if cn.h1(o) != cn.h1(n):
        errs.append("el editor de narrativa cambio el titulo (en el pipeline no se toca)")
    if not standfirst(n):
        errs.append("la version nueva no tiene copete")
    if errs:
        motivo = " | ".join(errs[:6])
        registrar("DESCARTADA", motivo)
        print("DESCARTADA " + motivo)
        return 0
    # aplicar: respaldo del original, version nueva, bajada sincronizada
    shutil.copyfile(p_cola, os.path.join(carpeta, id_ + ".original.html"))
    viejo_cop, nuevo_cop = standfirst(o), standfirst(n)
    if viejo_cop and nuevo_cop and viejo_cop != nuevo_cop:
        esc_v, esc_n = html.escape(viejo_cop, quote=True), html.escape(nuevo_cop, quote=True)
        cabeza, resto = n.split("</head>", 1)
        for v, nu in ((esc_v, esc_n), (viejo_cop, nuevo_cop), (viejo_cop.replace('"', "&quot;"), nuevo_cop.replace('"', "&quot;"))):
            cabeza = cabeza.replace(v, nu)
        n = cabeza + "</head>" + resto
    escribir(p_cola, n)
    try:
        c = json.load(io.open(p_json, encoding="utf-8"))
        for b in c.get("borradores", []):
            if b.get("id") == id_ and nuevo_cop:
                b["bajada"] = nuevo_cop
        escribir(p_json, json.dumps(c, ensure_ascii=False, indent=2) + "\n")
    except Exception as e:
        # el borrador ya esta aplicado y la bajada vieja en cola.json es solo un resumen: se avisa, no se frena
        print("AVISO no se pudo sincronizar la bajada en cola.json: %s" % e)
    cambios = len(informe.get("cambios") or [])
    registrar("APLICADA", "%d cambios; tesis: %s" % (cambios, str(informe.get("tesis", ""))[:160]))
    print("APLICADA %d cambios | tesis: %s" % (cambios, str(informe.get("tesis", ""))[:160]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
