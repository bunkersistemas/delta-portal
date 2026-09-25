# ===================================================================
#  Con Interes - redaccion programada, corre en AGENTE007
#  La dispara la tarea "Con Interes - Redaccion programada" (cada hora,
#  ver ACTIVAR_REDACCION.ps1). Autorizada por el editor el 23/09/2026:
#  las notas que pasan la verificacion se publican sin aprobacion una a una.
#
#  Uso manual:
#    powershell -NoProfile -ExecutionPolicy Bypass -File agente\local\redaccion_programada.ps1
#
#  Que hace:
#    1. Pone el repo al dia. Si hay cambios sin commitear, NO corre (no pisa
#       trabajo de nadie). Si en la cola hay un borrador RETENIDO por esta
#       misma redaccion, le repite el control: si pasa lo publica, si no lo
#       rechaza y sigue. Un borrador que no es suyo (lo dejo alguien a mano)
#       no se toca y la corrida espera.
#    2. Corre Claude Code sin interaccion con la mision de redaccion. El
#       agente investiga, verifica y deja UNA nota en cola/ (o ninguna), y
#       declara el resultado en .corrida.json. No tiene permisos de git.
#    3. Si el veredicto es APTA, el script controla: entrada en cola.json,
#       archivo con noindex, cifra ancla, y que cada URL de fuentes responda.
#         - pasa: se publica;
#         - una fuente no respondio a tiempo (falla transitoria): el borrador
#           se commitea en la cola y se RETIENE para la corrida siguiente;
#         - falla definitiva: se rechaza con rechazar.py.
#       En ningun caso el repo queda sucio: una nota trabada no frena el dia.
#       (24/09/2026: una nota que estaba bien dejo 9 corridas seguidas sin
#       correr porque el control la dejo sin commitear.)
#    4. Publica con aprobar.py, controla que solo se hayan tocado archivos
#       del sitio, commitea y sube.
#    5. Anota la corrida en coninteres-logs\corridas.jsonl: una linea al
#       empezar y otra al terminar. Con eso n8n arma el resumen diario; una
#       corrida con inicio y sin fin es una corrida cortada. No manda mails.
#  Todo en ASCII: la consola de Windows rompe las tildes.
# ===================================================================
$ErrorActionPreference = 'Continue'
$env:GIT_TERMINAL_PROMPT = '0'
$env:PYTHONIOENCODING = 'utf-8'
# Python y git escriben UTF-8: sin esto PowerShell 5.1 lee su salida con la
# pagina de codigos de la consola y los titulos con tildes llegan rotos al
# commit (paso en la primera corrida, 23/09/2026).
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# Todo en hora de Buenos Aires, cualquiera sea la zona de la maquina (esta en
# Madrid): TZ lo respetan python, git y claude; los logs usan HoraAR.
$env:TZ = 'ART3'
function HoraAR { [TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow, 'Argentina Standard Time') }

$Raiz = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $Raiz

$Logs = Join-Path $env:USERPROFILE 'coninteres-logs'
New-Item -ItemType Directory -Force $Logs | Out-Null
$Hoy = (HoraAR).ToString('yyyy-MM-dd')
$Log = Join-Path $Logs "redaccion_$Hoy.log"
$Latido = Join-Path $Logs 'redaccion.latido'
$Registro = Join-Path $Logs 'corridas.jsonl'
# Borradores que esta redaccion dejo en la cola por una falla transitoria.
# Vive fuera del repo: es estado de la maquina, no del sitio.
$ArchivoRetenidos = Join-Path $Logs 'retenidos.txt'
$Resultado = Join-Path $Raiz '.corrida.json'
$Corrida = (HoraAR).ToString('yyyy-MM-ddTHH:mm:ss')

