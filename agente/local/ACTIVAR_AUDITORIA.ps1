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
if ($zona -notmatch 'Argentina') {
  Write-Output "[AVISO] la zona horaria es '$zona', no Argentina: las 07:00 no son las de Buenos Aires"
}

$accion = New-ScheduledTaskAction -Execute 'powershell.exe' `
  -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Script`"" -WorkingDirectory $Raiz
$disparo = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At '07:00'
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive
$ajustes = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 3) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $Tarea -Action $accion -Trigger $disparo -Principal $principal `
  -Settings $ajustes -Force | Out-Null

$t = Get-ScheduledTask -TaskName $Tarea -ErrorAction SilentlyContinue
if (-not $t) { Write-Output '[FALLA] la tarea no quedo creada'; exit 1 }
$prox = (Get-ScheduledTaskInfo -TaskName $Tarea).NextRunTime
Write-Output "[OK] tarea '$Tarea' creada. Proxima corrida: $prox"
Write-Output ('     log: ' + (Join-Path $env:USERPROFILE 'coninteres-logs'))
