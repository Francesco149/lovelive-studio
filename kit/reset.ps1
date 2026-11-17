# reset.ps1 - put the Studio back into its known-good state. Never touches pictures (outputs), models or my\.
#
#   powershell -ExecutionPolicy Bypass -File kit\reset.ps1                 # soft: stop, clear temp + editor settings, restore workflows, restart, self-test
#   powershell -ExecutionPolicy Bypass -File kit\reset.ps1 -Level engine   # unpack the pinned engine again (old one moved aside)
#   powershell -ExecutionPolicy Bypass -File kit\reset.ps1 -Level models   # re-check model checksums, re-download broken ones
param([ValidateSet("soft", "engine", "models")][string]$Level = "soft", [switch]$NoSelftest)
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$SettingsPath = Join-Path $Repo "my\settings.json"
if (-not (Test-Path $SettingsPath)) { Write-Host "Not set up yet: run kit\setup.ps1 first." -ForegroundColor Red; exit 2 }
$S = Get-Content $SettingsPath -Raw | ConvertFrom-Json
$Engine = $S.engine_dir
function Say($m) { Write-Host ("[reset] " + $m) }

Say "stopping the engine and the Studio page"
& powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "start.ps1") -Stop | Out-Null

if ($Level -eq "engine") {
    if (Test-Path $Engine) {
        $old = $Engine + ".old-" + (Get-Date -Format "yyyyMMdd-HHmmss")
        Say ("moving the current engine aside: " + $old)
        Rename-Item $Engine $old
    }
    # setup re-unpacks the pinned engine (the archive is kept in <data>\downloads, re-downloaded if missing) and rewires it
    & powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "setup.ps1") -DataDir $S.data_dir -NoShortcut -SkipSelftest
    if ($LASTEXITCODE -ne 0) { Say "setup failed, see my\setup.log"; exit $LASTEXITCODE }
}
elseif ($Level -eq "models") {
    Get-ChildItem (Join-Path $S.data_dir "models") -Recurse -Filter "*.ok" | Remove-Item -Force
    $opt = @()
    if ($S.optional_models) { $opt = @($S.optional_models) }
    $a = @("-ExecutionPolicy", "Bypass", "-File", (Join-Path $PSScriptRoot "setup.ps1"), "-DataDir", $S.data_dir, "-NoShortcut", "-SkipSelftest")
    if ($opt.Count -gt 0) { $a += @("-Optional", ($opt -join ",")) }
    & powershell @a
    if ($LASTEXITCODE -ne 0) { Say "setup failed, see my\setup.log"; exit $LASTEXITCODE }
}
else {
    $temp = Join-Path $Engine "ComfyUI\temp"
    if (Test-Path $temp) { Remove-Item -Recurse -Force $temp -ErrorAction SilentlyContinue }
    $userDir = Join-Path $Engine "ComfyUI\user\default"
    $set = Join-Path $userDir "comfy.settings.json"
    if (Test-Path $set) {
        $bak = $set + ".bak-" + (Get-Date -Format "yyyyMMdd-HHmmss")
        Move-Item $set $bak; Say ("editor settings reset (old copy: " + $bak + ")")
    }
    $wf = Join-Path $userDir "workflows"
    New-Item -ItemType Directory -Force $wf | Out-Null
    Copy-Item (Join-Path $PSScriptRoot "workflows\Love Live*.json") $wf -Force
    $ctl = Join-Path $S.data_dir "inputs\studio"
    New-Item -ItemType Directory -Force $ctl | Out-Null
    Copy-Item (Join-Path $PSScriptRoot "controls\*.png") $ctl -Force
    Say "workflows and body drawings restored"
}

& powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "start.ps1") -NoBrowser -NoStudio
if ($LASTEXITCODE -ne 0) { Say "the engine does not start: read <data>\logs\comfyui.err.log"; exit 14 }
if (-not $NoSelftest) {
    & (Join-Path $Engine "python_embeded\python.exe") -s (Join-Path $PSScriptRoot "studio\gen.py") selftest
    if ($LASTEXITCODE -ne 0) { Say "self-test failed"; exit 14 }
}
& powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "start.ps1") -NoBrowser
Say "done: the Studio is back to its known-good state"
exit 0
