"""
semana_ia.py <hoy AAAA-MM-DD> [<forzada AAAA-MM-DD>] -- le toca una corrida de IA?

La seccion "La economia de la IA" publica una nota por semana, los martes
(NEWSROOM.md 2 quinquies, decision del editor del 11/10/2026). La semana va de
martes a lunes: la nota es debida si desde el ultimo martes (incluido) no se
publico ninguna nota con "seccion": "IA" en data/articulos.json.

<forzada> es una fecha puesta a mano (coninteres-logs/ia_forzada.txt): pide una
nota IA con fecha >= esa, aunque no sea martes. Se usa una vez, para adelantar
una entrega; cuando ya salio, se avisa para borrar el archivo.

Imprime una linea:  IA|motivo   o   GENERAL|motivo   y, si la forzada ya se
cumplio o es invalida, una segunda linea:  BORRAR_FORZADA
"""
import datetime as dt, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MARTES = 1

def fechas_ia():
    a = json.load(open(os.path.join(ROOT, "data", "articulos.json"), encoding="utf-8"))
    lista = a["articulos"] if isinstance(a, dict) else a
    return sorted(x.get("fecha", "") for x in lista if x.get("seccion") == "IA")

def main(hoy_s, forzada_s=""):
    hoy = dt.date.fromisoformat(hoy_s)
    inicio = hoy - dt.timedelta(days=(hoy.weekday() - MARTES) % 7)
    ia = fechas_ia()
    ultima = ia[-1] if ia else "ninguna"
    borrar = False
    if forzada_s:
        try:
            f = dt.date.fromisoformat(forzada_s.strip())
        except ValueError:
            f = None
        if f is None or f > hoy:
            borrar = f is None
        elif not any(x >= f.isoformat() for x in ia):
            print(f"IA|entrega adelantada pedida para el {f} y todavia no salio (ultima IA: {ultima})")
            return
        else:
            borrar = True
    if not any(x >= inicio.isoformat() for x in ia):
        if hoy == inicio:
            print(f"IA|martes {inicio}: falta la nota de la semana (ultima IA: {ultima})")
        else:
            print(f"IA|la nota de la semana del martes {inicio} todavia no salio (ultima IA: {ultima})")
    else:
        print(f"GENERAL|la nota IA de la semana del martes {inicio} ya salio ({ultima})")
    if borrar:
        print("BORRAR_FORZADA")

if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        print("uso: python agente/local/semana_ia.py <hoy> [<forzada>]")
        sys.exit(1)
    main(*sys.argv[1:])
