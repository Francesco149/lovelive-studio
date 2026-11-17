# start.ps1 - starts the image engine (ComfyUI, hidden) and the Studio page, then opens the browser.
#
#   powershell -ExecutionPolicy Bypass -File kit\start.ps1              # what the desktop shortcut runs
#   ... -NoBrowser      do not open the browser        ... -ComfyUI   open ComfyUI's own editor too
#   ... -Restart        stop and start again           ... -Stop      stop both
#   ... -NoStudio       engine only (setup's self-test)
# Logs: <data>\logs\comfyui.log, comfyui.err.log, studio.log, studio.err.log
param([switch]$NoBrowser, [switch]$ComfyUI, [switch]$Restart, [switch]$Stop, [switch]$NoStudio)
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$SettingsPath = Join-Path $Repo "my\settings.json"
if (-not (Test-Path $SettingsPath)) {
    Write-Host "The Studio is not set up yet. Open Claude and ask it to set up this folder." -ForegroundColor Red
    exit 2
}
$S = Get-Content $SettingsPath -Raw | ConvertFrom-Json
$Engine = $S.engine_dir
$Py = Join-Path $Engine "python_embeded\python.exe"
$Logs = Join-Path $S.data_dir "logs"
New-Item -ItemType Directory -Force $Logs | Out-Null

function Up($url) {
    try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 $url | Out-Null; return $true } catch { return $false }
}

function Q($list) {
    # Start-Process joins arguments with spaces in Windows PowerShell 5.1: quote the ones with spaces
    return @($list | ForEach-Object { if ("$_" -match '\s') { '"' + $_ + '"' } else { "$_" } })
}

function Stop-Ours {
    # only the processes started from this kit's engine folder
    $procs = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.ExecutablePath -eq $Py }
    foreach ($p in $procs) { try { Stop-Process -Id $p.ProcessId -Force } catch {} }
    Start-Sleep -Seconds 2
}

if ($Stop -or $Restart) { Stop-Ours; if ($Stop) { Write-Host "stopped"; exit 0 } }

if (-not (Up "$($S.comfy_url)/system_stats")) {
    $cargs = @("-s", "ComfyUI\main.py", "--windows-standalone-build", "--listen", "127.0.0.1", "--port", "8188",
              "--output-directory", (Join-Path $S.data_dir "outputs"), "--input-directory", (Join-Path $S.data_dir "inputs"),
              "--disable-auto-launch", "--preview-method", "none")
    if ($S.extra_flags) { $cargs += @($S.extra_flags) }
    Write-Host "starting the image engine ..."
    Start-Process -FilePath $Py -ArgumentList (Q $cargs) -WorkingDirectory $Engine -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $Logs "comfyui.log") -RedirectStandardError (Join-Path $Logs "comfyui.err.log")
    $t0 = Get-Date
    while (-not (Up "$($S.comfy_url)/system_stats")) {
        if (((Get-Date) - $t0).TotalSeconds -gt 240) {
            Write-Host "The image engine did not start. Ask Claude: 'the studio does not start'." -ForegroundColor Red
            exit 3
        }
        Start-Sleep -Seconds 2
    }
}
if (-not $NoStudio -and -not (Up "$($S.studio_url)/api/state")) {
    Start-Process -FilePath $Py -ArgumentList (Q @("-s", (Join-Path $PSScriptRoot "studio\server.py"))) -WorkingDirectory $Repo -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $Logs "studio.log") -RedirectStandardError (Join-Path $Logs "studio.err.log")
    $t0 = Get-Date
    while (-not (Up "$($S.studio_url)/api/state")) {
        if (((Get-Date) - $t0).TotalSeconds -gt 30) { Write-Host "The Studio page did not start (see studio.err.log)." -ForegroundColor Red; exit 4 }
        Start-Sleep -Milliseconds 500
    }
}
if (-not $NoBrowser) {
    if (-not $NoStudio) { Start-Process $S.studio_url }
    if ($ComfyUI) { Start-Process $S.comfy_url }
}
Write-Host "running: Studio $($S.studio_url)  engine $($S.comfy_url)"
exit 0
