# ===================================================================
#  Con Interes - auditoria semanal, corre en AGENTE007
#  La dispara la tarea programada "Con Interes - Auditoria semanal"
#  (lunes 07:00). Reemplaza a la rutina de la nube, que apuntaba al
#  repo viejo (hojeda465) y estaba apagada desde el 25/08.
#
#  Uso manual (por ejemplo, para auditar un periodo atrasado):
#    powershell -NoProfile -ExecutionPolicy Bypass -File agente\local\auditoria_semanal.ps1 -Desde 2026-08-25 -Hasta 2026-09-20
#
#  Que hace:
#    1. Pone el repo al dia. Si hay cambios sin commitear, NO audita.
#    2. Cuenta en data/articulos.json las notas de la ventana. Si son cero,
#       lo deja dicho en el log y termina: no se llama al modelo.
#    3. Corre Claude Code sin interaccion, con permisos acotados: leer,
#       buscar en la web, correr verificar_enlaces.py y escribir.
#    4. Controla el informe: que exista y que declare la misma cantidad
#       de notas que conto el script.
#    5. Commitea SOLO el informe y lo sube. Cualquier otro archivo que el
#       agente haya tocado queda sin subir y se avisa.
#  Todo en ASCII: la consola de Windows rompe las tildes.
# ===================================================================
param(
  [string]$Desde = '',
  [string]$Hasta = ''
)

# 'Continue': git escribe avisos por stderr. El corte lo hace $LASTEXITCODE.
$ErrorActionPreference = 'Continue'
$env:GIT_TERMINAL_PROMPT = '0'

$Raiz = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $Raiz

$Logs = Join-Path $env:USERPROFILE 'coninteres-logs'
New-Item -ItemType Directory -Force $Logs | Out-Null
$Hoy = Get-Date -Format 'yyyy-MM-dd'
$Log = Join-Path $Logs "auditoria_$Hoy.log"
$Latido = Join-Path $Logs 'auditoria.latido'

function Anotar($t) {
  $l = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + '  ' + $t
  Write-Output $l
  Add-Content -Path $Log -Value $l -Encoding ASCII
}
function Terminar($codigo, $t) {
  Anotar $t
  Set-Content -Path $Latido -Value ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + '  ' + $t) -Encoding ASCII
  exit $codigo
}

Anotar '==== auditoria semanal: inicio ===='

# ---- ventana: por defecto, de lunes a domingo de la semana pasada ----
if (-not $Desde -or -not $Hasta) {
  $h = (Get-Date).Date
  $dow = [int]$h.DayOfWeek            # 0 domingo .. 6 sabado
  $lunesEsta = $h.AddDays(-(($dow + 6) % 7))
  $Desde = $lunesEsta.AddDays(-7).ToString('yyyy-MM-dd')
  $Hasta = $lunesEsta.AddDays(-1).ToString('yyyy-MM-dd')
}
Anotar "ventana: $Desde a $Hasta"

# ---- 1. repo al dia ----
$sucio = git status --porcelain
if ($sucio) {
  Terminar 1 ('[FALLA] hay cambios sin commitear, no se audita: ' + ($sucio -join ' | '))
}
git pull --ff-only origin main 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Terminar 1 '[FALLA] git pull no pudo traer lo ultimo; no se audita sobre un repo viejo' }
Anotar ('repo: ' + (git log --oneline -1))

# ---- 2. universo: cuantas notas hay en la ventana ----
$py = $null
foreach ($c in @('python','py')) { if (Get-Command $c -ErrorAction SilentlyContinue) { $py = $c; break } }
if (-not $py) { Terminar 1 '[FALLA] no hay python en el PATH' }
$cuenta = & $py -c "import json,sys;a=json.load(open('data/articulos.json',encoding='utf-8'))['articulos'];print(sum(1 for x in a if '$Desde'<=str(x.get('fecha',''))[:10]<='$Hasta'))"
$N = 0
if (-not [int]::TryParse(("$cuenta").Trim(), [ref]$N)) { Terminar 1 "[FALLA] no se pudo contar notas: $cuenta" }
Anotar "notas publicadas en la ventana: $N"
if ($N -eq 0) {
  Terminar 0 "[OK] cero notas publicadas entre $Desde y ${Hasta}: no hay nada que auditar (no se llamo al modelo)"
}

# ---- 3. correr el auditor ----
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) { Terminar 1 '[FALLA] claude no esta en el PATH' }
$Informe = "negocio/auditoria-$Hoy.md"
$prompt = @"
Sos el auditor semanal de Con Interes. Corres sin nadie mirando: no hagas preguntas.
Lee agente/AUDITORIA.md (tu runbook) y agente/NEWSROOM.md seccion 3 (la vara de verificacion) y aplicalos al pie de la letra.
Ventana: notas de data/articulos.json con fecha entre $Desde y $Hasta inclusive. Son $N notas; auditalas todas.
Para las URLs usa: python scripts/verificar_enlaces.py (python, no python3).
Escribi el informe en $Informe. La primera linea despues del titulo tiene que ser exactamente:
Notas revisadas: $N
REGLAS: no edites ni despubliques ninguna nota, no corras aprobar.py ni rechazar.py, no hagas commit ni push (lo hace el script que te llamo). Solo escribis el informe.
Al final, responde con: el scorecard y la lista priorizada de acciones, marcando URGENTE lo grave.
"@
Anotar 'llamando al auditor...'
$salida = & claude -p $prompt --permission-mode dontAsk `
  --allowedTools 'Read' 'Glob' 'Grep' 'WebFetch' 'WebSearch' 'Write' 'Edit' 'Bash(python scripts/verificar_enlaces.py:*)' 2>&1
$codigo = $LASTEXITCODE
Add-Content -Path $Log -Value ($salida | Out-String) -Encoding UTF8
Anotar "claude termino con codigo $codigo"

# ---- 4. controles sobre el informe ----
if (-not (Test-Path $Informe)) { Terminar 1 "[FALLA] el auditor no dejo $Informe" }
$texto = Get-Content $Informe -Raw -Encoding UTF8
if ($texto -notmatch "Notas revisadas:\s*$N\b") {
  Terminar 1 "[FALLA] el informe no declara 'Notas revisadas: $N'; queda sin subir para revisarlo a mano"
}
Anotar "[OK] informe con $N notas declaradas"

# ---- 5. commit SOLO del informe, y push ----
$otros = @(git status --porcelain | Where-Object { $_ -notmatch [regex]::Escape("negocio/auditoria-$Hoy.md") })
if ($otros.Count -gt 0) { Anotar ('[AVISO] el auditor toco otros archivos, NO se suben: ' + ($otros -join ' | ')) }
git add -- $Informe
git -c user.email='auditoria@coninteres.com' -c user.name='Auditoria Con Interes' commit -m "Auditoria semanal $Desde a $Hasta ($N notas)" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Terminar 1 '[FALLA] no se pudo commitear el informe' }
git pull --rebase --autostash origin main 2>&1 | Out-Null
git push origin main 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Terminar 1 '[FALLA] el push fallo; el informe quedo commiteado en la VM' }
Terminar 0 "[OK] informe subido: https://coninteres.com/$Informe ($N notas, $Desde a $Hasta)"
