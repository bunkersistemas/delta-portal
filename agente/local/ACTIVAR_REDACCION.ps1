# ===================================================================
#  ACTIVAR_REDACCION.ps1 -- se corre EN AGENTE007, con el usuario Agentes.
#
#    powershell -NoProfile -ExecutionPolicy Bypass -File agente\local\ACTIVAR_REDACCION.ps1
#
#  Crea la tarea "Con Interes - Redaccion programada": cada 3 horas, corre
#  agente\local\redaccion_programada.ps1. Una de las corridas cae a las 16:30
#  de Buenos Aires (19:30 UTC), media hora despues de que publican INDEC y BCRA.
#  Idempotente: se puede correr dos veces. Necesita la sesion de Agentes
#  iniciada, como la auditoria.
#
#  Para apagarla:  Disable-ScheduledTask -TaskName 'Con Interes - Redaccion programada'
# ===================================================================
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
# Cada 3 horas desde ahi: 16:30, 19:30, 22:30, 01:30, 04:30, 07:30, 10:30, 13:30 de Buenos Aires.
$ancla = [DateTime]::SpecifyKind((Get-Date).ToUniversalTime().Date.AddHours(19.5), 'Utc').ToLocalTime()
$disparo = New-ScheduledTaskTrigger -Once -At $ancla -RepetitionInterval (New-TimeSpan -Hours 3)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive
$ajustes = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2 -Minutes 45) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $Tarea -Action $accion -Trigger $disparo -Principal $principal `
  -Settings $ajustes -Force | Out-Null

$t = Get-ScheduledTask -TaskName $Tarea -ErrorAction SilentlyContinue
if (-not $t) { Write-Output '[FALLA] la tarea no quedo creada'; exit 1 }
$prox = (Get-ScheduledTaskInfo -TaskName $Tarea).NextRunTime
Write-Output "[OK] tarea '$Tarea' creada. Proxima corrida: $prox (hora de esta maquina)"
Write-Output ('     log: ' + (Join-Path $env:USERPROFILE 'coninteres-logs'))
