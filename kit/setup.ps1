# setup.ps1 - installs the Love Live Studio on this PC. Safe to run again: finished steps are skipped.
#
#   powershell -ExecutionPolicy Bypass -File kit\setup.ps1 -Check                  # report only (GPU, driver, RAM, drives)
#   powershell -ExecutionPolicy Bypass -File kit\setup.ps1 -DataDir "D:\LoveLiveStudio"
#   ... -Optional turbo,base,h3  also download optional models (kit\manifest.json "key"): turbo 4 GB, base 4 GB, h3 29 GB
#   ... -Build pascal|modern     override the automatic engine choice (normally never needed)
#
# Everything big lives in -DataDir: downloads\, engine\ (ComfyUI portable), models\, outputs\, inputs\, logs\.
# The repo keeps only text, small pictures and my\settings.json. Exit codes: 0 ok, 10 driver too old,
# 11 not enough disk space, 12 no NVIDIA GPU, 13 download/verify failed, 14 self-test failed.
param(
    [string]$DataDir,
    [switch]$Check,
    [string[]]$Optional = @(),
    [ValidateSet("auto", "modern", "pascal")][string]$Build = "auto",
    [switch]$NoShortcut,
    [switch]$SkipSelftest,
    [switch]$Use7z   # testing: skip Windows tar and unpack with 7-Zip (what happens on Windows 10)
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$Repo = Split-Path -Parent $PSScriptRoot
$My = Join-Path $Repo "my"
$Manifest = Get-Content (Join-Path $PSScriptRoot "manifest.json") -Raw | ConvertFrom-Json
New-Item -ItemType Directory -Force $My | Out-Null
try { Start-Transcript -Path (Join-Path $My "setup.log") -Append | Out-Null } catch {}

function Run-Native {
    # Windows PowerShell 5.1 turns a native program's stderr into a terminating error under "Stop": relax it for the call
    $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    try { & $args[0] @($args | Select-Object -Skip 1) } finally { $ErrorActionPreference = $old }
}
function Say($msg) { Write-Host ("[setup] " + $msg) }
function Fail($code, $msg) { Write-Host ("[setup] PROBLEM: " + $msg) -ForegroundColor Red; exit $code }

function Save-Json($obj, $path) {
    $json = $obj | ConvertTo-Json -Depth 8
    [System.IO.File]::WriteAllText($path, $json, (New-Object System.Text.UTF8Encoding($false)))
}

function Get-SystemReport {
    $r = [ordered]@{}
    $os = Get-CimInstance Win32_OperatingSystem
    $r.windows = $os.Caption + " " + $os.Version
    $r.ram_gb = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
    $r.cpu = (Get-CimInstance Win32_Processor | Select-Object -First 1).Name.Trim()
    $smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
    if (-not $smi) { $p = "C:\Windows\System32\nvidia-smi.exe"; if (Test-Path $p) { $smi = $p } }
    if ($smi) {
        $line = & $smi --query-gpu=name,memory.total,driver_version,compute_cap --format=csv,noheader,nounits 2>$null | Select-Object -First 1
        if ($line) {
            $f = $line.Split(",") | ForEach-Object { $_.Trim() }
            $r.gpu = $f[0]; $r.vram_gb = [math]::Round([double]$f[1] / 1024, 1); $r.driver = $f[2]; $r.compute_cap = $f[3]
        }
    }
    if (-not $r.gpu) {
        $v = Get-CimInstance Win32_VideoController | Where-Object { $_.Name -like "*NVIDIA*" } | Select-Object -First 1
        if ($v) { $r.gpu = $v.Name; $r.driver_note = "nvidia-smi missing: install or update the NVIDIA driver" }
    }
    $disks = @{}
    try { Get-PhysicalDisk | ForEach-Object { $disks[[string]$_.DeviceId] = [string]$_.MediaType } } catch {}
    $vols = @()
    foreach ($v in (Get-Volume | Where-Object { $_.DriveLetter -and $_.DriveType -eq "Fixed" -and $_.Size -gt 0 })) {
        $media = "unknown"
        try {
            $part = Get-Partition -DriveLetter $v.DriveLetter -ErrorAction Stop
            if ($disks.ContainsKey([string]$part.DiskNumber)) { $media = $disks[[string]$part.DiskNumber] }
        } catch {}
        $vols += [ordered]@{ drive = [string]$v.DriveLetter + ":"; label = $v.FileSystemLabel; free_gb = [math]::Round($v.SizeRemaining / 1GB, 0);
                             size_gb = [math]::Round($v.Size / 1GB, 0); media = $media }
    }
    $r.drives = $vols
    return $r
}

function Get-NeedGB($build, $opt) {
    $b = $Manifest.engine.builds.$build
    $bytes = [double]$b.size * 3.2   # archive + extracted engine (~4.3 GB)
    foreach ($m in $Manifest.models) {
        if ($m.required -or ($opt -contains $m.key)) { $bytes += [double]$m.size }
    }
    return [math]::Ceiling($bytes / 1GB) + 10   # + room for a few thousand pictures
}

function Download($url, $dest, $size, $sha) {
    $dir = Split-Path -Parent $dest
    New-Item -ItemType Directory -Force $dir | Out-Null
    $okFile = $dest + ".ok"
    if ((Test-Path $dest) -and (Test-Path $okFile)) {
        $it = Get-Item $dest
        if ((Get-Content $okFile -Raw).Trim() -eq ("{0} {1}" -f $it.Length, $it.LastWriteTimeUtc.Ticks)) { Say ("ok (already verified): " + (Split-Path -Leaf $dest)); return }
    }
    for ($try = 1; $try -le 3; $try++) {
        if (-not (Test-Path $dest) -or (Get-Item $dest).Length -lt $size) {
            Say ("downloading {0} ({1:n1} GB) ..." -f (Split-Path -Leaf $dest), ($size / 1GB))
            Run-Native curl.exe -L --fail --retry 5 --retry-delay 5 -C - -o $dest $url
            if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 33) { Say "download interrupted (curl $LASTEXITCODE), retrying"; continue }
        }
        $len = (Get-Item $dest).Length
        if ($len -ne $size) { Say "size ${len}, expected ${size}: starting this file again"; Remove-Item $dest -Force; continue }
        Say ("checking " + (Split-Path -Leaf $dest) + " ...")
        $h = (Get-FileHash -Algorithm SHA256 $dest).Hash.ToLower()
        if ($h -ne $sha) { Say "checksum mismatch: starting this file again"; Remove-Item $dest -Force; continue }
        $it = Get-Item $dest
        Set-Content -Path $okFile -Value ("{0} {1}" -f $it.Length, $it.LastWriteTimeUtc.Ticks) -Encoding ASCII
        return
    }
    Fail 13 ("could not download " + $url)
}