function Anotar($t) {
  $l = (HoraAR).ToString('yyyy-MM-dd HH:mm:ss') + ' AR  ' + $t
  Write-Output $l
  Add-Content -Path $Log -Value $l -Encoding ASCII
}
function Registrar($evento, $resultado = '', $id = '', $motivo = '') {
  $o = [ordered]@{ corrida = $Corrida; evento = $evento; hora = (HoraAR).ToString('yyyy-MM-ddTHH:mm:ss');
                   resultado = $resultado; id = "$id"; motivo = "$motivo" }
  $linea = (New-Object PSObject -Property $o | ConvertTo-Json -Compress) + "`n"
  [System.IO.File]::AppendAllText($Registro, $linea, (New-Object System.Text.UTF8Encoding($false)))
}
# resultado: publicada | sin_tema | frenada | retenida | rechazada | en_espera | bloqueada | falla
function Terminar($codigo, $resultado, $t, $id = '') {
  Anotar $t
  Set-Content -Path $Latido -Value ((HoraAR).ToString('yyyy-MM-dd HH:mm:ss') + ' AR  ' + $t) -Encoding ASCII
  Registrar 'fin' $resultado $id $t
  exit $codigo
}
function LeerRetenidos { if (Test-Path $ArchivoRetenidos) { @(Get-Content $ArchivoRetenidos | Where-Object { $_.Trim() }) } else { @() } }
function GuardarRetenidos($ids) { Set-Content -Path $ArchivoRetenidos -Value @($ids) -Encoding ASCII }
function Cola { @(& $py -c "import json;[print(b['id']) for b in json.load(open('data/cola.json',encoding='utf-8'))['borradores']]" | Where-Object { "$_".Trim() }) }

Registrar 'inicio'
Anotar '==== redaccion programada: inicio ===='

# Archivos que una corrida puede tocar. Cualquier otro frena la subida.
# Las notas (articulos/, cola/) solo entran con nombre y apellido: ver Subir.
$sitio = '^(data/|assets/tarjetas/|index\.html$|hoy\.html$|archivo\.html$|feed\.xml$|sitemap\.xml$|seccion-[a-z0-9-]+\.html$)'
function Subir($mensaje, $nota = '') {
  $permitidos = $sitio
  if ($nota) {
    $n = [regex]::Escape($nota)
    $permitidos = $sitio + '|^articulos/' + $n + '\.html$|^cola/' + $n + '\.html$|^assets/tarjetas/'
  }
  $tocados = @(git status --porcelain | ForEach-Object { $_.Substring(3).Trim('"') })
  $raros = @($tocados | Where-Object { $_ -notmatch $permitidos })
  if ($raros.Count -gt 0) { Terminar 1 'falla' ('[FALLA] la corrida toco archivos fuera del sitio, no se sube nada: ' + ($raros -join ' | ')) $nota }
  if ($tocados.Count -eq 0) { return }
  # ya se controlo que todo lo tocado sea del sitio
  git add -A 2>&1 | Out-Null
  git -c user.email='redaccion@coninteres.com' -c user.name='Redaccion Con Interes' commit -m $mensaje 2>&1 | Out-Null
  if ($LASTEXITCODE -ne 0) { Terminar 1 'falla' '[FALLA] no se pudo commitear' $nota }
  git pull --rebase --autostash origin main 2>&1 | Out-Null
  git push origin main 2>&1 | Out-Null
  if ($LASTEXITCODE -ne 0) { Terminar 1 'falla' '[FALLA] el push fallo; el commit quedo en la maquina' $nota }
}

# Controla un borrador y lo publica. Devuelve el codigo del control si NO se
# publico (1 definitiva, 2 transitoria) y deja el motivo en $script:motivoControl.
function Publicar($id) {
  $control = & $py agente/local/controlar_borrador.py $id 2>&1
  $rc = $LASTEXITCODE
  if ($rc -ne 0) { $script:motivoControl = "$control"; return $rc }
  $partes = "$control".Split('|')
  $titulo = $partes[1]
  $null = Anotar "[OK] controles del borrador $id"
  & $py scripts/aprobar.py $id 2>&1 | ForEach-Object { Add-Content -Path $Log -Value $_ -Encoding UTF8 }
  if ($LASTEXITCODE -ne 0 -or -not (Test-Path "articulos/$id.html")) { Terminar 1 'falla' "[FALLA] aprobar.py no publico $id" $id }
  Subir "Publica: $titulo" $id
  GuardarRetenidos @(LeerRetenidos | Where-Object { $_ -ne $id })
  Terminar 0 'publicada' "[OK] publicada: https://coninteres.com/articulos/$id.html" $id
}
function Rechazar($id, $motivo) {
  $motivo = "$motivo".Replace([string][char]34, "'")
  & $py scripts/rechazar.py $id $motivo 2>&1 | ForEach-Object { Add-Content -Path $Log -Value $_ -Encoding UTF8 }
  if ($LASTEXITCODE -ne 0) { Terminar 1 'falla' "[FALLA] rechazar.py no pudo sacar $id de la cola" $id }
  Subir "Redaccion: rechaza $id (control)" $id
  GuardarRetenidos @(LeerRetenidos | Where-Object { $_ -ne $id })
  Registrar 'rechazo' 'rechazada' $id $motivo
  Anotar "[RECHAZADA] $id - $motivo"
}

