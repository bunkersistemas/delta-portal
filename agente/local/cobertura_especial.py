"""
cobertura_especial.py <ahora 'AAAA-MM-DD HH:MM'> -- le toca una nota de cobertura especial?

Cobertura especial de la segunda vuelta en Brasil (editor, 24/10/2026): el domingo
25/10/2026, cuatro notas en el dia sobre lo que dicen las fuentes oficiales. Cada
turno tiene hora de inicio; la nota de un turno cuenta como publicada si en
data/articulos.json hay una entrada con "cobertura": "<CLAVE>-<n>".

Reglas:
  - el turno debido es el ULTIMO que ya empezo y no salio. Uno que no salio cuando
    empieza el siguiente queda reemplazado: la nota siguiente toma lo esencial;
  - ese dia, entre PAUSA_DESDE y medianoche, la redaccion general no corre: si no
    hay turno debido, la corrida termina sin nota (no compite con la cobertura).

Imprime una linea:
  COBERTURA|<n>|<hora>|<titulo>|<turnos ya publicados, coma>
  PAUSA|motivo
  GENERAL|motivo
"""
import datetime as dt, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CLAVE = "brasil-2026"
DIA = dt.date(2026, 10, 25)
PAUSA_DESDE = "08:00"
TURNOS = [
    (1, "09:00", "Que esta en juego: los dos modelos economicos y que cambia para la Argentina"),
    (2, "13:00", "Como vota Brasil: padron, reglas y lo que informa el TSE durante el dia"),
    (3, "18:30", "Primeros resultados oficiales del escrutinio del TSE"),
    (4, "22:30", "El resultado y que significa para la Argentina"),
]

def publicados():
    a = json.load(open(os.path.join(ROOT, "data", "articulos.json"), encoding="utf-8"))
    lista = a["articulos"] if isinstance(a, dict) else a
    hechos = set()
    for x in lista:
        c = str(x.get("cobertura") or "")
        if c.startswith(CLAVE + "-") and c[len(CLAVE) + 1:].isdigit():
            hechos.add(int(c[len(CLAVE) + 1:]))
    return hechos

def main(ahora_s):
    ahora = dt.datetime.strptime(ahora_s.strip(), "%Y-%m-%d %H:%M")
    if ahora.date() != DIA:
        print("GENERAL|sin cobertura especial hoy")
        return
    hhmm = ahora.strftime("%H:%M")
    if hhmm < PAUSA_DESDE:
        print("GENERAL|cobertura %s: todavia no empieza la pausa (%s)" % (CLAVE, PAUSA_DESDE))
        return
    hechos = publicados()
    empezados = [t for t in TURNOS if t[1] <= hhmm]
    lista = ",".join(str(n) for n in sorted(hechos)) or "ninguno"
    if empezados and empezados[-1][0] not in hechos:
        n, hora, titulo = empezados[-1]
        print("COBERTURA|%d|%s|%s|%s" % (n, hora, titulo, lista))
        return
    prox = [t for t in TURNOS if t[1] > hhmm]
    sig = ("proximo turno %d a las %s" % (prox[0][0], prox[0][1])) if prox else "no quedan turnos"
    print("PAUSA|cobertura %s: turnos publicados %s; %s" % (CLAVE, lista, sig))

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("uso: python agente/local/cobertura_especial.py \"AAAA-MM-DD HH:MM\"")
        sys.exit(1)
    main(sys.argv[1])
