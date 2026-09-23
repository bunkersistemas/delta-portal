# ===================================================================
#  ACTIVAR_AUDITORIA.ps1 -- se corre EN AGENTE007, con el usuario Agentes.
#
#    powershell -NoProfile -ExecutionPolicy Bypass -File agente\local\ACTIVAR_AUDITORIA.ps1
#
#  Crea la tarea "Con Interes - Auditoria semanal": lunes 07:00, corre
#  agente\local\auditoria_semanal.ps1. Idempotente: se puede correr dos veces.
#  Como la del agente contable, necesita la sesion de Agentes iniciada.
# ===================================================================
$ErrorActionPreference = 'Continue'
$env:GIT_TERMINAL_PROMPT = '0'
$Raiz = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Tarea = 'Con Interes - Auditoria semanal'
$Script = Join-Path $Raiz 'agente\local\auditoria_semanal.ps1'

Set-Location $Raiz
git pull --ff-only origin main 2>&1 | Out-Null
Write-Output ('version: ' + (git log --oneline -1))
if (-not (Test-Path $Script)) { Write-Output "[FALLA] no existe $Script"; exit 1 }

$zona = [System.TimeZoneInfo]::Local.Id
Write-Output "zona horaria de esta maquina: $zona (el disparo va hasta una hora antes y el script espera a las 07:00 de Buenos Aires)"

$accion = New-ScheduledTaskAction -Execute 'powershell.exe' `
  -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Script`"" -WorkingDirectory $Raiz
# La VM no esta en hora argentina. El disparo es un poco ANTES de las 07:00 de
# Buenos Aires (10:00 UTC) en cualquier zona y estacion, y el script espera
# hasta las 10:00 UTC: asi no depende de como guarde la hora el Programador ni
# del cambio de horario europeo. Argentina no cambia de horario.
$ahora = Get-Date
$offset = [System.TimeZoneInfo]::Local.GetUtcOffset($ahora).TotalHours
$horaLocal = [math]::Floor(10 + $offset - 1)          # una hora antes, en hora local
if ($horaLocal -lt 0) { $horaLocal += 24 }
$disparo = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At ('{0:00}:00' -f $horaLocal)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive
$ajustes = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 4) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $Tarea -Action $accion -Trigger $disparo -Principal $principal `
  -Settings $ajustes -Force | Out-Null

$t = Get-ScheduledTask -TaskName $Tarea -ErrorAction SilentlyContinue
if (-not $t) { Write-Output '[FALLA] la tarea no quedo creada'; exit 1 }
$prox = (Get-ScheduledTaskInfo -TaskName $Tarea).NextRunTime
Write-Output "[OK] tarea '$Tarea' creada. Proxima corrida: $prox"
Write-Output ('     log: ' + (Join-Path $env:USERPROFILE 'coninteres-logs'))