# ---- 1. repo al dia y cola ----
$sucio = git status --porcelain
if ($sucio) { Terminar 1 'bloqueada' ('[FALLA] hay cambios sin commitear, no se corre: ' + ($sucio -join ' | ')) }
git pull --ff-only origin main 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Terminar 1 'falla' '[FALLA] git pull no pudo traer lo ultimo' }
Anotar ('repo: ' + (git log --oneline -1))

$py = $null
foreach ($c in @('python','py')) { if (Get-Command $c -ErrorAction SilentlyContinue) { $py = $c; break } }
if (-not $py) { Terminar 1 'falla' '[FALLA] no hay python en el PATH' }

$enCola = Cola
# lo retenido que ya no esta en la cola (lo publico o rechazo alguien a mano) se olvida
GuardarRetenidos @(LeerRetenidos | Where-Object { $enCola -contains $_ })
$retenidos = LeerRetenidos
foreach ($id in @($enCola | Where-Object { $retenidos -contains $_ })) {
  Anotar "segundo control del borrador retenido $id"
  $rc = Publicar $id
  # no se publico: segunda falla, se rechaza y la corrida sigue con otro tema
  Rechazar $id ("no paso el control por segunda vez: " + $script:motivoControl)
}
$enCola = Cola
if ($enCola.Count -gt 0) { Terminar 0 'en_espera' ("[OK] hay {0} borrador(es) esperando en la cola; no se genera otro: {1}" -f $enCola.Count, ($enCola -join ', ')) }

