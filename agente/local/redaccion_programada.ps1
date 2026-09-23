# ===================================================================
#  Con Interes - redaccion programada, corre en AGENTE007
#  La dispara la tarea "Con Interes - Redaccion programada" (cada 3 horas,
#  ver ACTIVAR_REDACCION.ps1). Autorizada por el editor el 23/09/2026:
#  las notas que pasan la verificacion se publican sin aprobacion una a una.
#
#  Uso manual:
#    powershell -NoProfile -ExecutionPolicy Bypass -File agente\local\redaccion_programada.ps1
#
#  Que hace:
#    1. Pone el repo al dia. Si hay cambios sin commitear o borradores en la
#       cola, NO corre (no pisa trabajo de nadie).
#    2. Corre Claude Code sin interaccion con la mision de redaccion. El
#       agente investiga, verifica y deja UNA nota en cola/ (o ninguna), y
#       declara el resultado en .corrida.json. No tiene permisos de git.
#    3. Si el veredicto es APTA, el script controla: entrada en cola.json,
#       archivo con noindex, cifra ancla, y que cada URL de fuentes responda.
#    4. Publica con aprobar.py, controla que solo se hayan tocado archivos
#       del sitio, commitea y sube.
#    5. Avisa por Gmail: la publicacion, o la falla si la hubo.
#  Todo en ASCII: la consola de Windows rompe las tildes.
# ===================================================================
$ErrorActionPreference = 'Continue'
$env:GIT_TERMINAL_PROMPT = '0'
$env:PYTHONIOENCODING = 'utf-8'

$Correo = 'oojeda465@gmail.com'

$Raiz = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $Raiz

$Logs = Join-Path $env:USERPROFILE 'coninteres-logs'
New-Item -ItemType Directory -Force $Logs | Out-Null
$Hoy = Get-Date -Format 'yyyy-MM-dd'
$Log = Join-Path $Logs "redaccion_$Hoy.log"
$Latido = Join-Path $Logs 'redaccion.latido'
$Resultado = Join-Path $Raiz '.corrida.json'

function Anotar($t) {
  $l = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + '  ' + $t
  Write-Output $l
  Add-Content -Path $Log -Value $l -Encoding ASCII
}
function Avisar($asunto, $cuerpo) {
  # PowerShell 5.1 rompe las comillas dobles al pasar argumentos a un programa
  $asunto = "$asunto".Replace('"', "'"); $cuerpo = "$cuerpo".Replace('"', "'")
  $p ="Manda UN mail con la herramienta de Gmail a $Correo. No hagas nada mas. Asunto: $asunto`nCuerpo (texto plano, tal cual):`n$cuerpo"
  $s = & claude -p $p --permission-mode dontAsk --allowedTools 'mcp__claude_ai_Gmail__send_message' 2>&1
  Add-Content -Path $Log -Value ('aviso gmail: ' + ($s | Out-String)) -Encoding UTF8
}
function Terminar($codigo, $t, $avisar = $false) {
  Anotar $t
  Set-Content -Path $Latido -Value ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + '  ' + $t) -Encoding ASCII
  if ($avisar) { Avisar 'Con Interes: la redaccion programada fallo' "$t`n`nLog: $Log" }
  exit $codigo
}

Anotar '==== redaccion programada: inicio ===='

# ---- 1. repo al dia y cola vacia ----
$sucio = git status --porcelain
if ($sucio) { Terminar 1 ('[FALLA] hay cambios sin commitear, no se corre: ' + ($sucio -join ' | ')) }
git pull --ff-only origin main 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Terminar 1 '[FALLA] git pull no pudo traer lo ultimo' $true }
Anotar ('repo: ' + (git log --oneline -1))

$py = $null
foreach ($c in @('python','py')) { if (Get-Command $c -ErrorAction SilentlyContinue) { $py = $c; break } }
if (-not $py) { Terminar 1 '[FALLA] no hay python en el PATH' $true }
$enCola = & $py -c "import json;print(len(json.load(open('data/cola.json',encoding='utf-8'))['borradores']))"
if ("$enCola".Trim() -ne '0') { Terminar 0 "[OK] hay $enCola borrador(es) esperando en la cola; no se genera otro" }

