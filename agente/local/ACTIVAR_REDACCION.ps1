# ===================================================================
#  ACTIVAR_REDACCION.ps1 -- se corre EN AGENTE007, con el usuario Agentes.
#
#    powershell -NoProfile -ExecutionPolicy Bypass -File agente\local\ACTIVAR_REDACCION.ps1
#
#  Crea la tarea "Con Interes - Redaccion programada": cada hora (o cada
#  -Horas N), corre agente\local\redaccion_programada.ps1. Una de las corridas
#  cae a las 16:30 de Buenos Aires (19:30 UTC), media hora despues de que
#  publican INDEC y BCRA. Si una corrida sigue trabajando cuando toca la
#  siguiente, la siguiente se saltea. Idempotente: correrlo de nuevo cambia
#  la frecuencia. Necesita la sesion de Agentes iniciada, como la auditoria.
#
#    ...ACTIVAR_REDACCION.ps1            cada 1 hora (desde el 23/09/2026)
#    ...ACTIVAR_REDACCION.ps1 -Horas 3   cada 3 horas
#
#  Para apagarla:  Disable-ScheduledTask -TaskName 'Con Interes - Redaccion programada'
# ===================================================================
param([ValidateSet(1,2,3,4,6,8,12)][int]$Horas = 1)
$ErrorActionPreference = 'Continue'
$env:GIT_TERMINAL_PROMPT = '0'
$Raiz = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Tarea = 'Con Interes - Redaccion programada'
$Script = Join-Path $Raiz 'agente\local\redaccion_programada.ps1'

Set-Location $Raiz
git pull --ff-only origin main 2>&1 | Out-Null
Write-Output ('version: ' + (git log --oneline -1))
if (-not (Test-Path $Script)) { Write-Output "[FALLA] no existe $Script"; exit 1 }

$accion = New-ScheduledTaskAction -Execute 'powershell.exe' `
  -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Script`"" -WorkingDirectory $Raiz

# Ancla en 19:30 UTC (16:30 de Buenos Aires), llevada a la hora de esta maquina.
# Cada $Horas horas desde ahi (los divisores de 24 mantienen las 16:30 todos los dias).
$ancla = [DateTime]::SpecifyKind((Get-Date).ToUniversalTime().Date.AddHours(19.5), 'Utc').ToLocalTime()
while ($ancla -gt (Get-Date).AddHours($Horas)) { $ancla = $ancla.AddHours(-$Horas) }
$disparo = New-ScheduledTaskTrigger -Once -At $ancla -RepetitionInterval (New-TimeSpan -Hours $Horas)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive
$ajustes = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2 -Minutes 45) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $Tarea -Action $accion -Trigger $disparo -Principal $principal `
  -Settings $ajustes -Force | Out-Null

$t = Get-ScheduledTask -TaskName $Tarea -ErrorAction SilentlyContinue
if (-not $t) { Write-Output '[FALLA] la tarea no quedo creada'; exit 1 }
$prox = (Get-ScheduledTaskInfo -TaskName $Tarea).NextRunTime
$proxAR = [TimeZoneInfo]::ConvertTimeBySystemTimeZoneId($prox, 'Argentina Standard Time')
Write-Output ("[OK] tarea '$Tarea' creada, cada $Horas hora(s). Proxima corrida: {0:dd/MM HH:mm} de Buenos Aires" -f $proxAR)
Write-Output ('     log: ' + (Join-Path $env:USERPROFILE 'coninteres-logs'))