# ---- 2. la corrida ----
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) { Terminar 1 'falla' '[FALLA] claude no esta en el PATH' }
Remove-Item $Resultado -ErrorAction SilentlyContinue
$ahoraAR = (HoraAR).ToString('yyyy-MM-dd HH:mm')
$prompt = @"
Sos la redaccion de Con Interes y corres sin nadie mirando: no hagas preguntas.
Fecha y hora de Buenos Aires: $ahoraAR. Usala para todo lo que dependa del dia (hoy, fecha de la nota, pregunta del dia, que ya publico el INDEC). La maquina esta en otra zona horaria: no te guies por su reloj.
Hace una corrida de redaccion completa siguiendo agente/local/misiones/redaccion.md y agente/NEWSROOM.md al pie de la letra (python, no python3).
El objetivo de cada corrida es publicar UNA nota buena. Trabaja asi:
1. RASTREO, siempre las cuatro cosas: (a) barre las portadas de economia de infobae, lanacion, clarin, ambito, iprofesional, cronista, tn y pagina12 con WebFetch, y anota los temas que se repiten en varias; (b) corre python scripts/build_empresas.py y despues python scripts/agenda.py, para el calendario oficial y el bloque EMPRESAS (lo que las empresas presentaron ante la CNV y la SEC); (c) de ese bloque, minimo 2 candidatas de empresas cuando tiene material; (d) la PREGUNTA DE PLATA detras de la noticia del dia, en cualquier seccion (deporte, espectaculos, sociedad, no solo economia): que pregunta de plata se hace la gente y buscaria en Google (cuanto cobra, cuanto cuesta, cuanto paga el Estado) que se pueda contestar con documentos oficiales. Minimo 2 candidatas de este tipo.
2. Arma una lista de 8 a 12 candidatas ordenada con los criterios del Editor de agente/local/misiones/redaccion.md: primero una pregunta que la gente busca y nadie contesta con datos (asi llego el 61% de los lectores del ultimo mes); el dato del dia del calendario solo gana si trae un angulo que los otros medios no tienen. Si agenda.py dice HOY NO HAY NOTA DE EMPRESAS, una candidata de empresas con documento primario compite con ventaja (NEWSROOM.md 2 quater): descartarla exige una razon escrita en el motivo, y la nota sigue sus lineas rojas. Descarta las que ya estan en data/cubiertas.json como publicada o en_cola sin un angulo nuevo. Las descartadas antes por falta de segunda fuente SI se pueden retomar: desde el 24/09/2026 rige la regla de estadisticas oficiales de NEWSROOM.md seccion 3.
3. Toma la primera candidata y hace investigacion y verificacion completas. Del portal se saca el TEMA; el numero sale siempre de la fuente primaria.
4. Si FRENA, registra el descarte en data/cubiertas.json y pasa a la candidata siguiente, en esta misma corrida. Hasta 4 candidatas. Recien si las 4 frenan, termina sin nota.
La vara no se negocia: la cifra ancla tiene que llegar a CONFIRMADO por alguno de los dos caminos de NEWSROOM.md seccion 3. Nunca inventes, redondees a favor ni publiques un dato que no cierra.
Como maximo UNA nota. Dejala en cola/ con noindex, agregala a data/cola.json, registrala en data/cubiertas.json como en_cola y corre python scripts/build_portada.py.
Antes de terminar, corre vos los tres chequeos del editor de cierre (URLs 200, superlativos con valor previo, coherencia copete-graficos-cuerpo-manifiesto).
Si es la primera corrida del dia y data/pregunta.json no es de hoy, actualizala. Sin kit social.
PROHIBIDO: correr aprobar.py o rechazar.py, usar git, tocar notas ya publicadas, poner credenciales en ningun lado. La publicacion la hace el script que te llamo, despues de controlar tu trabajo.
AL FINAL escribi el archivo .corrida.json en la raiz del repo: un objeto JSON con tres claves de texto.
veredicto: APTA, FRENAR o SIN_TEMA. id: el id de la nota en la cola, o vacio. motivo: una linea que explique el resultado; si no hubo nota, nombra cada candidata que probaste y por que freno.
"@
Anotar 'llamando a la redaccion...'
$salida = & claude -p $prompt --permission-mode dontAsk `
  --allowedTools 'Read' 'Glob' 'Grep' 'WebFetch' 'WebSearch' 'Write' 'Edit' 'Bash(python:*)' 'Bash(py:*)' 'Bash(curl:*)' 2>&1
$codigo = $LASTEXITCODE
Add-Content -Path $Log -Value ($salida | Out-String) -Encoding UTF8
Anotar "claude termino con codigo $codigo"

if (-not (Test-Path $Resultado)) { Terminar 1 'falla' '[FALLA] la redaccion no dejo .corrida.json; el repo queda como esta para revisarlo' }
$r = Get-Content $Resultado -Raw -Encoding UTF8 | ConvertFrom-Json
Remove-Item $Resultado -ErrorAction SilentlyContinue
Anotar ("veredicto: {0} | {1} | {2}" -f $r.veredicto, $r.id, $r.motivo)

if ($r.veredicto -ne 'APTA') {
  # sin nota: se sube solo lo que haya quedado registrado (descarte, pregunta del dia)
  $quedo = Cola
  if ($quedo.Count -gt 0) { Terminar 1 'falla' ("[FALLA] veredicto {0} pero quedo un borrador en la cola; no se sube nada" -f $r.veredicto) }
  Subir ("Redaccion: corrida sin nota ({0})" -f $r.veredicto)
  $res = 'sin_tema'; if ($r.veredicto -eq 'FRENAR') { $res = 'frenada' }
  Terminar 0 $res ("[OK] corrida sin nota: {0} - {1}" -f $r.veredicto, $r.motivo)
}

# ---- 3. controles sobre el borrador, y 4. publicar ----
$id = "$($r.id)".Trim()
if ($id -notmatch '^\d{4}-\d{2}-\d{2}-[a-z0-9-]+$') { Terminar 1 'falla' "[FALLA] id invalido: '$id'" }
$rc = Publicar $id
if ($rc -eq 2) {
  # falla transitoria: el borrador se commitea en la cola (con noindex) y la
  # corrida siguiente le repite el control antes de investigar otra cosa
  Subir "Redaccion: queda en cola $id (fuente sin respuesta, se reintenta)" $id
  GuardarRetenidos @(@(LeerRetenidos) + $id | Select-Object -Unique)
  Terminar 0 'retenida' "[RETENIDA] $id no paso el control por una fuente que no respondio; se reintenta en la corrida siguiente: $($script:motivoControl)" $id
}
Rechazar $id $script:motivoControl
Terminar 0 'rechazada' "[RECHAZADA] $id no paso el control: $($script:motivoControl)" $id