# ---- 2. la corrida ----
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) { Terminar 1 '[FALLA] claude no esta en el PATH' $true }
Remove-Item $Resultado -ErrorAction SilentlyContinue
$prompt = @"
Sos la redaccion de Con Interes y corres sin nadie mirando: no hagas preguntas.
Hace una corrida de redaccion completa siguiendo agente/local/misiones/redaccion.md y agente/NEWSROOM.md al pie de la letra (python, no python3).
Prioridad: lo que INDEC o BCRA publicaron hoy o en los ultimos dias y todavia no tiene nota nuestra (scripts/agenda.py, data/cubiertas.json).
La vara no se negocia: si la cifra ancla no llega a CONFIRMADO con dos fuentes independientes, FRENAR. Un dia sin nota es mejor que una nota floja.
Si no hay ningun dato nuevo con valor periodistico, no escribas nada: es un resultado valido.
Como maximo UNA nota. Dejala en cola/ con noindex, agregala a data/cola.json, registrala en data/cubiertas.json como en_cola y corre python scripts/build_portada.py.
Antes de terminar, corre vos los tres chequeos del editor de cierre (URLs 200, superlativos con valor previo, coherencia copete-graficos-cuerpo-manifiesto).
Si es la primera corrida del dia y data/pregunta.json no es de hoy, actualizala. Sin kit social.
PROHIBIDO: correr aprobar.py o rechazar.py, usar git, tocar notas ya publicadas, poner credenciales en ningun lado. La publicacion la hace el script que te llamo, despues de controlar tu trabajo.
AL FINAL escribi el archivo .corrida.json en la raiz del repo: un objeto JSON con tres claves de texto.
veredicto: APTA, FRENAR o SIN_TEMA. id: el id de la nota en la cola, o vacio. motivo: una linea que explique el resultado.
Con FRENAR registra el descarte en data/cubiertas.json como pide la mision.
"@
Anotar 'llamando a la redaccion...'
$salida = & claude -p $prompt --permission-mode dontAsk `
  --allowedTools 'Read' 'Glob' 'Grep' 'WebFetch' 'WebSearch' 'Write' 'Edit' 'Bash(python:*)' 'Bash(py:*)' 'Bash(curl:*)' 2>&1
$codigo = $LASTEXITCODE
Add-Content -Path $Log -Value ($salida | Out-String) -Encoding UTF8
Anotar "claude termino con codigo $codigo"

if (-not (Test-Path $Resultado)) { Terminar 1 '[FALLA] la redaccion no dejo .corrida.json; el repo queda como esta para revisarlo' $true }
$r = Get-Content $Resultado -Raw -Encoding UTF8 | ConvertFrom-Json
Remove-Item $Resultado -ErrorAction SilentlyContinue
Anotar ("veredicto: {0} | {1} | {2}" -f $r.veredicto, $r.id, $r.motivo)

# Archivos que una corrida puede tocar. Cualquier otro frena la subida.
# Las notas (articulos/, cola/) solo entran con nombre y apellido: ver Subir.
$sitio = '^(data/|assets/tarjetas/|index\.html$|hoy\.html$|archivo\.html$|feed\.xml$|sitemap\.xml$|seccion-[a-z0-9-]+\.html$)'
function Subir($mensaje, $nota = '') {
  $permitidos = $sitio
  if ($nota) { $permitidos = $sitio + '|^articulos/' + [regex]::Escape($nota) + '\.html$|^assets/tarjetas/' }
  $tocados = @(git status --porcelain | ForEach-Object { $_.Substring(3).Trim('"') })
  $raros = @($tocados | Where-Object { $_ -notmatch $permitidos })
  if ($raros.Count -gt 0) { Terminar 1 ('[FALLA] la corrida toco archivos fuera del sitio, no se sube nada: ' + ($raros -join ' | ')) $true }
  if ($tocados.Count -eq 0) { return }
  # ya se controlo que todo lo tocado sea del sitio
  git add -A 2>&1 | Out-Null
  git -c user.email='redaccion@coninteres.com' -c user.name='Redaccion Con Interes' commit -m $mensaje 2>&1 | Out-Null
  if ($LASTEXITCODE -ne 0) { Terminar 1 '[FALLA] no se pudo commitear' $true }
  git pull --rebase --autostash origin main 2>&1 | Out-Null
  git push origin main 2>&1 | Out-Null
  if ($LASTEXITCODE -ne 0) { Terminar 1 '[FALLA] el push fallo; el commit quedo en la maquina' $true }
}

if ($r.veredicto -ne 'APTA') {
  # sin nota: se sube solo lo que haya quedado registrado (descarte, pregunta del dia)
  $quedo = & $py -c "import json;print(len(json.load(open('data/cola.json',encoding='utf-8'))['borradores']))"
  if ("$quedo".Trim() -ne '0') { Terminar 1 ("[FALLA] veredicto {0} pero quedo un borrador en la cola; no se sube nada" -f $r.veredicto) $true }
  Subir ("Redaccion: corrida sin nota ({0})" -f $r.veredicto)
  Terminar 0 ("[OK] corrida sin nota: {0} - {1}" -f $r.veredicto, $r.motivo)
}

# ---- 3. controles sobre el borrador ----
$id = "$($r.id)".Trim()
if ($id -notmatch '^\d{4}-\d{2}-\d{2}-[a-z0-9-]+$') { Terminar 1 "[FALLA] id invalido: '$id'" $true }
$control = & $py agente/local/controlar_borrador.py $id 2>&1
if ($LASTEXITCODE -ne 0) { Terminar 1 "[FALLA] el borrador $id no paso los controles: $control. Queda en la cola sin publicar." $true }
$partes = "$control".Split('|')
$titulo = $partes[1]; $numero = $partes[2]; $etiqueta = $partes[3]
Anotar "[OK] controles del borrador $id"

# ---- 4. publicar y subir ----
& $py scripts/aprobar.py $id 2>&1 | ForEach-Object { Add-Content -Path $Log -Value $_ -Encoding UTF8 }
if ($LASTEXITCODE -ne 0 -or -not (Test-Path "articulos/$id.html")) { Terminar 1 "[FALLA] aprobar.py no publico $id" $true }
Subir "Publica: $titulo" $id
$url = "https://coninteres.com/articulos/$id.html"

# ---- 5. aviso ----
Avisar "Con Interes publico: $titulo" "Titulo: $titulo`nCifra ancla: $numero ($etiqueta)`nLink: $url`n`nPublicada por la redaccion programada. Log: $Log"
Terminar 0 "[OK] publicada: $url"
