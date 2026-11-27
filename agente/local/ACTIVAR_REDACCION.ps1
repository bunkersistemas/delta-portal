# ===================================================================
#  ACTIVAR_REDACCION.ps1 -- se corre EN AGENTE007, con el usuario Agentes.
#
#    powershell -NoProfile -ExecutionPolicy Bypass -File agente\local\ACTIVAR_REDACCION.ps1
#
#  Crea la tarea "Con Interes - Redaccion programada": corre
#  agente\local\redaccion_programada.ps1 en los TURNOS de abajo (hora de Buenos
#  Aires), cuando la gente lee (editor, 27/11/2026). Antes eran cada 6 h desde
#  las 16:30 y la de las 04:30 salia cuando nadie lee.
#
#  Corre SIN sesion iniciada (S4U, editor 27/11/2026): el 26/11 la VM se apago,
#  volvio sin la sesion de Agentes y la redaccion no corrio 14 h. Probado el
#  27/11 con una tarea S4U: claude, git por SSH y python andan sin sesion.
#
#  Las corridas extra de una sola vez (finales, coberturas) que ya tenga la
#  tarea y sean futuras SE CONSERVAN. Idempotente.
#
#  Para apagarla:  Disable-ScheduledTask -TaskName 'Con Interes - Redaccion programada'
# ===================================================================
param([string[]]$Turnos = @('07:00', '12:00', '17:00', '21:00'))
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

# Turnos diarios: hora AR -> UTC (AR es UTC-3 todo el ano) -> hora de esta maquina.
# El disparador queda anclado en UTC: el cambio de horario de Europa no lo corre.
$disparos = @()
foreach ($t in $Turnos) {
  $hm = [TimeSpan]::Parse($t)
  $utc = [DateTime]::SpecifyKind((Get-Date).ToUniversalTime().Date.Add($hm).AddHours(3), 'Utc')
  $disparos += New-ScheduledTaskTrigger -Daily -At $utc.ToLocalTime()
}
# Corridas extra de una sola vez que ya existan y sean futuras: se conservan.
$vieja = Get-ScheduledTask -TaskName $Tarea -ErrorAction SilentlyContinue
$extra = 0
if ($vieja) {
  foreach ($tr in $vieja.Triggers) {
    $esUnaVez = ($tr.CimClass.CimClassName -eq 'MSFT_TaskTimeTrigger') -and (-not $tr.Repetition.Interval)
    if ($esUnaVez -and ([DateTime]::Parse($tr.StartBoundary) -gt (Get-Date))) {
      $disparos += New-ScheduledTaskTrigger -Once -At ([DateTime]::Parse($tr.StartBoundary))
      $extra++
    }
  }
}
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U
# 4 h 30: un turno puede encadenar hasta 3 corridas (si la nota no cumple, otra en el acto).
$ajustes = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 4 -Minutes 30) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $Tarea -Action $accion -Trigger $disparos -Principal $principal `
  -Settings $ajustes -Force | Out-Null

$t = Get-ScheduledTask -TaskName $Tarea -ErrorAction SilentlyContinue
if (-not $t) { Write-Output '[FALLA] la tarea no quedo creada'; exit 1 }
$prox = (Get-ScheduledTaskInfo -TaskName $Tarea).NextRunTime
$proxAR = [TimeZoneInfo]::ConvertTimeBySystemTimeZoneId($prox, 'Argentina Standard Time')
Write-Output ("[OK] tarea '$Tarea': turnos {0} (AR), {1} corrida(s) extra conservada(s), sin sesion ({2})." -f ($Turnos -join ', '), $extra, $t.Principal.LogonType)
Write-Output ("     proxima corrida: {0:dd/MM HH:mm} de Buenos Aires" -f $proxAR)
