"""
serie_deportistas.py <hoy AAAA-MM-DD> -- le toca una corrida de "la plata de los deportistas"?

Prueba aprobada por el editor el 11/10/2026 (propuesta 1 del primer memo semanal):
4 notas en 2 semanas, 2 por semana, sobre cuanto cobra un deportista, cuanto le
cuesta competir y quien le paga. La prueba tiene FECHA DE FIN: despues de esa
fecha la serie no se corre sola; el memo mide el resultado y el editor decide si
sigue.

La nota es debida si:
  - hoy esta dentro de la prueba;
  - en la semana (lunes a domingo) se publicaron menos de CUPO notas con
    "serie": "plata-deportistas" en data/articulos.json;
  - hoy no se publico ninguna (asi las 2 de la semana caen en dias distintos).

Imprime una linea:  DEPORTISTAS|motivo   o   GENERAL|motivo
"""
import datetime as dt, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SERIE = "plata-deportistas"
DESDE, HASTA = dt.date(2026, 10, 12), dt.date(2026, 10, 25)
CUPO = 2

def fechas_serie():
    a = json.load(open(os.path.join(ROOT, "data", "articulos.json"), encoding="utf-8"))
    lista = a["articulos"] if isinstance(a, dict) else a
    return sorted(x.get("fecha", "") for x in lista if x.get("serie") == SERIE)

def main(hoy_s):
    hoy = dt.date.fromisoformat(hoy_s)
    if not (DESDE <= hoy <= HASTA):
        print(f"GENERAL|la prueba de la serie va del {DESDE} al {HASTA}")
        return
    lunes = hoy - dt.timedelta(days=hoy.weekday())
    f = fechas_serie()
    semana = [x for x in f if x >= lunes.isoformat()]
    if len(semana) >= CUPO:
        print(f"GENERAL|ya salieron {len(semana)} de {CUPO} notas de la serie esta semana")
    elif hoy.isoformat() in f:
        print(f"GENERAL|hoy ya salio una nota de la serie ({len(semana)} de {CUPO} en la semana)")
    else:
        print(f"DEPORTISTAS|{len(semana)} de {CUPO} notas de la serie en la semana del {lunes}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("uso: python agente/local/serie_deportistas.py <hoy>")
        sys.exit(1)
    main(sys.argv[1])