# ---------------------------------------------------------------- 1. the machine
$sys = Get-SystemReport
New-Item -ItemType Directory -Force $My | Out-Null
Save-Json $sys (Join-Path $My "system.json")
Say ("Windows: {0} | CPU: {1} | RAM: {2} GB" -f $sys.windows, $sys.cpu, $sys.ram_gb)
Say ("GPU: {0} | VRAM: {1} GB | driver {2} | compute {3}" -f $sys.gpu, $sys.vram_gb, $sys.driver, $sys.compute_cap)
foreach ($d in $sys.drives) { Say ("drive {0} {1}: {2} GB free of {3} GB ({4})" -f $d.drive, $d.label, $d.free_gb, $d.size_gb, $d.media) }

if (-not $sys.gpu -or $sys.gpu -notlike "*NVIDIA*") { Fail 12 "no NVIDIA graphics card found. This kit needs an NVIDIA GPU with 8 GB." }
if ($Build -eq "auto") {
    $Build = "modern"
    if ($sys.compute_cap -and [double]$sys.compute_cap -lt 7.5) { $Build = "pascal" }
    if (-not $sys.compute_cap -and $sys.gpu -match "GTX (9|10)\d\d") { $Build = "pascal" }
}
$B = $Manifest.engine.builds.$Build
Say ("engine build: {0} ({1})" -f $Build, $B.for)
if ($sys.driver -and [double]$sys.driver -lt [double]$B.min_driver) {
    Fail 10 ("the NVIDIA driver {0} is too old; this needs {1} or newer. Update it from https://www.nvidia.com/Download/index.aspx (GeForce, your card), then run setup again." -f $sys.driver, $B.min_driver)
}
$opt = @($Optional | ForEach-Object { $_.Split(",") } | ForEach-Object { $_.Trim().ToLower() } | Where-Object { $_ })
$need = Get-NeedGB $Build $opt
Say ("space needed: about {0} GB" -f $need)
if ($Check) { exit 0 }

