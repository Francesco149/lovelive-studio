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

function Launch($exe, $arglist, $wd, $out, $err) {
    # Start hidden and fully detached. Win32_Process.Create (WMI) makes a process that is not our child: it holds none of
    # our handles (a caller capturing output, like an agent's shell, would otherwise wait for the engine to exit) and is in
    # no job object (an ssh session or a tool runner would otherwise kill it when its command ends). It runs until
    # "start.ps1 -Stop", a reset, or a reboot. cmd.exe does the redirection to the log files.
    $line = 'cmd.exe /s /c ""' + $exe + '" ' + ((Q $arglist) -join " ") + ' 1>"' + $out + '" 2>"' + $err + '""'
    $si = New-CimInstance -ClassName Win32_ProcessStartup -ClientOnly -Property @{ ShowWindow = [uint16]0 }
    $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $line; CurrentDirectory = $wd; ProcessStartupInformation = $si }
    if ($r.ReturnValue -ne 0) { throw ("could not start " + $exe + " (WMI error " + $r.ReturnValue + ")") }
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
    Launch $Py $cargs $Engine (Join-Path $Logs "comfyui.log") (Join-Path $Logs "comfyui.err.log")
    $t0 = Get-Date
    while (-not (Up "$($S.comfy_url)/system_stats")) {
        if (((Get-Date) - $t0).TotalSeconds -gt 240) {
            Write-Host "The image engine did not start. Ask Claude: 'the studio does not start'." -ForegroundColor Red
            exit 3
        }
        Start-Sleep -Seconds 2
    }
}
if (-not $NoStudio -and (Up "$($S.studio_url)/api/state")) {
    # a Studio started before a `git pull` keeps running the old code: restart it (only the page server, the engine
    # stays loaded) when its code is older than the files, unless it is still drawing pictures
    try {
        $st = Invoke-RestMethod -TimeoutSec 5 "$($S.studio_url)/api/state"
        if ($st.code_now -gt $st.code_stamp -or $null -eq $st.code_stamp) {
            $busy = @(Invoke-RestMethod -TimeoutSec 5 "$($S.studio_url)/api/jobs" | Where-Object { $_.status -in @("queued", "running") })
            if ($busy.Count -gt 0) {
                Write-Host "The Studio was updated; it will load the new version once the $($busy.Count) picture(s) it is drawing are done and it is started again."
            } else {
                Write-Host "loading the updated Studio ..."
                Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
                    Where-Object { $_.ExecutablePath -eq $Py -and $_.CommandLine -like "*server.py*" } |
                    ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force } catch {} }
                Start-Sleep -Seconds 1
            }
        }
    } catch {}
}
if (-not $NoStudio -and -not (Up "$($S.studio_url)/api/state")) {
    Launch $Py @("-s", (Join-Path $PSScriptRoot "studio\server.py")) $Repo (Join-Path $Logs "studio.log") (Join-Path $Logs "studio.err.log")
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