# ---------------------------------------------------------------- 2. where the big files go
$SettingsPath = Join-Path $My "settings.json"
$S = $null
if (Test-Path $SettingsPath) { $S = Get-Content $SettingsPath -Raw | ConvertFrom-Json }
if (-not $DataDir -and $S) { $DataDir = $S.data_dir }
if (-not $DataDir) { Fail 11 "no -DataDir given. Ask the user which drive to use (see CLAUDE.md 'Storage'), then run again with -DataDir." }
$DataDir = [System.IO.Path]::GetFullPath($DataDir)
$drive = $DataDir.Substring(0, 2)
$free = [math]::Round((Get-PSDrive $drive.TrimEnd(":")).Free / 1GB, 0)
$have = 0
if (Test-Path $DataDir) { $have = [math]::Round(((Get-ChildItem $DataDir -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum) / 1GB, 0) }
if ($free + $have -lt $need) { Fail 11 ("drive {0} has {1} GB free, about {2} GB is needed. Pick another drive or free some space." -f $drive, $free, $need) }
foreach ($sub in "downloads", "engine", "models", "outputs", "inputs", "logs") { New-Item -ItemType Directory -Force (Join-Path $DataDir $sub) | Out-Null }
Say ("data folder: " + $DataDir)

# ---------------------------------------------------------------- 3. Visual C++ runtime (torch needs it)
$vc = Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" -ErrorAction SilentlyContinue
if (-not $vc -or $vc.Installed -ne 1) {
    Say "installing the Microsoft Visual C++ runtime (Windows may ask for permission) ..."
    $vcexe = Join-Path $DataDir "downloads\vc_redist.x64.exe"
    Run-Native curl.exe -L --fail -o $vcexe "https://aka.ms/vs/17/release/vc_redist.x64.exe"
    Start-Process -FilePath $vcexe -ArgumentList "/install", "/quiet", "/norestart" -Verb RunAs -Wait
} else { Say "Visual C++ runtime: ok" }

# ---------------------------------------------------------------- 4. the engine (ComfyUI portable, pinned)
$archive = Join-Path $DataDir ("downloads\" + $B.file)
Download $B.url $archive ([int64]$B.size) $B.sha256
$EngineRoot = Join-Path $DataDir "engine"
$Engine = Join-Path $EngineRoot "ComfyUI_windows_portable"
$marker = Join-Path $Engine ".studio-engine"
$want = "{0} {1}" -f $Manifest.engine.version, $Build
if (-not (Test-Path $marker) -or (Get-Content $marker -Raw).Trim() -ne $want) {
    if (Test-Path $Engine) {
        $old = $Engine + ".old-" + (Get-Date -Format "yyyyMMdd-HHmmss")
        Say ("moving the previous engine aside to " + $old); Rename-Item $Engine $old
    }
    Say "unpacking the engine (about a minute) ..."
    $ok = $false
    if (-not $Use7z) {
        Run-Native tar.exe -xf $archive -C $EngineRoot
        $ok = ($LASTEXITCODE -eq 0) -and (Test-Path (Join-Path $Engine "python_embeded\python.exe"))
    }
    if (-not $ok) {
        Say "Windows' own unpacker can't open this archive here; using 7-Zip instead"
        if (Test-Path $Engine) { Remove-Item -Recurse -Force $Engine }
        $t = $Manifest.tools."7zr"
        $sz = Join-Path $DataDir "downloads\7zr.exe"
        Download $t.url $sz ([int64]$t.size) $t.sha256
        Run-Native $sz x $archive ("-o" + $EngineRoot) -y | Out-Null
        $ok = ($LASTEXITCODE -eq 0) -and (Test-Path (Join-Path $Engine "python_embeded\python.exe"))
    }
    if (-not $ok) { Fail 13 "unpacking the engine failed" }
    Set-Content -Path $marker -Value $want -Encoding ASCII
} else { Say ("engine " + $want + ": ok") }

# ---------------------------------------------------------------- 5. models
foreach ($m in $Manifest.models) {
    if (-not $m.required -and -not ($opt -contains $m.key)) { continue }
    Download $m.url (Join-Path $DataDir ("models\" + $m.dir + "\" + $m.file)) ([int64]$m.size) $m.sha256
}

# ---------------------------------------------------------------- 6. wire the engine to the data folder
$mp = ($DataDir -replace "\\", "/") + "/models"
$yaml = "studio:`n    base_path: $mp`n    diffusion_models: diffusion_models`n    text_encoders: text_encoders`n    vae: vae`n    model_patches: model_patches`n    loras: loras`n    checkpoints: checkpoints`n"
[System.IO.File]::WriteAllText((Join-Path $Engine "ComfyUI\extra_model_paths.yaml"), $yaml, (New-Object System.Text.UTF8Encoding($false)))
foreach ($sub in "loras", "checkpoints") { New-Item -ItemType Directory -Force (Join-Path $DataDir ("models\" + $sub)) | Out-Null }
$wfDst = Join-Path $Engine "ComfyUI\user\default\workflows"
New-Item -ItemType Directory -Force $wfDst | Out-Null
Copy-Item (Join-Path $PSScriptRoot "workflows\Love Live*.json") $wfDst -Force -ErrorAction SilentlyContinue
$cs = Join-Path $Engine "ComfyUI\user\default\comfy.settings.json"
if (-not (Test-Path $cs)) { Copy-Item (Join-Path $PSScriptRoot "comfy.settings.json") $cs }   # no first-run template gallery
$ctlDst = Join-Path $DataDir "inputs\studio"
New-Item -ItemType Directory -Force $ctlDst | Out-Null
Copy-Item (Join-Path $PSScriptRoot "controls\*.png") $ctlDst -Force   # so ComfyUI's editor lists the body drawings

# ---------------------------------------------------------------- 7. settings
$flags = @()
if ($S -and $S.extra_flags) { $flags = @($S.extra_flags) }
$settings = [ordered]@{
    data_dir = $DataDir; engine_dir = $Engine; engine_build = $Build; engine_version = $Manifest.engine.version
    comfy_url = "http://127.0.0.1:8188"; studio_url = "http://127.0.0.1:8190"; extra_flags = $flags
    gpu = $sys.gpu; vram_gb = $sys.vram_gb; ram_gb = $sys.ram_gb; optional_models = $opt
    setup_date = (Get-Date -Format "yyyy-MM-dd HH:mm")
}
Save-Json $settings $SettingsPath
Say ("settings saved: " + $SettingsPath)

# ---------------------------------------------------------------- 8. desktop shortcut
if (-not $NoShortcut) {
    $lnk = Join-Path ([Environment]::GetFolderPath("Desktop")) "Love Live Studio.lnk"
    $ws = New-Object -ComObject WScript.Shell
    $sc = $ws.CreateShortcut($lnk)
    $sc.TargetPath = Join-Path $Repo "Love Live Studio.cmd"
    $sc.WorkingDirectory = $Repo
    $sc.WindowStyle = 7
    $ico = Join-Path $PSScriptRoot "studio\icon.ico"
    if (Test-Path $ico) { $sc.IconLocation = $ico }
    $sc.Save()
    Say ("desktop shortcut: " + $lnk)
}

# ---------------------------------------------------------------- 9. start + self-test (black-image fallback for old cards)
if ($SkipSelftest) { Say "done (self-test skipped)"; exit 0 }
$py = Join-Path $Engine "python_embeded\python.exe"
$tries = @(@(), @("--fp32-vae"), @("--fp32-vae", "--force-fp32"))
if ($flags.Count -gt 0) { $tries = @(, $flags) + $tries }
foreach ($t in $tries) {
    $settings.extra_flags = $t; Save-Json $settings $SettingsPath
    & powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "start.ps1") -Restart -NoBrowser -NoStudio
    if ($LASTEXITCODE -ne 0) { Fail 14 "the engine did not start; see the logs folder in the data folder" }
    Say ("self-test with flags [" + ($t -join " ") + "] (the first image loads the models, a few minutes on old cards) ...")
    & $py -s (Join-Path $PSScriptRoot "studio\gen.py") selftest
    if ($LASTEXITCODE -eq 0) { Say "self-test passed. Setup finished."; exit 0 }
    Say "self-test picture looked wrong (black or blank); trying safer settings"
}
Fail 14 "the self-test failed with every setting; see CLAUDE.md 'Troubleshooting'"
